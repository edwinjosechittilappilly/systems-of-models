"""Paired, seed-aware E3a evaluation statistics; never tune on these outputs."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _paired(table: pd.DataFrame, stream: str, arm: str, reference: str) -> pd.DataFrame:
    part = table.loc[table["stream"] == stream]
    left = part.loc[part["arm"] == arm].set_index("ticket_index").sort_index()
    right = part.loc[part["arm"] == reference].set_index("ticket_index").sort_index()
    if left.empty or not left.index.is_unique or not right.index.is_unique or not left.index.equals(right.index):
        raise ValueError(f"unpaired or missing arm: {stream}/{arm}/{reference}")
    return left.merge(right, left_index=True, right_index=True, suffixes=("_arm", "_ref"))


def evaluate(
    table: pd.DataFrame, *, seed: int = 20261122, resamples: int = 2000
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """H3/H4 ticket-paired intervals and Holm-adjusted randomization p-values.

    H3 uses all control tickets 1200–2399, including escalations, for its
    primary accuracy-only noninferiority test. The compiled-served subset is
    descriptive. Samples and sign flips are stratified by seed. H4's unit is a ticket;
    seed-wise effects and their sign consistency are reported separately. An
    exact one-sided seed sign-flip test has minimum p=1/8 for three seeds,
    so it cannot establish significance at 0.05 even before Holm correction.
    """
    if resamples < 1:
        raise ValueError("resamples must be positive")
    rng = np.random.default_rng(seed)
    losses = []
    served_arm = []
    served_ref = []
    for stream_seed in (11, 23, 37):
        data = _paired(table, f"seed_{stream_seed}_control", "s1_audit", "always_agent")
        data = data[(data.index >= 1200) & (data.index < 2400)]
        if len(data) != 1200:
            raise ValueError(f"incomplete H3 post-shift window: seed {stream_seed}")
        arm = data["gold_joint_correct_arm"].astype(float)
        ref = data["gold_joint_correct_ref"].astype(float)
        losses.append((ref - arm).to_numpy())
        served = data["served_by_arm"].ne("agent")
        served_arm.extend(arm[served])
        served_ref.extend(ref[served])
    loss = float(np.concatenate(losses).mean())
    draws = np.array(
        [np.concatenate([part[rng.integers(0, len(part), len(part))] for part in losses]).mean() for _ in range(resamples)]
    )
    upper = float(np.quantile(draws, 0.95))
    h3 = [
        {
            "hypothesis": "H3",
            "paired_accuracy_loss": loss,
            "upper_one_sided_95": upper,
            "margin": 0.02,
            "noninferior": upper < 0.02,
            "served_count": len(served_arm),
            "served_arm_accuracy": float(np.mean(served_arm)) if served_arm else None,
            "served_reference_accuracy": float(np.mean(served_ref)) if served_ref else None,
            "served_paired_accuracy_loss": float(np.mean(np.subtract(served_ref, served_arm))) if served_arm else None,
            "resamples": resamples,
        }
    ]
    h4 = []
    for severity in (15,):
        comparisons = []
        for other in ("s1_refit", "escalation_only"):
            differences = []
            for stream_seed in (11, 23, 37):
                stream = f"seed_{stream_seed}_restructure_{severity}"
                data = _paired(table, stream, "s1_audit", other)
                data = data[(data.index >= 1200) & (data.index < 2400)]
                if len(data) != 1200:
                    raise ValueError(f"incomplete H4 post-shift window: {stream}")
                # Lower error in audit arm gives a positive advantage.
                differences.append(
                    data["gold_joint_correct_arm"].astype(float).to_numpy()
                    - data["gold_joint_correct_ref"].astype(float).to_numpy()
                )
            values = np.stack(differences)
            contrasts = values.sum(axis=1)
            point = float(contrasts.mean())
            boot = np.array(
                [
                    np.mean([part[rng.integers(0, len(part), len(part))].sum() for part in values])
                    for _ in range(resamples)
                ]
            )
            lo, hi = np.quantile(boot, [0.025, 0.975])
            permutations = np.array(
                [float((values * rng.choice((-1, 1), size=values.shape)).sum(axis=1).mean()) for _ in range(resamples)]
            )
            p = (1 + int(np.sum(permutations >= point - 1e-12))) / (resamples + 1)
            comparisons.append(
                {
                    "hypothesis": "H4",
                    "severity": severity,
                    "comparison": other,
                    "mean_audit_advantage": point,
                    "ci_low": float(lo),
                    "ci_high": float(hi),
                    "ticket_permutation_one_sided_p": p,
                    "per_seed_advantages": contrasts.tolist(),
                    "all_seed_effects_positive": bool(np.all(contrasts > 0)),
                }
            )
        order = sorted(range(len(comparisons)), key=lambda i: comparisons[i]["ticket_permutation_one_sided_p"])
        running = 0.0
        for rank, index in enumerate(order):
            running = max(running, min(1.0, (len(order) - rank) * comparisons[index]["ticket_permutation_one_sided_p"]))
            comparisons[index]["holm_p_within_severity"] = running
        h4.extend(comparisons)
    return h3, h4
