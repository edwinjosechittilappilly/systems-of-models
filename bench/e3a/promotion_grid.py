"""Bootstrap development shadow pairs through the actual promotion rule."""

from __future__ import annotations

import numpy as np
import pandas as pd
from bench.common.stats import wilson
from bench.e3a.shadow_analysis import OUT
from scipy.stats import beta


def cp_bounds(errors, counts, alpha):
    result = np.ones(len(counts), dtype=float)
    mask = (counts > 0) & (errors < counts)
    result[mask] = beta.ppf(1 - alpha, errors[mask] + 1, counts[mask] - errors[mask])
    return result


def promote(scores, errors, n, epsilon, rule):
    """Apply CompiledDecision's threshold-selection and independent validation rules."""
    cs, ce = scores[:n], errors[:n]
    thresholds = np.r_[0.0, np.nextafter(np.unique(cs[cs < 1]), np.inf)]
    selected = cs[None, :] >= thresholds[:, None]
    counts = selected.sum(axis=1)
    mistakes = (selected & ce).sum(axis=1)
    if rule == "margin":
        ok = (counts > 0) & (mistakes <= 0.6 * epsilon * counts)
    else:
        ok = (counts > 0) & (cp_bounds(mistakes, counts, 0.05) <= epsilon)
    if not ok.any():
        return False
    threshold = thresholds[np.flatnonzero(ok)[0]]
    selected_val = scores[n:] >= threshold
    count = int(selected_val.sum())
    mistakes = int((errors[n:] & selected_val).sum())
    return bool(count and cp_bounds(np.array([mistakes]), np.array([count]), 0.0125)[0] <= epsilon)


def main():
    shadow = pd.read_csv(OUT / "shadow_observations.csv")
    shadow = shadow[shadow.decision == "D1"]
    joint = pd.read_csv(OUT.parent / "dev-tuning-joint/dev_control_s1_audit.csv")
    joined = joint.merge(shadow[["ticket_index", "score"]], on="ticket_index")
    joined = joined[joined.joint_decision_agreement.notna()]
    scores = joined.score.to_numpy(dtype=float)
    errors = ~joined.joint_decision_agreement.to_numpy(dtype=bool)
    rng = np.random.default_rng(20261122)
    rows = []
    for epsilon in (0.10, 0.15, 0.20):
        for n in (250, 400, 500):
            draws = rng.integers(0, len(scores), size=(500, 2 * n))
            for rule in ("margin", "upper_bound"):
                successes = sum(promote(scores[d], errors[d], n, epsilon, rule) for d in draws)
                low, high = wilson(successes, len(draws))
                rows.append(
                    {
                        "epsilon": epsilon,
                        "n_cal": n,
                        "n_val": n,
                        "rule": rule,
                        "successes": successes,
                        "replicates": len(draws),
                        "power": successes / len(draws),
                        "power_wilson_low": low,
                        "power_wilson_high": high,
                        "fits_preshift": 300 + 2 * n <= 1200,
                        "joined_shadow": len(joined),
                    }
                )
    result = pd.DataFrame(rows)
    result.to_csv(OUT.parent / "dev-tuning-joint/promotion_grid.csv", index=False)
    print(result.to_string(index=False))


if __name__ == "__main__":
    main()
