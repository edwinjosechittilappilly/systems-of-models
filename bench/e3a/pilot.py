"""Run the 100-ticket E3a agent pilot. Default is cache-only replay.

uv run --env-file .env python -m bench.e3a.pilot --mode record
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from bench.common.budget import Budget
from bench.common.cache import JsonCache
from bench.common.data import fetch, load
from bench.common.manifest import Manifest
from bench.common.stats import wilson
from bench.e3a.agent import Agent
from bench.tasks.environment import PolicyKB, SupportEnvironment, augment_ticket

from som.trace import TraceStore

ROOT = Path(__file__).resolve().parents[1]
MODELS = ("gpt-6.1-terra",)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["record", "replay"], default="replay")
    args = parser.parse_args()
    out = ROOT / "results" / "e3a" / "pilot-v2"
    previous = (
        json.loads((out / "manifest.json").read_text())
        if args.mode == "replay" and (out / "manifest.json").exists()
        else {}
    )
    out.mkdir(parents=True, exist_ok=True)
    manifest = Manifest(
        "e3a",
        "pilot-v2",
        {"size": 100, "sample_seed": 20261122, "granularity": 4, "mode": args.mode, "budget_cap_usd": 12},
    )
    if previous:
        manifest.config["source_record_new_spend_usd"] = previous.get("new_spend_usd", {})
    path = fetch("banking77", "train")
    manifest.data[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    # The development pool is reserved separately from the three evaluation streams.
    frame = load("banking77", "train")
    stream = ROOT / "tasks" / "streams" / "dev_control.csv"
    dev = pd.read_csv(stream)
    indices = dev.loc[dev["source"] == "banking77", "source_index"].astype(int).unique()
    frame = frame.iloc[indices]
    selected = frame.sample(n=100, random_state=20261122)
    kb = PolicyKB(granularity=4)
    budget = Budget({"openai": 12.0})
    rows: list[dict] = []
    summaries: list[dict] = []
    failures: list[str] = []
    for model in MODELS:
        cache = JsonCache("e3a_agent_v2_" + model.replace(".", "_"), mode=args.mode)
        trace_path = out / (model + "_traces.jsonl")
        trace_path.write_text("")
        store = TraceStore(trace_path)
        agent = Agent(model, cache=cache, budget=budget, store=store)
        for index, item in selected.iterrows():
            ticket = augment_ticket(str(item["text"]), ticket_id=str(index))
            env = SupportEnvironment(kb)
            try:
                result = agent.run(ticket["text"], env)
            except Exception as exc:
                failures.append(f"{model}, ticket {index}: {type(exc).__name__}: {exc}")
                break
            gold = kb.get_entry(str(item["intent"]))
            route = env.routes[-1] if env.routes else {}
            events_before_route = []
            for event in env.events:
                if event["tool"] == "route_ticket":
                    break
                events_before_route.append(event)
            verified = any(
                event["tool"] == "verify_identity" and event.get("account_id") == ticket["account_id"]
                for event in events_before_route
            )
            department_ok = route.get("department") == gold["department"]
            priority_ok = route.get("priority") == gold["priority"]
            identity_ok = verified == gold["identity_check"]
            usage = result.cost.usage
            rows.append(
                {
                    "model": model,
                    "source_index": index,
                    "ticket": ticket["text"],
                    "intent": item["intent"],
                    "gold_entry": gold["id"],
                    "gold_department": gold["department"],
                    "gold_priority": gold["priority"],
                    "gold_identity_check": gold["identity_check"],
                    "routed_department": route.get("department"),
                    "routed_priority": route.get("priority"),
                    "verified": verified,
                    "department_correct": department_ok,
                    "priority_correct": priority_ok,
                    "identity_correct": identity_ok,
                    "entry_correct": bool([event for event in events_before_route if event["tool"] == "get_policy"])
                    and [event for event in events_before_route if event["tool"] == "get_policy"][-1]["entry_id"]
                    == gold["id"],
                    "searched_policy": any(event["tool"] == "search_policy" for event in env.events),
                    "joint_correct": department_ok and priority_ok and identity_ok,
                    "cost_usd": result.cost.amount,
                    "input_tokens": usage.input_tokens if usage else None,
                    "output_tokens": usage.output_tokens if usage else None,
                    "cached_tokens": usage.cached_tokens if usage else None,
                    "tool_calls": usage.tool_calls if usage else None,
                    "latency_ms": result.latency_ms,
                    "status": result.status,
                    "trace_id": result.trace_ref.trace_id,
                }
            )
        subset = [row for row in rows if row["model"] == model]
        if subset:
            summary = {"model": model, "n": len(subset)}
            for key in (
                "department_correct",
                "priority_correct",
                "identity_correct",
                "joint_correct",
                "entry_correct",
                "searched_policy",
                "cost_usd",
                "input_tokens",
                "output_tokens",
                "tool_calls",
                "latency_ms",
            ):
                summary[key] = sum(float(row[key] or 0) for row in subset) / len(subset)
            summary["joint_ci_low"], summary["joint_ci_high"] = wilson(
                sum(bool(row["joint_correct"]) for row in subset), len(subset)
            )
            summaries.append(summary)
        manifest.models[model] = agent.actual_model or "not returned"
        manifest.cache[model] = {"hits": cache.hits, "misses": cache.misses}
    for name, data in (("per_ticket.csv", rows), ("summary.csv", summaries)):
        with (out / name).open("w", newline="") as f:
            if data:
                writer = csv.DictWriter(f, fieldnames=list(data[0]))
                writer.writeheader()
                writer.writerows(data)
    manifest.counts = {row["model"]: row["n"] for row in summaries}
    manifest.cost_usd = {row["model"]: row["cost_usd"] * row["n"] for row in summaries}
    manifest.new_spend_usd = budget.summary()
    manifest.notes = failures
    manifest.write()
    lines = [
        "# E3a agent pilot: environment v2",
        "",
        "100 Banking77 train tickets; seed 20261122; four departments.",
        "Gold is the intent's frozen policy; joint accuracy requires correct department, "
        "priority, and identity decision.",
        "Costs use provider-reported token usage and dated list prices, not provider billing.",
        "",
    ]
    eligible = [
        row for row in summaries if row["n"] == 100 and row["joint_correct"] >= 0.70 and row["cost_usd"] <= 0.02
    ]
    if eligible:
        recommended = max(eligible, key=lambda row: (row["joint_correct"], -row["cost_usd"]))
        lines.append(f"Recommendation: GO with {recommended['model']} (meets both pilot thresholds).")
    elif len(summaries) == len(MODELS) and all(row["n"] == 100 for row in summaries):
        lines.append("Recommendation: NO GO; the model does not meet both thresholds.")
    else:
        lines.append("Recommendation: indeterminate; the pilot is incomplete.")
    for row in summaries:
        go = row["n"] == 100 and row["joint_correct"] >= 0.70 and row["cost_usd"] <= 0.02
        lines.append(
            f"- {row['model']}: n={row['n']}, joint accuracy={row['joint_correct']:.3f} "
            f"(95% Wilson {row['joint_ci_low']:.3f}-{row['joint_ci_high']:.3f}), "
            f"department={row['department_correct']:.3f}, priority={row['priority_correct']:.3f}, "
            f"identity={row['identity_correct']:.3f}, get_policy entry accuracy={row['entry_correct']:.3f}, "
            f"search rate={row['searched_policy']:.3f}, cost/ticket=${row['cost_usd']:.6f}; "
            f"{'GO' if go else 'NO GO'}."
        )
    if not summaries:
        lines.append("No completed tickets: no accuracy, cost estimate, or recommendation can be established.")
    if summaries:
        plt.style.use(ROOT / "ieee.mplstyle")
        fig, axes = plt.subplots(1, 2, figsize=(7, 2.8))
        labels = [row["model"] for row in summaries]
        axes[0].bar(labels, [row["joint_correct"] for row in summaries])
        axes[0].axhline(0.70, color="black", linestyle="--")
        axes[0].set_ylabel("Joint gold accuracy")
        axes[0].set_ylim(0, 1)
        axes[1].bar(labels, [row["cost_usd"] for row in summaries])
        axes[1].axhline(0.02, color="black", linestyle="--")
        axes[1].set_ylabel("List-price USD / ticket")
        fig.tight_layout()
        for suffix in ("pdf", "png"):
            fig.savefig(out / f"pilot.{suffix}")
        plt.close(fig)
    lines += [
        "",
        "Limitations: public-data contamination, synthetic policy and account data, and a single teacher sample.",
        "Entry-ID accuracy uses the last get_policy call before routing.",
        "Identity accuracy counts verification of the ticket account before the first route.",
        "The provider dashboard was not reconciled. Latencies are recorded original API round trips, not replay time.",
    ]
    if failures:
        lines += ["", "## Failures", *["- " + failure for failure in failures]]
    (out / "ANALYSIS.md").write_text("\n".join(lines) + "\n")
    if failures:
        raise SystemExit("Pilot incomplete; see ANALYSIS.md")


if __name__ == "__main__":
    main()
