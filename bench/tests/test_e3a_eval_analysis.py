import json

import pandas as pd

from bench.e3a.eval_analysis import report


def write_csv(path, rows):
    pd.DataFrame(rows).to_csv(path, index=False)


def test_missing_and_interrupted_outputs_are_not_success(tmp_path):
    (tmp_path / "budget_stop.json").write_text(json.dumps({"spent_usd": {"openai": 75}, "error": "budget"}))
    text = report(tmp_path)
    assert "Recorded budget stop" in text
    assert "Manifest unavailable" in text
    assert "not evaluable" in text
    assert "h3.csv" in text
    assert "seed_11_control_s1_audit.csv" in text
    assert "Provider dashboard reconciliation is unverified" in text


def test_numeric_verdicts_and_promotions_are_reported(tmp_path):
    write_csv(
        tmp_path / "discovery_summary.csv",
        [
            {"discovery_precision": 1, "discovery_recall": 1},
            {"discovery_precision": 0.5, "discovery_recall": 1},
            {"discovery_precision": None, "discovery_recall": 0},
        ],
    )
    write_csv(
        tmp_path / "h3.csv",
        [
            {
                "paired_accuracy_loss": 0.01,
                "upper_one_sided_95": 0.019,
                "margin": 0.02,
                "noninferior": True,
                "served_count": 4,
            }
        ],
    )
    write_csv(
        tmp_path / "h4.csv",
        [
            {
                "comparison": "s1_refit",
                "mean_audit_advantage": 4,
                "holm_p_within_severity": 0.04,
                "per_seed_advantages": "[1, 2, 9]",
                "all_seed_effects_positive": True,
            },
            {
                "comparison": "escalation_only",
                "mean_audit_advantage": -1,
                "holm_p_within_severity": 0.2,
                "per_seed_advantages": "[-1, 0, -2]",
                "all_seed_effects_positive": False,
            },
        ],
    )
    modification = {
        "operation": "add",
        "target_ref": "s1_audit/d1",
        "after": {"value": {"generation": 1}},
        "evaluation": {
            "eval_suite": "independent shadow calibration and validation",
            "candidate": {"validation_served": 80, "validation_errors": 3, "validation_upper_bound": 0.12},
        },
    }
    (tmp_path / "s5-records.jsonl").write_text(
        json.dumps({"response": {"body": {"modifications": [modification]}}}) + "\n"
    )
    text = report(tmp_path)
    assert "1/2 reports" in text
    assert "1 have undefined endpoints" in text
    assert "below 0.15: 1/1 (1)" in text
    assert "noninferiority demonstrated" in text
    assert "Against s1_refit: lower error demonstrated" in text
    assert "Against escalation_only: lower error not demonstrated" in text
    assert "[1, 2, 9]" in text


def test_empty_promotions_and_missing_holm_family_are_inconclusive(tmp_path):
    (tmp_path / "s5-records.jsonl").write_text("")
    write_csv(
        tmp_path / "h4.csv",
        [
            {
                "comparison": "s1_refit",
                "mean_audit_advantage": 5,
                "holm_p_within_severity": 0.01,
                "per_seed_advantages": "[5,5,5]",
                "all_seed_effects_positive": True,
            }
        ],
    )
    text = report(tmp_path)
    assert "not evaluable: no promotions" in text
    assert "both valid Holm-family comparisons are required" in text
    assert "lower error demonstrated" not in text
