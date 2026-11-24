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


def test_typesafe_reconciliation_and_stop_history(tmp_path):
    stop = {"error": "TypeSafe 402 Payment Required", "spent_usd": {"typesafe": 2.8020353839984793}}
    previous = tmp_path / "previous.json"
    previous.write_text(json.dumps(stop))
    (tmp_path / "budget_stop.json").write_text(json.dumps({"error": "new stop"}))
    text = report(tmp_path, (previous,))
    assert "new stop" in text
    assert "TypeSafe 402 Payment Required" in text
    assert "$4.89" in text
    assert "$2.75" in text
    assert "1.78" in text
    assert "$8.00" in text
    assert "$14.78" in text
    assert "$0.05" in text
    assert "cannot guarantee" in text


def test_openai_503_deviation_preserves_both_explicit_stop_histories(tmp_path):
    previous = tmp_path / "previous.json"
    resumed = tmp_path / "resumed.json"
    previous.write_text(json.dumps({"error": "TypeSafe 402 Payment Required"}))
    resumed.write_text(
        json.dumps(
            {
                "error": "BudgetExceeded: openai: budget reserved for unpriced call: "
                "Error code: 503 - Unable to verify model access right now. Please retry.",
                "spent_usd": {"openai": 35.112541169999865},
            }
        )
    )
    text = report(tmp_path, (resumed, previous))
    assert str(resumed) in text
    assert str(previous) in text
    assert "TypeSafe 402 Payment Required" in text
    assert "503 - Unable to verify model access" in text
    assert "503 stop deviation" in text
    assert "$1.00 unpriced-call reservation is retained" in text
    assert "not evidence of actual provider billing" in text


def test_unrelated_503_does_not_claim_openai_reservation(tmp_path):
    (tmp_path / "budget_stop.json").write_text(json.dumps({"error": "other provider: 503"}))
    text = report(tmp_path)
    assert "503 stop deviation" not in text
    assert "$1.00 unpriced-call reservation is retained" not in text


def test_openai_credit_stop_and_clinc_replay_deviation(tmp_path):
    (tmp_path / "budget_stop.json").write_text(json.dumps({"error": "openai: 429 - You have no credits remaining"}))
    text = report(tmp_path)
    assert "OpenAI 429 deviation" in text
    assert "$1.00 unpriced-call reservation was retained" in text
    assert "seed_11_clinc: secondary audit-rate replays skipped" in text
    assert "seed_11_clinc_s1_audit_0.1.csv" not in text


def test_explicit_current_stop_is_reported_only_once(tmp_path):
    stop = tmp_path / "budget_stop.json"
    stop.write_text(json.dumps({"error": "budget"}))
    text = report(tmp_path, (stop,))
    assert text.count("Recorded budget stop") == 1


def test_cli_does_not_overwrite_existing_report(tmp_path, monkeypatch):
    import sys

    import pytest

    from bench.e3a.eval_analysis import main

    output = tmp_path / "ANALYSIS.md"
    output.write_text("previous report")
    monkeypatch.setattr(sys, "argv", ["eval_analysis", "--input-dir", str(tmp_path), "--output", str(output)])
    with pytest.raises(FileExistsError):
        main()
    assert output.read_text() == "previous report"


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
    assert "Distinct validation result signatures below 0.15: 1/1" in text
    assert "noninferiority demonstrated" in text
    assert "Against s1_refit: lower error demonstrated" in text
    assert "Against escalation_only: lower error not demonstrated" in text
    assert "point estimate favours the comparator" in text
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


def test_duplicate_promotion_records_are_not_independent_windows(tmp_path):
    def modification(arm):
        return {
            "operation": "add",
            "target_ref": f"{arm}/d1",
            "after": {"value": {"generation": 1}},
            "evaluation": {
                "eval_suite": "independent shadow calibration and validation",
                "candidate": {"validation_served": 80, "validation_errors": 3, "validation_upper_bound": 0.12},
            },
        }

    mods = [modification("s1_audit"), modification("s1_refit"), modification("s1_audit_0.1")]
    (tmp_path / "s5-records.jsonl").write_text(json.dumps({"response": {"body": {"modifications": mods}}}) + "\n")
    text = report(tmp_path)
    assert "Distinct validation result signatures below 0.15: 1/1" in text
    assert "3 transition rows include repeated arms and secondary replays" in text


def test_cost_ratios_use_only_matched_streams(tmp_path):
    write_csv(
        tmp_path / "summary.csv",
        [
            {"stream": "seed_11_control", "arm": "always_agent", "tickets": 10, "total_cost_usd": 10},
            {"stream": "seed_23_control", "arm": "always_agent", "tickets": 10, "total_cost_usd": 20},
            {"stream": "seed_11_control", "arm": "s1_audit_0.1", "tickets": 10, "total_cost_usd": 8},
            {"stream": "seed_37_clinc", "arm": "always_agent", "tickets": 10, "total_cost_usd": 100},
        ],
    )
    text = report(tmp_path)
    assert "| s1_audit_0.1 | control | 1 | 0.8 |" in text
    assert "| s1_audit_0.1 | clinc |" not in text


def test_h3_composition_and_served_disagreement_are_descriptive(tmp_path):
    for seed in (11, 23, 37):
        stream = f"seed_{seed}_control"
        served = seed != 11
        write_csv(
            tmp_path / f"{stream}_s1_audit.csv",
            [
                {
                    "ticket_index": 1200,
                    "served_by": "s1" if served else "agent",
                    "gold_joint_correct": True,
                    "joint_decision_agreement": not served,
                }
            ],
        )
        write_csv(
            tmp_path / f"{stream}_always_agent.csv",
            [
                {
                    "ticket_index": 1200,
                    "served_by": "agent",
                    "gold_joint_correct": not served,
                }
            ],
        )
    text = report(tmp_path)
    assert "| 11 | 1 | 0 |" in text
    assert "Compiled-served: 2/3" in text
    assert "Selected served subset, descriptive only" in text
    assert "Audits do not replace the compiled answer" in text
    assert "seed_23_control, all: 1/1 = 1" in text


def test_h1_warmup_and_distractors_are_not_averaged(tmp_path):
    write_csv(
        tmp_path / "discovery_summary.csv",
        [
            {
                "stream": "seed_11_control",
                "arm": "s1_audit",
                "ticket_index": 300,
                "stage": "raw",
                "discovery_precision": 0.5,
                "discovery_recall": 1,
                "ambiguous_retrieval_count": 0,
            }
        ],
    )
    write_csv(
        tmp_path / "discovery.csv",
        [
            {"name": "get_policy.entry_id", "accepted": True, "stage": "raw", "support": 30},
            {"name": "route_ticket.queue", "accepted": True, "stage": "raw", "support": 20},
            {"name": "route_ticket.branch", "accepted": True, "stage": "raw", "support": 8},
        ],
    )
    text = report(tmp_path)
    assert "H1 is not supported as stated" in text
    assert "| seed_11_control | raw | 0.5 | 1 |" in text
    assert "Distractor `get_policy.entry_id` accepted in 1/1" in text
    assert "Distractor `route_ticket.queue` accepted in 1/1" in text
    assert "Ambiguous retrieval count range: 0-0" in text
    assert "mean candidate-level precision" not in text
