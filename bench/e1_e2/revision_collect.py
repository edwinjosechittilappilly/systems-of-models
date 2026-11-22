"""Collect the corrected CLINC predicate and paired teacher decisions."""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
from bench.common.cache import CachedDecider, JsonCache
from bench.e1_e2.collect import ReplayOnly, splits, teacher_subset
from bench.e1_e2.pilot import Charged
from bench.e1_e2.revised import revised_questions
from bench.e1_e2.revision_pilot import namespace

import som


def collect_revised(mode, budget, legacy):
    _, cal, test = splits("clinc150")
    teacher_cal = teacher_subset(cal)
    rows, cache_stats = [], {}
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
        inner_name = {
            "typesafe": "typesafe/jev-1.14.0",
            "decisions": "openai-decisions/gpt-6-luna",
            "s2": "openai/gpt-6.1-terra",
        }[system]
        inner = ReplayOnly(inner_name, tier) if mode == "replay" else Charged(factory(), budget, provider)
        for split, frame in (("calibration", teacher_cal if system == "s2" else cal), ("test", test)):
            cache = JsonCache(namespace(system, split), mode=mode)
            decider = CachedDecider(inner, cache)
            qs = revised_questions(system)
            stripes = [threading.Lock() for _ in range(257)]

            def measure(item, stripes=stripes, decider=decider, qs=qs, system=system, split=split, model=model):
                idx, row = item
                with stripes[hash(row.text) % len(stripes)]:
                    result = decider.decide(row.text, qs)
                env = result.envelope
                env.validate()
                if env.implementation is None or env.implementation.model != model:
                    raise RuntimeError(f"Model drift: expected {model}")
                if env.cost.amount is None:
                    raise RuntimeError("Unknown paid cost")
                fit = result.answers["fit"]
                answer = result.answers.get("intent")
                return {
                    "dataset": "clinc150",
                    "system": system,
                    "split": split,
                    "item_id": int(idx),
                    "gold": row.intent,
                    "answer": answer.value if answer else None,
                    "probabilities": json.dumps(getattr(answer, "probabilities", {}), sort_keys=True),
                    "top_probability": answer.top_probability if answer else None,
                    "confidence": answer.confidence if answer else None,
                    "fit_answer": fit.value,
                    "fit_probability": getattr(fit, "probability", None),
                    "cost": env.cost.amount,
                    "cost_basis": env.cost.basis,
                    "latency_ms": env.latency_ms,
                    "model": model,
                }

            with ThreadPoolExecutor(max_workers=12) as executor:
                rows.extend(executor.map(measure, frame.iterrows()))
            cache_stats[f"clinc150/{system}/{split}/v2"] = {"hits": cache.hits, "misses": cache.misses}
            print(f"Collected corrected clinc150 {system} {split}: {len(frame)} items", flush=True)
    corrected = pd.DataFrame(rows)
    merged = []
    for system in ("typesafe", "decisions"):
        old = legacy[(legacy.dataset == "clinc150") & (legacy.system == system)].copy()
        new = corrected[corrected.system == system].copy()
        combined = old.merge(
            new,
            on=["dataset", "system", "split", "item_id", "gold", "model"],
            suffixes=("_choice", "_fit"),
            validate="one_to_one",
        )
        if len(combined) != len(old) or len(combined) != len(new):
            raise RuntimeError("Corrected fit results do not pair with legacy choices")
        merged.append(
            pd.DataFrame(
                {
                    "dataset": combined.dataset,
                    "system": combined.system,
                    "split": combined.split,
                    "item_id": combined.item_id,
                    "gold": combined.gold,
                    "model": combined.model,
                    "choice_call_variant": combined.choice_call_variant,
                    "answer": combined.answer_choice,
                    "probabilities": combined.probabilities_choice,
                    "top_probability": combined.top_probability_choice,
                    "confidence": combined.confidence_choice,
                    "fit_answer": combined.fit_answer_fit,
                    "fit_probability": combined.fit_probability_fit,
                    "cost": combined.cost_choice + combined.cost_fit,
                    "cost_basis": combined.cost_basis_choice.where(
                        combined.cost_basis_choice == combined.cost_basis_fit, "unknown"
                    ),
                    "latency_ms": combined.latency_ms_choice + combined.latency_ms_fit,
                    "choice_cost": combined.cost_choice,
                    "fit_cost": combined.cost_fit,
                    "choice_latency_ms": combined.latency_ms_choice,
                    "fit_latency_ms": combined.latency_ms_fit,
                }
            )
        )
    return pd.concat(
        [legacy[legacy.dataset != "clinc150"], *merged, corrected[corrected.system == "s2"]], ignore_index=True
    ), cache_stats
