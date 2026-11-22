"""Pilot the corrected CLINC predicate and S2 request before the rerun."""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
from bench.common.budget import Budget
from bench.common.cache import CACHE_DIR, CachedDecider, JsonCache
from bench.common.data import DATA_DIR, load
from bench.e1_e2.pilot import Charged
from bench.e1_e2.revised import revised_questions

import som

CAPS = {"openai": 60.0, "typesafe": 5.0}


def prior_budget():
    budget = Budget(CAPS)
    for pattern, provider in (
        ("e1_typesafe_*.jsonl", "typesafe"),
        ("e1_decisions_*.jsonl", "openai"),
        ("e1_s2_*.jsonl", "openai"),
    ):
        for path in CACHE_DIR.glob(pattern):
            with path.open(encoding="utf-8") as handle:
                for line in handle:
                    amount = json.loads(line)["response"]["envelope"]["cost"]["amount"]
                    if amount is None:
                        raise RuntimeError("Unknown historic cost prevents budget accounting")
                    budget.charge(provider, amount)
    return budget


def namespace(system, split):
    if system == "s2":
        return "e1_s2_cal_clinc150_v2" if split == "calibration" else "e1_s2_clinc150_v2"
    return f"e1_{system}_clinc150_fit_v2"


def main(mode=None):
    if mode is None:
        parser = argparse.ArgumentParser()
        parser.add_argument("--mode", choices=["record", "replay"], default="record")
        mode = parser.parse_args().mode
    if mode == "replay" and not (DATA_DIR / "clinc150-test.parquet").exists():
        raise RuntimeError("Pilot replay requires cached data; refusing to download")
    budget = prior_budget()
    before = budget.summary()
    frame = load("clinc150", "test").iloc[:50]
    rows = []
    for system, provider, factory in (
        ("typesafe", "typesafe", lambda: som.TypeSafe("jev-1.14.0")),
        ("decisions", "openai", lambda: som.OpenAIDecisions("gpt-6-luna")),
        ("s2", "openai", lambda: som.OpenAIResponses("gpt-6.1-terra", reasoning_effort="low")),
    ):
        cache = JsonCache(namespace(system, "test"), mode=mode)
        inner_name = {
            "typesafe": "typesafe/jev-1.14.0",
            "decisions": "openai-decisions/gpt-6-luna",
            "s2": "openai/gpt-6.1-terra",
        }[system]
        tier = "s2.reasoning" if system == "s2" else "s1.decision"
        inner = (
            SimpleNamespace(name=inner_name, system=tier) if mode == "replay" else Charged(factory(), budget, provider)
        )
        decider = CachedDecider(inner, cache)
        qs = revised_questions(system)

        def measure(item, decider=decider, qs=qs, system=system):
            idx, row = item
            result = decider.decide(row.text, qs)
            env = result.envelope
            env.validate()
            usage = env.cost.usage
            if usage is None or env.cost.amount is None or env.implementation is None:
                raise RuntimeError("Incomplete pilot accounting")
            return {
                "dataset": "clinc150",
                "system": system,
                "item_id": idx,
                "gold": row.intent,
                "fit": result.answers["fit"].value,
                "fit_probability": getattr(result.answers["fit"], "probability", None),
                "model": env.implementation.model,
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "cost": env.cost.amount,
                "latency_ms": env.latency_ms,
                "cost_basis": env.cost.basis,
            }

        with ThreadPoolExecutor(max_workers=4) as executor:
            rows.extend(executor.map(measure, frame.iterrows()))
    raw = pd.DataFrame(rows)
    root = Path("bench/results/e1/pilot-v2")
    root.mkdir(parents=True, exist_ok=True)
    raw.to_csv(root / "calls.csv", index=False, lineterminator="\n")
    summary = raw.groupby("system", as_index=False).agg(
        calls=("cost", "size"),
        input_tokens=("input_tokens", "mean"),
        output_tokens=("output_tokens", "mean"),
        cost_per_call=("cost", "mean"),
        latency_p50_ms=("latency_ms", "median"),
        latency_p95_ms=("latency_ms", lambda x: x.quantile(0.95)),
    )
    summary.to_csv(root / "summary.csv", index=False, lineterminator="\n")
    if mode == "replay":
        return
    costs = dict(zip(summary.system, summary.cost_per_call, strict=True))
    projected_extra = {"typesafe": costs["typesafe"] * 8600, "openai": costs["decisions"] * 8600 + costs["s2"] * 6000}
    projected_total = {provider: before.get(provider, 0) + projected_extra[provider] for provider in CAPS}
    manifest = {
        "previous_cache_accounted_usd": before,
        "after_pilot_accounted_usd": budget.summary(),
        "new_spend_usd": {p: round(budget.summary().get(p, 0) - before.get(p, 0), 6) for p in CAPS},
        "projected_extra_usd": projected_extra,
        "projected_total_usd": projected_total,
        "caps_usd": CAPS,
        "models": {str(system): str(group.model.iloc[0]) for system, group in raw.groupby("system")},
        "counts": {str(system): len(group) for system, group in raw.groupby("system")},
        "usage_weighted_cost_usd": {str(system): float(group.cost.sum()) for system, group in raw.groupby("system")},
        "data_sha256": {
            "clinc150-test.parquet": json.loads((DATA_DIR / "CHECKSUMS.json").read_text())["clinc150-test.parquet"]
        },
        "full_run_go": all(projected_total[p] <= 0.8 * CAPS[p] for p in CAPS),
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    (root / "ANALYSIS.md").write_text(
        "# Corrected CLINC pilot\n\nThe original companion predicate could not see the separate Choice's options. "
        "The revised predicate includes the full mechanically humanised in-scope list in its own instructions. "
        "These 50 first test items contain no OOS cases and are not representative.\n\n"
        + summary.to_string(index=False)
        + "\n\nProjected total task spend: "
        + json.dumps(projected_total)
        + ". List-price costs; soft cap, up to one in-flight batch of overshoot.\n"
    )
    print(json.dumps(manifest), flush=True)
    if not manifest["full_run_go"]:
        raise SystemExit("Corrected full run exceeds 80% cap; stopped")


if __name__ == "__main__":
    main()
