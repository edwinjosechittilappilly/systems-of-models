"""Paired, seed-aware E3a evaluation statistics; never tune on these outputs."""

from __future__ import annotations

import itertools
from typing import Any

import numpy as np
import pandas as pd


def _paired(table: pd.DataFrame, stream: str, arm: str, reference: str) -> pd.DataFrame:
    part = table.loc[table["stream"] == stream]
    left = part.loc[part["arm"] == arm].set_index("ticket_index")
    right = part.loc[part["arm"] == reference].set_index("ticket_index")
    if left.empty or not left.index.equals(right.index):
        raise ValueError(f"unpaired or missing arm: {stream}/{arm}/{reference}")
    return left.merge(right, left_index=True, right_index=True, suffixes=("_arm", "_ref"))


def evaluate(
    table: pd.DataFrame, *, cost_bound_percent: float, seed: int = 20261122, resamples: int = 2000
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """H3/H4 paired intervals and Holm-adjusted exact seed-level randomization p-values.

    Resampling for H3 is stratified over seeds and samples tickets within each
    seed. H4 bootstraps the three paired per-seed cumulative-error contrasts;
    exact sign flips expose the severe resolution limit from only three seeds.
    """
    if resamples < 1 or cost_bound_percent <= 0:
        raise ValueError("resamples and cost bound must be positive")
    rng = np.random.default_rng(seed)
    pre = []
    cost_arm = cost_ref = 0.0
    for stream_seed in (11, 23, 37):
        data = _paired(table, f"seed_{stream_seed}_control", "s1_audit", "always_agent")
        data = data[(data.index >= 600) & (data.index < 1200)]
        if len(data) != 600:
            raise ValueError(f"incomplete H3 pre-shift window: seed {stream_seed}")
        pre.append(
            data["gold_joint_correct_ref"].astype(float).to_numpy()
            - data["gold_joint_correct_arm"].astype(float).to_numpy()
        )
        cost_arm += data["cost_usd_arm"].sum()
        cost_ref += data["cost_usd_ref"].sum()
    loss = float(np.concatenate(pre).mean())
    draws = np.array(
        [np.concatenate([part[rng.integers(0, len(part), len(part))] for part in pre]).mean() for _ in range(resamples)]
    )
    upper = float(np.quantile(draws, 0.95))
    ratio = 100 * cost_arm / cost_ref
    h3 = [
        {
            "hypothesis": "H3",
            "paired_accuracy_loss": loss,
            "upper_one_sided_95": upper,
            "margin": 0.02,
            "cost_percent": ratio,
            "cost_bound_percent": cost_bound_percent,
            "noninferior_and_cost_pass": upper < 0.02 and ratio <= cost_bound_percent,
            "resamples": resamples,
        }
    ]
    h4 = []
    for severity in (15, 30):
        comparisons = []
        for other in ("s1_refit", "escalation_only"):
            contrasts = []
            for stream_seed in (11, 23, 37):
                stream = f"seed_{stream_seed}_restructure_{severity}"
                data = _paired(table, stream, "s1_audit", other)
                data = data[(data.index >= 1200) & (data.index < 2400)]
                if len(data) != 1200:
                    raise ValueError(f"incomplete H4 post-shift window: {stream}")
                # Lower error in audit arm gives a positive advantage.
                contrasts.append(
                    float(
                        (
                            data["gold_joint_correct_arm"].astype(float) - data["gold_joint_correct_ref"].astype(float)
                        ).sum()
                    )
                )
            values = np.array(contrasts)
            point = float(values.mean())
            boot = np.array([values[rng.integers(0, len(values), len(values))].mean() for _ in range(resamples)])
            lo, hi = np.quantile(boot, [0.025, 0.975])
            flips = [float(np.mean(values * signs)) for signs in itertools.product((-1, 1), repeat=len(values))]
            p = sum(value >= point - 1e-12 for value in flips) / len(flips)
            comparisons.append(
                {
                    "hypothesis": "H4",
                    "severity": severity,
                    "comparison": other,
                    "mean_audit_advantage": point,
                    "ci_low": float(lo),
                    "ci_high": float(hi),
                    "exact_one_sided_p": p,
                    "per_seed_advantages": contrasts,
                }
            )
        order = sorted(range(len(comparisons)), key=lambda i: comparisons[i]["exact_one_sided_p"])
        running = 0.0
        for rank, index in enumerate(order):
            running = max(running, min(1.0, (len(order) - rank) * comparisons[index]["exact_one_sided_p"]))
            comparisons[index]["holm_p_within_severity"] = running
        h4.extend(comparisons)
    return h3, h4
