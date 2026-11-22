import math

from bench.e3b.sensitivity import sensitivity


def row(domain, candidate, variant, teacher, prediction, transcript=()):
    return {
        "domain": domain,
        "candidate": candidate,
        "state_variant": variant,
        "teacher": teacher,
        "prediction": prediction,
        "state": {"transcript": list(transcript)},
    }


def test_held_out_majorities_and_matched_ablation_accuracy():
    rows = [
        row("retail", "cancel_pending_order.reason", "full", "z", "z"),
        row("retail", "cancel_pending_order.reason", "full", "a", "a"),
        row("airline", "book_reservation.cabin", "full", "economy", "economy"),
        row("retail", "cancel_pending_order.reason", "user-and-tools-only", "z", "z"),
        row("retail", "cancel_pending_order.reason", "user-and-tools-only", "a", "wrong"),
        row("airline", "book_reservation.cabin", "user-and-tools-only", "economy", None),
    ]
    result = sensitivity(rows)
    assert result["held_out_majority"] == {
        "airline": {"book_reservation.cabin": "economy"},
        "retail": {"cancel_pending_order.reason": "a"},
    }
    assert result["matched_majority"] == {"n": 2, "correct": 1, "accuracy": 0.5}
    assert result["user_and_tools_only_teacher"] == {"n": 2, "correct": 1, "accuracy": 0.5}


def test_cancellation_echo_counts_instances_not_messages_and_only_assistant_text():
    candidate = "cancel_pending_order.reason"
    assistant = {"role": "assistant", "content": "I will cancel for changed mind; changed mind."}
    user = {"role": "user", "content": "changed mind"}
    rows = [
        row("retail", candidate, "full", "changed mind", "changed mind", [assistant, assistant]),
        row("retail", candidate, "full", "changed mind", "changed mind", [user]),
        row("retail", candidate, "full", "Changed mind", "Changed mind", [assistant]),
        row("retail", candidate, "user-and-tools-only", "changed mind", "changed mind", [assistant]),
        row("airline", candidate, "full", "changed mind", "changed mind", [assistant]),
        row("retail", "other.reason", "full", "changed mind", "changed mind", [assistant]),
    ]
    assert sensitivity(rows)["cancellation_reason_assistant_echo_count"] == 1
    assert sensitivity(rows)["cancellation_reason_casefolded_assistant_echo_count"] == 2


def test_empty_input_and_unmatched_ablation_have_undefined_accuracy():
    empty = sensitivity([])
    assert empty["held_out_majority"] == {}
    assert empty["cancellation_reason_assistant_echo_count"] == 0
    for key in ("matched_majority", "user_and_tools_only_teacher"):
        assert empty[key]["n"] == empty[key]["correct"] == 0
        assert math.isnan(empty[key]["accuracy"])

    unmatched = sensitivity([row("retail", "x", "user-and-tools-only", "yes", "yes")])
    assert unmatched["user_and_tools_only_teacher"] == {"n": 1, "correct": 1, "accuracy": 1.0}
    assert unmatched["matched_majority"]["n"] == 0
    assert math.isnan(unmatched["matched_majority"]["accuracy"])
