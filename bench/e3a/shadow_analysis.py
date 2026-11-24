"""Analyze first-generation development shadow scores without model calls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import beta

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEV_DIR = ROOT / "results/e3a/dev-tuning-joint"
LEGACY_SHADOW = ROOT / "results/e3a/dev-tuning/shadow_observations.csv"


def upper(errors: int, n: int, alpha: float = 0.0125) -> float:
    if n == 0 or errors == n:
        return 1.0
    return float(beta.ppf(1 - alpha, errors + 1, n - errors))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev-dir", type=Path, default=DEFAULT_DEV_DIR)
    args = parser.parse_args()
    out = args.dev_dir
    rows = pd.read_csv(out / "dev_control_s1_audit.csv")
    config = json.loads((out / "manifest.json").read_text())["config"]
    if config["streams"] != "dev":
        raise ValueError("shadow analysis accepts development runs only")
    if "predicted_entry_probability" not in rows:
        if out.resolve() != DEFAULT_DEV_DIR.resolve():
            raise ValueError("run lacks predicted_entry_probability; cannot match S1 cache safely")
        # The original Terra bootstrap used this separately recorded historical
        # shadow table. Never reuse it for a different teacher or development run.
        data = pd.read_csv(LEGACY_SHADOW)
        print(f"Using historical Terra shadow observations from {LEGACY_SHADOW}")
    else:
        frame = pd.read_csv(ROOT / "tasks/streams/dev_control.csv")
        shift = len(frame) // 2
        rows = rows[(rows.ticket_index >= config["warmup"]) & (rows.ticket_index < shift)]
        compiled = rows.loc[rows.compile_status == "compiled", "ticket_index"].sort_values()
        if compiled.empty:
            raise ValueError("development run has no successful S1 compilation before shift")
        start = int(compiled.iloc[0])
        end = int(compiled.iloc[1]) if len(compiled) > 1 else shift
        rows = rows[(rows.ticket_index >= start) & (rows.ticket_index < end)]
        rows = rows.dropna(subset=["predicted_entry_probability", "joint_decision_agreement"])
        rows = rows.head(config["n_cal"] + config["n_val"])
        if rows.empty:
            raise ValueError("first generation has no joint-labeled S1 scores")
        data = pd.DataFrame(
            {
                "ticket_index": rows.ticket_index,
                "decision": "D1",
                "score": rows.predicted_entry_probability,
                "error": ~rows.joint_decision_agreement.astype(bool),
            }
        )
    data.to_csv(out / "shadow_observations.csv", index=False, lineterminator="\n")
    grid = []
    rng = np.random.default_rng(20261122)
    for decision, group in data.groupby("decision"):
        scores = group.score.to_numpy()
        errors = group.error.to_numpy(dtype=bool)
        for tau in np.arange(0.50, 1.001, 0.05):
            eligible = scores >= tau - 1e-10
            n = int(eligible.sum())
            k = int(errors[eligible].sum())
            result = {
                "decision": decision,
                "tau": round(float(tau), 2),
                "total": len(group),
                "selected": n,
                "coverage": n / len(group),
                "errors": k,
                "selective_error": k / n if n else np.nan,
                "cp_upper_actual": upper(k, n),
            }
            for window in (300, 500, 1000):
                draws = rng.integers(0, len(group), size=(500, window))
                picked = eligible[draws]
                counts = picked.sum(axis=1)
                mistakes = (errors[draws] & picked).sum(axis=1)
                bounds = [upper(int(a), int(b)) for a, b in zip(mistakes, counts, strict=True)]
                result[f"bootstrap_median_cp_n{window}"] = float(np.median(bounds))
                for epsilon in (0.10, 0.15, 0.20):
                    result[f"bootstrap_val_pass_n{window}_eps{epsilon:.2f}"] = float(
                        np.mean(np.asarray(bounds) <= epsilon)
                    )
            grid.append(result)
    table = pd.DataFrame(grid)
    table.to_csv(out / "shadow_risk_coverage.csv", index=False, lineterminator="\n")
    plt.style.use(ROOT / "ieee.mplstyle")
    fig, ax = plt.subplots(figsize=(3.5, 2.5))
    for decision, group in table.groupby("decision"):
        ax.plot(group.coverage, group.selective_error, marker="o", label=decision)
    ax.set(xlabel="Coverage", ylabel="Teacher disagreement")
    ax.legend()
    fig.savefig(out / "shadow_risk_coverage.pdf", bbox_inches="tight")
    fig.savefig(out / "shadow_risk_coverage.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    groups = list(table.groupby("decision"))
    fig, axes = plt.subplots(1, len(groups), figsize=(3.5 * len(groups), 2.5), sharey=True, squeeze=False)
    for ax, (decision, group) in zip(axes[0], groups, strict=True):
        for window in (300, 500, 1000):
            ax.plot(group.tau, group[f"bootstrap_median_cp_n{window}"], label=f"n={window}")
        ax.set(title=decision, xlabel="Threshold", ylim=(0, 1))
    axes[0, 0].set_ylabel("Bootstrap median CP upper bound")
    axes[0, -1].legend()
    fig.savefig(out / "shadow_cp_windows.pdf", bbox_inches="tight")
    fig.savefig(out / "shadow_cp_windows.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"joined={len(data)}")
    print(table.to_string(index=False))


if __name__ == "__main__":
    main()
