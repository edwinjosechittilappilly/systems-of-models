import pandas as pd
import pytest

from bench.e3a.hypotheses import evaluate


def test_paired_hypotheses_use_ticket_permutation_and_report_seed_consistency():
    rows = []
    for seed in (11, 23, 37):
        for index in range(600, 2400):
            for arm in ("always_agent", "s1_audit"):
                rows.append(
                    {
                        "stream": f"seed_{seed}_control",
                        "ticket_index": index,
                        "arm": arm,
                        "gold_joint_correct": index >= 1200 or arm == "always_agent",
                        "served_by": "s1" if arm == "s1_audit" and index % 2 == 0 else "agent",
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
    table = pd.DataFrame(rows).sample(frac=1, random_state=17)
    h3, h4 = evaluate(table, resamples=50)
    assert h3[0]["noninferior"]
    assert h3[0]["paired_accuracy_loss"] == 0
    assert h3[0]["served_count"] == 1800
    assert h3[0]["served_arm_accuracy"] == 1
    assert h3[0]["served_reference_accuracy"] == 1
    assert all(row["mean_audit_advantage"] == 1200 for row in h4)
    assert all(row["ticket_permutation_one_sided_p"] == pytest.approx(1 / 51) for row in h4)
    assert all(row["holm_p_within_severity"] == pytest.approx(2 / 51) for row in h4)
    assert all(row["all_seed_effects_positive"] for row in h4)
    duplicate = pd.concat([table, table.loc[table["stream"] == "seed_11_control"].iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="unpaired or missing"):
        evaluate(duplicate, resamples=1)

    seed_37 = table["stream"] == "seed_37_restructure_15"
    table.loc[seed_37 & (table["arm"] == "s1_audit"), "gold_joint_correct"] = False
    table.loc[seed_37 & (table["arm"] == "s1_refit"), "gold_joint_correct"] = True
    _, mixed = evaluate(table, resamples=5)
    refit = next(row for row in mixed if row["comparison"] == "s1_refit")
    assert refit["per_seed_advantages"] == [1200, 1200, -1200]
    assert not refit["all_seed_effects_positive"]

    # A whole seed has loss one: seed-stratified resampling must preserve
    # exactly one third loss in every draw, including escalated tickets.
    control = table["stream"].str.endswith("_control")
    audit = table["arm"] == "s1_audit"
    table.loc[control & audit & (table["stream"] == "seed_11_control"), "gold_joint_correct"] = False
    stratified, _ = evaluate(table, resamples=10)
    assert stratified[0]["paired_accuracy_loss"] == pytest.approx(1 / 3)
    assert stratified[0]["upper_one_sided_95"] == pytest.approx(1 / 3)
    assert not stratified[0]["noninferior"]
    assert stratified[0]["served_paired_accuracy_loss"] == pytest.approx(1 / 3)

    table.loc[control & audit, "served_by"] = "agent"
    no_service, _ = evaluate(table, resamples=1)
    assert no_service[0]["served_count"] == 0
    assert no_service[0]["served_arm_accuracy"] is None
    assert no_service[0]["served_reference_accuracy"] is None
    assert no_service[0]["served_paired_accuracy_loss"] is None

    missing_ticket = table[~(control & (table["ticket_index"] == 2399))]
    with pytest.raises(ValueError, match="incomplete H3 post-shift window"):
        evaluate(missing_ticket, resamples=1)


def test_missing_paired_stream_is_an_error():
    empty = pd.DataFrame(columns=["stream", "ticket_index", "arm"])
    with pytest.raises(ValueError, match="unpaired or missing"):
        evaluate(empty)
