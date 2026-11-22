"""Collect paired teacher runs for E3a streams, sharing the response cache.

Only development streams are exposed by this collection entry point. Evaluation
streams are not touched; callers can reuse ``items_for_stream`` after approval.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import pandas as pd
from bench.common.manifest import Manifest
from bench.e3a.agent import instructions_for
from bench.e3a.providers import E3aProviders
from bench.e3a.spend import JournaledBudget
from bench.tasks.environment import PolicyKB, augment_ticket
from bench.tasks.policy import load_policy
from bench.tasks.streams import shifted_policy

ROOT = Path(__file__).resolve().parents[1]
DEV_STREAMS = (
    "dev_control",
    "dev_restructure_05",
    "dev_restructure_15",
    "dev_restructure_30",
    "dev_clinc",
    "dev_visible",
)


def previous_openai_spend() -> float:
    """Return recorded spend from the v1/v2 pilots; subsequent spend is journaled."""
    v1 = ROOT / "results" / "e3a" / "pilot" / "manifest.json"
    total = sum(json.loads(v1.read_text())["cost_usd"].values()) if v1.exists() else 0.0
    for name in ("pilot-v2",):
        path = ROOT / "results" / "e3a" / name / "manifest.json"
        if path.exists():
            manifest = json.loads(path.read_text())
            total += float(manifest.get("new_spend_usd", {}).get("openai", 0))
            total += float(manifest.get("config", {}).get("source_record_new_spend_usd", {}).get("openai", 0))
    return total


def items_for_stream(frame: pd.DataFrame, *, phase_limit: int | None = None) -> tuple[list[dict[str, Any]], int]:
    """Build initial/shifted KB snapshots and ticket inputs without disclosing gold to the agent."""
    if frame.empty:
        raise ValueError("empty stream")
    shift = len(frame) // 2
    if phase_limit is not None and phase_limit < 1:
        raise ValueError("phase_limit must be positive")
    positions = list(range(shift)) + list(range(shift, len(frame)))
    if phase_limit is not None:
        positions = list(range(min(phase_limit, shift))) + list(range(shift, min(len(frame), shift + phase_limit)))
    base_entries = load_policy(4)
    initial = PolicyKB(entries=base_entries)
    shifted = PolicyKB(entries=shifted_policy(base_entries, frame, 4))
    items: list[dict[str, Any]] = []
    for position in positions:
        row = frame.iloc[position]
        source = str(row["source"])
        source_index = int(row["source_index"])
        ticket_id = str(source_index) if source == "banking77" else f"{source}:{source_index}"
        ticket = augment_ticket(str(row["text"]), ticket_id=ticket_id)
        kb = shifted if position >= shift else initial
        gold = kb.get_entry(str(row["entry_id"]))
        items.append(
            {
                "index": position,
                "text": ticket["text"],
                "ticket": ticket,
                "gold": gold,
                "kb": kb,
                "prompt_version": str(row["prompt_version"]),
            }
        )
    return items, shift


def collect(items: list[dict[str, Any]], providers: E3aProviders, *, workers: int = 8) -> list[dict[str, Any]]:
    """Populate teacher results; any failed calls are returned with their exact error.

    The cache stores each paid Responses call, including unsuccessful complete
    agent runs. Tool-run failures are not silently replaced by a teacher label.
    """

    def one(item: dict[str, Any]) -> dict[str, Any]:
        try:
            result = providers.teacher(
                item["text"],
                item["ticket"]["account_id"],
                item["kb"],
                instructions=instructions_for(item["prompt_version"]),
            )
            item["teacher"] = result
            return {
                "ticket_index": item["index"],
                "status": result.envelope.status,
                "cost_usd": result.envelope.cost.amount,
                "latency_ms": result.envelope.latency_ms,
                "error": "",
            }
        except Exception as exc:
            return {
                "ticket_index": item["index"],
                "status": "error",
                "cost_usd": None,
                "latency_ms": None,
                "error": f"{type(exc).__name__}: {exc}",
            }

    if workers < 1:
        raise ValueError("workers must be positive")
    rows = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(one, item) for item in items]
        for future in as_completed(futures):
            rows.append(future.result())
    return sorted(rows, key=lambda row: row["ticket_index"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("record", "replay"), default="replay")
    parser.add_argument(
        "--phase-limit",
        type=int,
        default=1000,
        help="development tickets per pre/post phase; omit via the Python API for all rows",
    )
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    out = ROOT / "results" / "e3a" / "dev-collection"
    prior = previous_openai_spend()
    budget = JournaledBudget({"openai": 55.0, "typesafe": 5.0}, initial={"openai": prior})
    providers = E3aProviders(args.mode, budget)
    out.mkdir(parents=True, exist_ok=True)
    manifest = Manifest(
        "e3a",
        "dev-collection",
        {
            "mode": args.mode,
            "phase_limit": args.phase_limit,
            "workers": args.workers,
            "budget_caps_usd": budget.caps,
            "prior_total_openai_spend_usd": prior,
        },
    )
    failed = 0
    for name in DEV_STREAMS:
        source = ROOT / "tasks" / "streams" / f"{name}.csv"
        manifest.data[source.name] = hashlib.sha256(source.read_bytes()).hexdigest()
        items, _ = items_for_stream(pd.read_csv(source), phase_limit=args.phase_limit)
        rows = collect(items, providers, workers=args.workers)
        with (out / f"{name}.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["ticket_index", "status", "cost_usd", "latency_ms", "error"])
            writer.writeheader()
            writer.writerows(rows)
        errors = sum(row["status"] == "error" for row in rows)
        manifest.counts[name] = len(rows) - errors
        failed += errors
        if errors:
            manifest.notes.append(f"{name}: {errors} ticket calls failed; see CSV")
            break
    manifest.new_spend_usd = budget.new_spend()
    manifest.cache["teacher"] = {"hits": providers.agent_cache.hits, "misses": providers.agent_cache.misses}
    manifest.models["teacher"] = "gpt-6.1-terra"
    manifest.write()
    if failed:
        raise SystemExit("development collection incomplete; see manifest and CSV")


if __name__ == "__main__":
    main()
