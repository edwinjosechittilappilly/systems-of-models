"""Measure 50 paired test items per dataset before authorizing the full E1/E2 run.

Options are mechanically humanised by replacing underscores with spaces. These
pilot items remain in the full test set and reuse the same cached responses.
"""

from __future__ import annotations

import argparse
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
from bench.common.budget import Budget, BudgetExceeded
from bench.common.cache import CachedDecider, JsonCache
from bench.common.data import DATA_DIR, label_names, load

import som


class Charged:
    """Charge only cache misses, because this adapter sits inside CachedDecider."""

    def __init__(self, inner, budget, provider):
        self.inner, self.budget, self.provider = inner, budget, provider
        self.name, self.system = inner.name, inner.system
        self._rate_lock = threading.Lock()
        self._next_request = 0.0

    def decide(self, input, questions, *, trace_id=None):
        if self.provider == "openai":
            with self._rate_lock:
                delay = max(0.0, self._next_request - time.monotonic())
                if delay:
                    time.sleep(delay)
                self._next_request = time.monotonic() + (0.36 if self.system == "s2.reasoning" else 0.1)
        with self.budget._lock:
            if self.budget.spent[self.provider] >= self.budget.caps[self.provider]:
                raise BudgetExceeded(f"{self.provider}: budget cap reached")
        result = self.inner.decide(input, questions, trace_id=trace_id)
        cost = result.envelope.cost.amount
        if cost is None:
            raise RuntimeError("Cannot guard a paid call with unknown cost")
        self.budget.charge(self.provider, cost)
        return result


def questions(dataset):
    labels = [label for label in label_names(dataset) if label != "oos"]
    result = [
        som.Choice("intent", "Which listed intent best matches the request?", {x: x.replace("_", " ") for x in labels})
    ]
    if dataset == "clinc150":
        result.append(
            som.Predicate(
                "fit",
                "Does the request match one of the listed intents?",
                true_means="The request matches a listed intent.",
                false_means="The request does not match a listed intent.",
            )
        )
    return result


def main(mode=None):
    if mode is None:
        parser = argparse.ArgumentParser()
        parser.add_argument("--mode", choices=["record", "replay"], required=True)
        args = parser.parse_args()
    else:
        args = SimpleNamespace(mode=mode)
    budget = Budget({"openai": 45.0, "typesafe": 5.0})
    output = Path("bench/results/e1/pilot")
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    caches = {}
    for dataset in ("banking77",):
        if args.mode == "replay" and not (DATA_DIR / f"{dataset}-test.parquet").exists():
            raise RuntimeError("Pilot replay requires cached data; refusing to download")
        frame = load(dataset, "test").iloc[:50]
        for name, provider, factory in (
            ("typesafe", "typesafe", lambda: som.TypeSafe("jev-1.14.0")),
            ("decisions", "openai", lambda: som.OpenAIDecisions("gpt-6-luna")),
            ("s2", "openai", lambda: som.OpenAIResponses("gpt-6.1-terra", reasoning_effort="low")),
        ):
            cache = JsonCache(f"e1_{name}_{dataset}", mode=args.mode)
            caches[f"{dataset}/{name}"] = cache
            inner_name = {
                "typesafe": "typesafe/jev-1.14.0",
                "decisions": "openai-decisions/gpt-6-luna",
                "s2": "openai/gpt-6.1-terra",
            }[name]
            tier = "s2.reasoning" if name == "s2" else "s1.decision"
            inner = (
                SimpleNamespace(name=inner_name, system=tier)
                if args.mode == "replay"
                else Charged(factory(), budget, provider)
            )
            decider = CachedDecider(inner, cache)
            qs = questions(dataset)

            def measure(item, decider=decider, qs=qs, dataset=dataset, name=name):
                idx, row = item
                decision = decider.decide(row.text, qs)
                env = decision.envelope
                env.validate()
                usage = env.cost.usage
                if env.cost.amount is None or usage is None or env.implementation is None:
                    raise RuntimeError("Pilot returned incomplete accounting")
                return {
                    "dataset": dataset,
                    "item_id": idx,
                    "gold": row.intent,
                    "system": name,
                    "answer": str(decision.answers["intent"].value),
                    "model": env.implementation.model,
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "cached_tokens": usage.cached_tokens,
                    "cost": env.cost.amount,
                    "cost_basis": env.cost.basis,
                    "latency_ms": env.latency_ms,
                }

            with ThreadPoolExecutor(max_workers=4) as executor:
                rows.extend(executor.map(measure, frame.iterrows()))
    raw = pd.DataFrame(rows)
    raw.to_csv(output / "calls.csv", index=False, lineterminator="\n")
    summary = raw.groupby(["dataset", "system"], as_index=False).agg(
        calls=("cost", "size"),
        input_tokens_mean=("input_tokens", "mean"),
        output_tokens_mean=("output_tokens", "mean"),
        cost_mean=("cost", "mean"),
        latency_p50_ms=("latency_ms", "median"),
        latency_p95_ms=("latency_ms", lambda x: x.quantile(0.95)),
    )
    summary.to_csv(output / "summary.csv", index=False, lineterminator="\n")
    projected = {"openai": 0.0, "typesafe": 0.0}
    for row in summary.itertuples():
        count = {
            "banking77": {"typesafe": 4620, "decisions": 4620, "s2": 3580},
            # CLINC's replacement pilot is recorded separately in pilot-v2.
        }[row.dataset][row.system]
        projected["typesafe" if row.system == "typesafe" else "openai"] += count * row.cost_mean
    manifest = {
        "pilot_items_per_dataset": 50,
        "selection": "first 50 test items in dataset order",
        "data_sha256": json.loads((DATA_DIR / "CHECKSUMS.json").read_text()),
        "models": {f"{d}/{s}": str(g.model.iloc[0]) for (d, s), g in raw.groupby(["dataset", "system"])},
        "new_spend_usd": budget.summary(),
        "pilot_total_list_price_usd": float(raw.cost.sum()),
        "projected_full_list_price_usd": projected,
        "caps_usd": budget.caps,
        "cache": {k: {"hits": c.hits, "misses": c.misses} for k, c in caches.items()},
    }
    if args.mode != "replay" or not (output / "manifest.json").exists():
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    (output / "ANALYSIS.md").write_text(
        "# E1 Banking77 pilot\n\n50 paired test items; first 50 in dataset order, not a random or "
        "stratified sample. Option descriptions replace underscores with spaces.\n\n"
        + summary.to_string(index=False)
        + "\n\nProjected Banking77 full list-price spend (including the 500-item S2 calibration subset): "
        + json.dumps(projected)
        + ". Projection extrapolates these unrepresentative pilot calls and is not a spending guarantee. "
        "Costs are usage-weighted list prices, not provider bills. The cap is soft: calls are charged on "
        "completion, so up to one in-flight batch may exceed it. Failed HTTP attempts are assumed not billed.\n"
    )
    print(json.dumps({"projected_full_list_price_usd": projected, "new_spend_usd": budget.summary()}))
    if any(projected[p] > 0.8 * cap for p, cap in budget.caps.items()):
        raise SystemExit("Projected full run exceeds 80% of budget; do not run full experiment")


if __name__ == "__main__":
    main()
