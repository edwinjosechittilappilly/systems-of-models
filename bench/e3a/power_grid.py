"""Compare development-only promotion and conditional audit-detection estimates.

Example: python -m bench.e3a.power_grid --dev-dir bench/results/e3a/dev-tuning-joint
The directory must contain the two S1 audit CSVs and promotion_grid.csv for the
same development run. No evaluation streams are read.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict
from pathlib import Path

from bench.e3a.power import simulate_power
from bench.e3a.tune import measured_effect


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dev-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="JSON output; defaults to DEV-DIR/power_grid.json")
    parser.add_argument("--seed", type=int, default=20261122)
    parser.add_argument("--repetitions", type=int, default=500)
    args = parser.parse_args()

    baseline, effect, coverage, details = measured_effect(args.dev_dir)
    with (args.dev_dir / "promotion_grid.csv").open(newline="") as source:
        promotion = {
            float(row["epsilon"]): row
            for row in csv.DictReader(source)
            if int(row["n_cal"]) == 400 and int(row["n_val"]) == 400 and row["rule"] == "margin"
        }
    rows = []
    for epsilon in (0.10, 0.15, 0.20):
        if epsilon not in promotion:
            raise ValueError(f"missing promotion estimate for epsilon={epsilon}")
        estimate = promotion[epsilon]
        for audit_rate in (0.3, 0.6, 1.0):
            result = simulate_power(
                severity=effect,
                epsilon=epsilon,
                alpha=0.05 / 4,
                baseline_error=baseline,
                coverage=coverage,
                horizon=1200,
                audit_rate=audit_rate,
                seed=args.seed,
                repetitions=args.repetitions,
                pre_shift_horizon=600,
            )
            summary = asdict(result)
            del summary["detection_delays"], summary["audit_detection_delays"]
            promotion_probability = float(estimate["power"])
            rows.append(
                {
                    "epsilon": epsilon,
                    "promotion_successes": int(estimate["successes"]),
                    "promotion_replicates": int(estimate["replicates"]),
                    "promotion_probability": promotion_probability,
                    "promotion_wilson_interval": [
                        float(estimate["power_wilson_low"]),
                        float(estimate["power_wilson_high"]),
                    ],
                    "conditional_detection": summary,
                    "promotion_times_detection": promotion_probability * result.power,
                }
            )
    output = {
        "method": {
            "description": (
                "Development bootstrap promotion estimate multiplied by separately simulated detection "
                "conditional on synthetic successful promotion; not an end-to-end lifecycle estimate."
            ),
            "n_cal": 400,
            "n_val": 400,
            "rule": "margin",
            "alpha": 0.05 / 4,
            "pre_shift_tickets": 600,
            "post_shift_tickets": 1200,
            "seed": args.seed,
            "repetitions": args.repetitions,
            "sources": ["dev_control_s1_audit.csv", "dev_restructure_15_s1_audit.csv", "promotion_grid.csv"],
        },
        "observed": {"baseline_error": baseline, "effect": effect, "coverage": coverage, **details},
        "results": rows,
        "winner": max(rows, key=lambda row: row["promotion_times_detection"]),
    }
    destination = args.output or args.dev_dir / "power_grid.json"
    destination.write_text(json.dumps(output, indent=2) + "\n")
    print(f"Wrote {destination}")


if __name__ == "__main__":
    main()
