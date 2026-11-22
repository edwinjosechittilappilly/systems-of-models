"""Collect paid E1/E2 decisions using the pilot's exact question and cache keys."""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
from bench.common.budget import Budget
from bench.common.cache import CACHE_DIR, CachedDecider, CacheMiss, JsonCache
from bench.common.data import load
from bench.e1_e2.pilot import Charged, questions

import som

CAPS = {"openai": 60.0, "typesafe": 5.0}


def splits(dataset):
    train = load(dataset, "train")
    if dataset == "banking77":
        groups = [group.sample(n=20, random_state=0) for _, group in train.groupby("intent", sort=True)]
        cal = pd.concat(groups).sample(frac=1, random_state=0)
        remaining = train.drop(cal.index)
        cal = cal.reset_index(drop=True)
    else:
        cal = load(dataset, "validation")
        remaining = train
    test = load(dataset, "test")
    return remaining, cal, test


def teacher_subset(cal):
    """500 calibration items, proportional stratification including OOS, seed 0."""
    counts = cal.groupby("intent", sort=True).size()
    quotas = counts * (500 / len(cal))
    allocations = np.floor(quotas).astype(int)
    remainder = 500 - int(allocations.sum())
    for label in (quotas - allocations).sort_values(ascending=False, kind="stable").index[:remainder]:
        allocations[label] += 1
    parts = [
        group.sample(n=int(allocations[label]), random_state=0) for label, group in cal.groupby("intent", sort=True)
    ]
    return pd.concat(parts).sort_index()


class ReplayOnly:
    def __init__(self, name, system):
        self.name, self.system = name, system

    def decide(self, *args, **kwargs):
        raise RuntimeError("Replay attempted a network call")


def collect(mode):
    pilot = json.loads(Path("bench/results/e1/pilot/manifest.json").read_text())
    if any(pilot["projected_full_list_price_usd"][provider] > 0.8 * cap for provider, cap in CAPS.items()):
        raise RuntimeError("Pilot projection exceeds 80% of cap")
    revised_pilot = json.loads(Path("bench/results/e1/pilot-v2/manifest.json").read_text())
    if not revised_pilot["full_run_go"]:
        raise RuntimeError("Corrected CLINC pilot projection exceeds 80% of cap")
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
                        raise RuntimeError("Cached paid call has unknown cost")
                    budget.charge(provider, amount)
    previous = budget.summary()
    all_rows, cache_stats = [], {}
    for dataset in ("banking77", "clinc150"):
        _, cal, test = splits(dataset)
        subset = teacher_subset(cal)
        for system, provider, model, tier, factory in (
            ("typesafe", "typesafe", "jev-1.14.0", "s1.decision", lambda: som.TypeSafe("jev-1.14.0")),
            ("decisions", "openai", "gpt-6-luna", "s1.decision", lambda: som.OpenAIDecisions("gpt-6-luna")),
            (
                "s2",
                "openai",
                "gpt-6.1-terra",
                "s2.reasoning",
                lambda: som.OpenAIResponses("gpt-6.1-terra", reasoning_effort="low"),
            ),
        ):
            if dataset == "clinc150" and system == "s2":
                continue
            inner_name = {
                "typesafe": "typesafe/jev-1.14.0",
                "decisions": "openai-decisions/gpt-6-luna",
                "s2": "openai/gpt-6.1-terra",
            }[system]
            inner = ReplayOnly(inner_name, tier) if mode == "replay" else Charged(factory(), budget, provider)
            for split, frame in (("calibration", subset if system == "s2" else cal), ("test", test)):
                namespace = (
                    f"e1_s2_cal_{dataset}" if system == "s2" and split == "calibration" else f"e1_{system}_{dataset}"
                )
                cache = JsonCache(namespace, mode="replay" if dataset == "clinc150" else mode)
                decider = CachedDecider(inner, cache)
                qs = questions(dataset)
                choice_cache = (
                    JsonCache(f"e1_{system}_clinc150_choice_v2", mode=mode) if dataset == "clinc150" else None
                )
                alternative = CachedDecider(inner, choice_cache) if choice_cache is not None else None
                # Serialize identical text to prevent the shared cache issuing duplicate paid calls.
                stripes = [threading.Lock() for _ in range(257)]

                def measure(
                    item,
                    stripes=stripes,
                    decider=decider,
                    qs=qs,
                    model=model,
                    dataset=dataset,
                    split=split,
                    system=system,
                    alternative=alternative,
                ):
                    idx, row = item
                    with stripes[hash(row.text) % len(stripes)]:
                        try:
                            decision = decider.decide(row.text, qs)
                            choice_variant = "legacy_bundled" if dataset == "clinc150" else None
                        except CacheMiss:
                            if alternative is None:
                                raise
                            decision = alternative.decide(row.text, qs[:1])
                            choice_variant = "choice_only"
                    env = decision.envelope
                    env.validate()
                    if env.implementation is None or env.implementation.model != model:
                        raise RuntimeError(f"Model drift: expected {model}")
                    answer = decision.answers["intent"]
                    fit = decision.answers.get("fit")
                    return {
                        "dataset": dataset,
                        "split": split,
                        "item_id": int(idx),
                        "gold": row.intent,
                        "system": system,
                        "answer": answer.value,
                        "probabilities": json.dumps(getattr(answer, "probabilities", {}), sort_keys=True),
                        "top_probability": answer.top_probability,
                        "confidence": answer.confidence,
                        "fit_answer": fit.value if fit else None,
                        "fit_probability": getattr(fit, "probability", None),
                        "cost": env.cost.amount,
                        "cost_basis": env.cost.basis,
                        "latency_ms": env.latency_ms,
                        "model": env.implementation.model,
                        "choice_call_variant": choice_variant,
                    }

                with ThreadPoolExecutor(max_workers=12) as executor:
                    all_rows.extend(executor.map(measure, frame.iterrows()))
                cache_stats[f"{dataset}/{system}/{split}"] = {"hits": cache.hits, "misses": cache.misses}
                if choice_cache is not None:
                    cache_stats[f"{dataset}/{system}/{split}/choice_only"] = {
                        "hits": choice_cache.hits,
                        "misses": choice_cache.misses,
                    }
                print(f"Collected {dataset} {system} {split}: {len(frame)} items", flush=True)
    from bench.e1_e2.revision_collect import collect_revised

    combined, revised_stats = collect_revised(mode, budget, pd.DataFrame(all_rows))
    cache_stats.update(revised_stats)
    accounted = budget.summary()
    new_spend = {provider: round(accounted.get(provider, 0) - previous.get(provider, 0), 6) for provider in CAPS}
    return combined, {"new_spend_usd": new_spend, "cache_accounted_spend_usd": accounted}, cache_stats
