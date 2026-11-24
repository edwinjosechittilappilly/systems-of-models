import pandas as pd
import pytest

from bench.e3a.metrics import discovery_rows, discovery_summary, summarize_streams
from som.compile.mining import Candidate, MiningReport


def candidate(kind, tool, reason=None):
    return Candidate(kind, f"{tool}.{kind}", tool, None, reason=reason)


def test_discovery_scores_frozen_truth_and_retains_rejections_and_ambiguity():
    report = MiningReport(
        [candidate("retrieval_choice", "search_policy"), candidate("branch", "route")],
        [
            candidate("branch", "verify_identity", "functional_dependency"),
            candidate("tool_argument", "search_policy", "copied_from_input"),
        ],
        ambiguous_retrieval_count=3,
    )
    assert discovery_summary(report) == {
        "discovery_precision": 0.5,
        "discovery_recall": 0.5,
        "discovery_true_positives": 1,
        "discovery_accepted": 2,
        "discovery_rejected": 2,
        "ambiguous_retrieval_count": 3,
    }
    rows = discovery_rows(report)
    assert len(rows) == 4
    assert rows[2]["is_true"] and rows[2]["reason"] == "functional_dependency"
    assert not rows[3]["is_true"]


def test_discovery_recall_includes_truths_not_observed_by_miner():
    result = discovery_summary(MiningReport([], [], 0))
    assert result["discovery_precision"] is None
    assert result["discovery_recall"] == 0


def tickets(count=5, shift=2, stream="shifted"):
    rows = []
    for arm in ("always_agent", "compiled"):
        for i in range(count):
            rows.append(
                {
                    "ticket_index": i,
                    "shift_at": shift,
                    "arm": arm,
                    "stream": stream,
                    "gold_joint_correct": True,
                    "teacher_agreement": None,
                    "served_by": "agent" if arm == "always_agent" else "s1",
                    "cost_usd": 1.0,
                    "demoted": False,
                    "audited": False,
                    "promoted": False,
                }
            )
    return pd.DataFrame(rows)


def row(frame, arm="compiled"):
    return summarize_streams(frame).set_index("arm").loc[arm]


def test_detection_includes_shift_ticket_audits_and_pre_shift_false_alarms():
    data = tickets()
    compiled = data.arm == "compiled"
    data.loc[compiled & data.ticket_index.isin([1, 4]), "demoted"] = True
    data.loc[compiled & data.ticket_index.isin([2, 4]), "audited"] = True
    result = row(data)
    assert result.false_demotions == 1
    assert result.detection_ticket == 4
    assert result.detection_delay_tickets == 2
    assert result.detection_delay_audits == 2
    assert not result.detection_miss


def test_misses_and_no_shift_false_alarms_are_distinct():
    shifted = tickets()
    shifted.loc[(shifted.arm == "compiled") & (shifted.ticket_index == 1), "demoted"] = True
    result = row(shifted)
    assert result.detection_miss
    assert pd.isna(result.detection_ticket)
    assert result.false_demotions == 1
    control = shifted.copy()
    control["shift_at"] = None
    result = row(control)
    assert pd.isna(result.detection_miss)
    assert result.false_demotions == 1


def test_recovery_requires_full_200_ticket_run_and_rolling_accuracy_and_coverage():
    data = tickets(count=400, shift=100)
    result = row(data)
    assert result.recovery_ticket == 100
    assert result.recovery_delay_tickets == 0
    data = data[data.ticket_index < 299]
    assert pd.isna(row(data).recovery_ticket)
    data = tickets(count=400, shift=100)
    data.loc[(data.arm == "compiled") & (data.ticket_index == 120), "gold_joint_correct"] = False
    data.loc[(data.arm == "compiled") & (data.ticket_index == 121), "gold_joint_correct"] = False
    data.loc[(data.arm == "compiled") & (data.ticket_index == 122), "gold_joint_correct"] = False
    assert pd.isna(row(data).recovery_ticket)


def test_paired_excess_error_cost_and_amortization():
    data = tickets()
    compiled = data.arm == "compiled"
    data.loc[compiled, "cost_usd"] = [3.0, 0.5, 0.5, 0.5, 0.5]
    data.loc[compiled & data.ticket_index.isin([1, 3]), "gold_joint_correct"] = False
    result = row(data)
    assert result.total_cost_usd == 5
    assert result.cost_per_ticket_usd == 1
    assert result.cumulative_excess_error == 2
    assert result.postshift_cumulative_excess_error == 1
    assert result.amortization_ticket == 4
    assert result.amortization_horizon_tickets == 4
    assert pd.isna(row(data, "always_agent").amortization_ticket)


def test_recovery_requires_rolling_coverage_and_resets_on_a_bad_window():
    data = tickets(count=500, shift=100)
    compiled = data.arm == "compiled"
    data.loc[compiled & (data.ticket_index < 100), "served_by"] = "agent"
    result = row(data)
    assert result.recovery_ticket == 149
    data.loc[compiled & data.ticket_index.between(200, 299), "served_by"] = "agent"
    assert pd.isna(row(data).recovery_ticket)


def test_unpaired_and_duplicate_tickets_rejected():
    data = tickets()
    with pytest.raises(ValueError, match="Ticket indices differ"):
        summarize_streams(data.iloc[:-1])
    with pytest.raises(ValueError, match="Duplicate"):
        summarize_streams(pd.concat([data, data.iloc[[0]]]))
