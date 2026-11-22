import pandas as pd
import pytest

from bench.e3a.hypotheses import evaluate


def test_paired_hypotheses_use_ticket_permutation_and_report_seed_consistency():
    rows = []
    for seed in (11, 23, 37):
        for index in range(600, 1200):
            for arm in ("always_agent", "s1_audit"):
                rows.append(
                    {
                        "stream": f"seed_{seed}_control",
                        "ticket_index": index,
                        "arm": arm,
                        "gold_joint_correct": True,
                        "cost_usd": 1.0,
                    }
                )
        for severity in (15, 30):
            for index in range(1200, 2400):
                for arm in ("s1_audit", "s1_refit", "escalation_only"):
                    rows.append(
                        {
                            "stream": f"seed_{seed}_restructure_{severity}",
                            "ticket_index": index,
                            "arm": arm,
                            "gold_joint_correct": arm == "s1_audit",
                            "cost_usd": 1.0,
                        }
                    )
    h3, h4 = evaluate(pd.DataFrame(rows), cost_bound_percent=100, resamples=50)
    assert h3[0]["noninferior_and_cost_pass"]
    assert all(row["mean_audit_advantage"] == 1200 for row in h4)
    assert all(row["ticket_permutation_one_sided_p"] == pytest.approx(1 / 51) for row in h4)
    assert all(row["holm_p_within_severity"] == pytest.approx(2 / 51) for row in h4)
    assert all(row["all_seed_effects_positive"] for row in h4)


def test_missing_paired_stream_is_an_error():
    empty = pd.DataFrame(columns=["stream", "ticket_index", "arm"])
    with pytest.raises(ValueError, match="unpaired or missing"):
        evaluate(empty, cost_bound_percent=50)
