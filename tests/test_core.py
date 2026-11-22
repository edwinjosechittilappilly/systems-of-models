import pytest

import som
from som import pricing
from som.envelope import Usage
from som.questions import ChoiceAnswer, PredicateAnswer, Refusal
from som.testing import FunctionDecider
from som.trace import TraceStore

TEAMS = som.Choice("team", "Which team should handle this ticket?", {"billing": "charges", "cards": "card issues"})
FITS = som.Predicate("fits", "Is this ticket about billing or cards?")


def s1_answering(probability: float, choice: str = "billing", fit: float = 0.9) -> FunctionDecider:
    def answer(_input, question):
        if question.name == "fits":
            return PredicateAnswer("fits", fit)
        other = "cards" if choice == "billing" else "billing"
        return ChoiceAnswer(
            "team", choice, {choice: probability, other: 1 - probability}, confidence=2 * probability - 1
        )

    return FunctionDecider(answer, name="test/s1", cost_per_call=0.0001)


def s2_answering(choice: str = "cards") -> FunctionDecider:
    return FunctionDecider(
        lambda _i, q: ChoiceAnswer(q.name, choice), system="s2.reasoning", name="test/s2", cost_per_call=0.01
    )


def test_confident_s1_answer_is_served_without_calling_s2():
    s2 = s2_answering()
    result = som.Gate(s1_answering(0.95), s2, TEAMS, threshold=0.8)("I was charged twice")
    assert (result.served_by, result.value, s2.calls) == ("s1", "billing", 0)
    assert (result.cost.amount, result.cost.basis) == (pytest.approx(0.0001), "list_price")
    result.s1.envelope.validate()


def test_unsure_s1_answer_escalates_and_records_a_valid_handoff():
    result = som.Gate(s1_answering(0.6), s2_answering("cards"), TEAMS, threshold=0.8)("My card is stuck")
    assert (result.served_by, result.value) == ("s2", "cards")
    envelope = result.s1.envelope
    assert envelope.status == "escalated"
    assert envelope.escalation.reason == "low_confidence"
    assert envelope.escalation.threshold.observed == pytest.approx(0.6)
    assert envelope.escalation.downstream_response_id == result.s2.envelope.id
    assert result.s2.envelope.trace_ref.trace_id == envelope.trace_ref.trace_id
    envelope.validate()
    result.s2.envelope.validate()


def test_confidence_metric_uses_vendor_peakedness_not_probability():
    # p = 0.85 clears 0.8 as a probability, but its peakedness (2p - 1 = 0.7) does not.
    gate = som.Gate(s1_answering(0.85), s2_answering(), TEAMS, threshold=0.8, metric="confidence")
    assert gate("x").served_by == "s2"


def test_companion_predicate_escalates_out_of_answer_space():
    result = som.Gate(s1_answering(0.99, fit=0.1), s2_answering(), TEAMS, fit=FITS)("What is the weather?")
    assert result.escalation.reason == "out_of_answer_space"
    result.s1.envelope.validate()


def test_s2_can_say_nothing_fits_after_an_out_of_space_escalation():
    def s2_answer(_input, question):
        if question.name == "fits":
            return PredicateAnswer("fits", None, raw_value=False)
        return ChoiceAnswer(question.name, "billing")

    s2 = FunctionDecider(s2_answer, system="s2.reasoning")
    result = som.Gate(s1_answering(0.99, fit=0.1), s2, TEAMS, fit=FITS)("What is the weather?")
    assert (result.served_by, result.in_scope, result.value) == ("s2", False, None)
    confident = som.Gate(s1_answering(0.99, fit=0.95), s2, TEAMS, fit=FITS)("double charge")
    assert (confident.served_by, confident.in_scope, confident.value) == ("s1", True, "billing")


def test_refusal_escalates():
    s1 = FunctionDecider(lambda _i, q: Refusal(q.name, "out_of_answer_space"))
    result = som.Gate(s1, s2_answering(), TEAMS)("?")
    assert result.escalation.reason == "refusal"


def test_shadow_mode_serves_s2_and_reports_agreement_to_the_store():
    store = TraceStore()
    result = som.Gate(s1_answering(0.99, "billing"), s2_answering("billing"), TEAMS, mode="shadow", store=store)("x")
    assert (result.served_by, result.agreed, result.escalation) == ("s2", True, None)
    (gate_record,) = store.of_kind("gate")
    assert gate_record["s1_value"] == gate_record["s2_value"] == "billing"
    assert len(store.of_kind("envelope")) == 2


def test_breakeven_rate():
    assert som.breakeven_rate(0.0001, 0.01) == pytest.approx(0.99)
    with pytest.raises(ValueError, match="s2_cost"):
        som.breakeven_rate(1, 0)


def test_list_price_cost_counts_cached_tokens_at_the_cached_rate():
    card = pricing.lookup("openai", "gpt-6.1-terra-2026-10-01")
    cost = card.cost(Usage(input_tokens=1_000_000, output_tokens=100_000, cached_tokens=500_000))
    assert cost.amount == pytest.approx(0.5 * 1.00 + 0.5 * 0.05 + 0.1 * 5.00)
    assert (cost.basis, cost.rate_card) == ("list_price", {"source": card.source, "retrieved_at": card.retrieved_at})


def test_total_cost_takes_the_weakest_basis_and_unknown_wins():
    known = pricing.lookup("typesafe", "jev-1.14.0").cost(Usage(input_tokens=1000))
    local = pricing.local_cost(Usage())
    total = som.Cost.total([("s1.decision", known, "a"), ("s2.reasoning", local, "b")])
    assert (total.basis, total.amount) == ("local_measured", pytest.approx(known.amount))
    assert [item.basis for item in total.breakdown] == ["list_price", "local_measured"]
    unknown = som.Cost.total([("s1.decision", known, "a"), ("s2.reasoning", som.Cost.unknown(), "b")])
    assert (unknown.basis, unknown.amount) == ("unknown", None)


def test_unknown_cost_validates_with_a_null_amount_and_a_number_is_rejected():
    envelope = som.Gate(s1_answering(0.95), s2_answering(), TEAMS)("x").s1.envelope
    envelope.cost = som.Cost.unknown()
    envelope.validate()
    with pytest.raises(ValueError, match="exactly when"):
        som.Cost(amount=0.0, basis="unknown")


def test_unknown_model_price_is_an_error_not_zero():
    with pytest.raises(pricing.UnknownPriceError):
        pricing.lookup("openai", "gpt-unreleased")


def test_choice_rejects_duplicate_options():
    with pytest.raises(ValueError, match="distinct"):
        som.Choice("x", "?", ["a", "a"])


def test_trace_store_round_trips_through_jsonl(tmp_path):
    path = tmp_path / "trace.jsonl"
    store = TraceStore(path)
    store.add_tool_call("route_ticket", {"department": "billing"}, trace_id="0" * 32)
    assert TraceStore.load(path).of_kind("tool_call")[0]["arguments"] == {"department": "billing"}
