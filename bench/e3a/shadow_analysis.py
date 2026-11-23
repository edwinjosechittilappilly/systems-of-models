"""Analyze the first dev-control shadow generation without making model calls."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from bench.common.cache import answer_from_dict
from bench.e3a.collect import items_for_stream
from scipy.stats import beta

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/e3a/dev-tuning"


def upper(errors: int, n: int, alpha: float = 0.0125) -> float:
    if n == 0 or errors == n:
        return 1.0
    return float(beta.ppf(1 - alpha, errors + 1, n - errors))


def main() -> None:
    frame = pd.read_csv(ROOT / "tasks/streams/dev_control.csv")
    items, _ = items_for_stream(frame, phase_limit=1000)
    inputs = {item["index"]: item["text"] for item in items}
    rows = pd.read_csv(OUT / "dev_control_s1_audit.csv")
    rows = rows.loc[rows.ticket_index.between(300, 899)]
    wanted = {inputs[i] for i in rows.ticket_index}
    names = {"customer_support_intent": "D1", "verify_identity": "D2"}
    observations: dict[tuple[str, str], list[tuple[object, float]]] = {}
    with (ROOT / "cache/e3a_s1_jev.jsonl").open() as handle:
        for line in handle:
            entry = json.loads(line)
            request = entry["request"]
            text = request["input"]
            if text not in wanted:
                continue
            for name, raw in entry["response"]["answers"].items():
                if name not in names:
                    continue
                answer = answer_from_dict(raw)
                if answer.top_probability is not None:
                    observations.setdefault((text, names[name]), []).append((answer.value, answer.top_probability))
    records = []
    ambiguous = 0
    for row in rows.itertuples(index=False):
        for decision, prediction, correct in (
            ("D1", row.predicted_entry, row.d1_teacher_agreement),
            ("D2", row.predicted_verify, row.predicted_verify == row.verified),
        ):
            if pd.isna(prediction) or pd.isna(correct):
                continue
            candidates = {
                (value, round(float(score), 12))
                for value, score in observations.get((inputs[row.ticket_index], decision), [])
                if value == prediction
            }
            if len(candidates) != 1:
                ambiguous += 1
                continue
            records.append(
                {
                    "ticket_index": row.ticket_index,
                    "decision": decision,
                    "score": candidates.pop()[1],
                    "error": not bool(correct),
                }
            )
    data = pd.DataFrame(records)
    data.to_csv(OUT / "shadow_observations.csv", index=False)
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
    table.to_csv(OUT / "shadow_risk_coverage.csv", index=False)
    plt.style.use(ROOT / "ieee.mplstyle")
    fig, ax = plt.subplots(figsize=(3.5, 2.5))
    for decision, group in table.groupby("decision"):
        ax.plot(group.coverage, group.selective_error, marker="o", label=decision)
    ax.set(xlabel="Coverage", ylabel="Teacher disagreement")
    ax.legend()
    fig.savefig(OUT / "shadow_risk_coverage.pdf", bbox_inches="tight")
    fig.savefig(OUT / "shadow_risk_coverage.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"joined={len(data)} ambiguous_or_missing={ambiguous}")
    print(table.to_string(index=False))


if __name__ == "__main__":
    main()
