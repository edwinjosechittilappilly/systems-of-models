"""Run E1/E2; replay refuses network and requires the archived response and data caches."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from bench.common.data import DATA_DIR
from bench.common.stats import aurc, brier, ece, nll
from bench.e1_e2.analysis import analyse, with_signals
from bench.e1_e2.collect import collect, splits
from bench.e1_e2.metrics import choose_threshold
from bench.e1_e2.pilot import main as replay_banking_pilot
from bench.e1_e2.revision_pilot import main as replay_clinc_pilot
from bench.e1_e2.surrogate import fit_predict


def baseline(mode, raw):
    rows, summaries, sweeps = [], [], []
    for dataset in ("banking77", "clinc150"):
        classes, cal_prob, test_prob, accounting = fit_predict(dataset, mode=mode)
        _, cal, test = splits(dataset)
        subset = raw[(raw.dataset == dataset) & (raw.system == "s2")]
        teacher_cal = with_signals(subset[subset.split == "calibration"])
        teacher_test = with_signals(subset[subset.split == "test"]).sort_values("item_id")
        s2_correct = teacher_test.correct.to_numpy(bool)
        for metric in ("top_probability", "margin"):

            def signal(p, metric=metric):
                ordered = np.sort(p, axis=1)
                return ordered[:, -1] if metric == "top_probability" else ordered[:, -1] - ordered[:, -2]

            cal_signal, test_signal = signal(cal_prob), signal(test_prob)
            cal_correct = classes[cal_prob.argmax(axis=1)] == cal.intent.to_numpy()
            test_correct = classes[test_prob.argmax(axis=1)] == test.intent.to_numpy()
            grid = np.unique(cal_signal)
            tau, coverage, fallback = choose_threshold(cal_signal, cal_correct, teacher_cal.correct.mean(), grid)
            for value in grid:
                escalate = test_signal < value
                sweeps.append(
                    {
                        "dataset": dataset,
                        "system": "surrogate",
                        "metric": metric,
                        "tau": value,
                        "accuracy": float(np.where(escalate, s2_correct, test_correct).mean()),
                        "escalation_rate": float(escalate.mean()),
                        "local_cost_usd": None,
                        "s2_cost_lower_bound_usd": float(np.mean(np.where(escalate, teacher_test.cost, 0))),
                        "selected_tau": tau,
                        "selected_calibration_coverage": coverage,
                        "fallback_always_escalate": fallback,
                    }
                )
        for split, frame, probabilities in (("calibration", cal, cal_prob), ("test", test, test_prob)):
            indexes = probabilities.argmax(axis=1)
            pred = classes[indexes]
            correct = pred == frame.intent.to_numpy()
            lookup = {label: idx for idx, label in enumerate(classes)}
            labels = np.array([lookup.get(label, -1) for label in frame.intent], dtype=int)
            valid = labels >= 0
            conf = probabilities.max(axis=1)
            summaries.append(
                {
                    "dataset": dataset,
                    "split": split,
                    "n": len(frame),
                    "accuracy": float(correct.mean()),
                    "ece": ece(conf, correct),
                    "brier": brier(probabilities[valid], labels[valid]),
                    "nll": nll(probabilities[valid], labels[valid]),
                    "aurc": aurc(conf, correct),
                    "unknown_gold_classes": int((~valid).sum()),
                    **accounting,
                }
            )
            rows.extend(
                {
                    "dataset": dataset,
                    "split": split,
                    "item_id": int(i),
                    "gold": gold,
                    "prediction": answer,
                    "top_probability": float(probability),
                }
                for i, gold, answer, probability in zip(frame.index, frame.intent, pred, conf, strict=True)
            )
    root = Path("bench/results/e1/full")
    pd.DataFrame(rows).to_csv(
        root / "supervised_items.csv.gz", index=False, lineterminator="\n", compression={"method": "gzip", "mtime": 0}
    )
    pd.DataFrame(summaries).to_csv(root / "supervised_summary.csv", index=False, lineterminator="\n")
    for (dataset, metric), group in pd.DataFrame(sweeps).groupby(["dataset", "metric"]):
        group.to_csv(root / f"supervised_sweep_{dataset}_{metric}.csv", index=False, lineterminator="\n")
    with (root / "ANALYSIS.md").open("a") as handle:
        handle.write(
            "\n\n## Supervised embedding ceiling\n\n"
            + pd.DataFrame(summaries).to_string(index=False)
            + "\n\nThe classifier is trained on train data excluding Banking77 calibration; "
            "CLINC uses its train split. "
            "Embedding wall seconds are recorded, not embedding CPU seconds; classifier CPU and wall time "
            "are measured separately. Local monetary cost and per-request latency are unknown, so no "
            "zero-cost surrogate cascade is inferred.\n"
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["record", "replay"], required=True)
    args = parser.parse_args()
    if args.mode == "replay":
        needed = [
            DATA_DIR / f"{dataset}-{split}.parquet"
            for dataset, split in (
                ("banking77", "train"),
                ("banking77", "test"),
                ("clinc150", "train"),
                ("clinc150", "validation"),
                ("clinc150", "test"),
            )
        ]
        if not all(path.exists() for path in needed):
            raise RuntimeError("Replay requires all five cached data files; refusing to download")
        replay_banking_pilot("replay")
        replay_clinc_pilot("replay")
    raw, budget, stats = collect(args.mode)
    analyse(raw, budget, stats, mode=args.mode)
    baseline(args.mode, raw)
    print(json.dumps({"items": len(raw), "accounted_spend_usd": budget}))


if __name__ == "__main__":
    main()
