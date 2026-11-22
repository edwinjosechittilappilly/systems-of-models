"""Regression tests for the review of PRs #3/#4 (trace propagation, truncated output, Score semantics, margins)."""

import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

import som
from som import pricing
from som.adapters.typesafe import _retry_delay
from som.questions import PredicateAnswer, Refusal, ScoreAnswer
from som.testing import FunctionDecider

FIXTURES = Path(__file__).parent / "fixtures"
TEAM = som.Choice("team", "Which team?", ["billing", "cards"])


def test_s1_and_s2_share_one_trace_when_opentelemetry_is_configured():
    sdk_trace = pytest.importorskip("opentelemetry.sdk.trace")
    export = pytest.importorskip("opentelemetry.sdk.trace.export")
    in_memory = pytest.importorskip("opentelemetry.sdk.trace.export.in_memory_span_exporter")
    from opentelemetry import trace

    exporter = in_memory.InMemorySpanExporter()
    provider = sdk_trace.TracerProvider()
    provider.add_span_processor(export.SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test")
    unsure = FunctionDecider(lambda _i, q: som.ChoiceAnswer(q.name, "billing", {"billing": 0.55, "cards": 0.45}))
    s2 = FunctionDecider(lambda _i, q: som.ChoiceAnswer(q.name, "cards"), system="s2.reasoning")
    original = trace.get_tracer_provider
    trace.get_tracer_provider = lambda: provider  # type: ignore[assignment]
    try:
        with tracer.start_as_current_span("request"):
            result = som.Gate(unsure, s2, TEAM)("x")
    finally:
        trace.get_tracer_provider = original  # type: ignore[assignment]
    assert result.s1.envelope.trace_ref.trace_id == result.s2.envelope.trace_ref.trace_id
    assert len({span.context.trace_id for span in exporter.get_finished_spans()}) == 1


def test_s2_trace_id_joins_the_gate_trace_without_opentelemetry():
    unsure = FunctionDecider(lambda _i, q: som.ChoiceAnswer(q.name, "billing", {"billing": 0.5, "cards": 0.5}))
    s2 = FunctionDecider(lambda _i, q: som.ChoiceAnswer(q.name, "cards"), system="s2.reasoning")
    result = som.Gate(unsure, s2, TEAM)("x")
    assert result.s1.envelope.trace_ref.trace_id == result.s2.envelope.trace_ref.trace_id


def test_truncated_responses_output_becomes_an_incomplete_refusal_not_a_crash():
    recorded = json.loads((FIXTURES / "openai_responses.json").read_text())
    truncated = {
        **recorded,
        "status": "incomplete",
        "incomplete_details": {"reason": "max_output_tokens"},
        "output_text": '{"team":"bil',
    }
    adapter = som.OpenAIResponses(client=SimpleNamespace(responses=SimpleNamespace(create=lambda **_: truncated)))
    decision = adapter.decide("x", [TEAM])
    assert isinstance(decision["team"], Refusal)
    assert decision.envelope.status == "incomplete"
    assert decision.envelope.body["incomplete_details"]["reason"] == "max_output_tokens"
    decision.envelope.validate()


def test_chat_refusal_maps_to_policy_and_length_cutoff_to_incomplete():
    recorded = json.loads((FIXTURES / "openai_chat.json").read_text())
    choice = recorded["choices"][0]
    refused = {**recorded, "choices": [{**choice, "message": {**choice["message"], "content": None, "refusal": "no"}}]}
    cut = {
        **recorded,
        "choices": [{**choice, "finish_reason": "length", "message": {**choice["message"], "content": "["}}],
    }

    def chat(response):
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_: response)))
        return som.OpenAIChat("gpt-6-luna", client=client).decide("x", [TEAM])

    assert chat(refused)["team"] == Refusal("team", "policy")
    truncated = chat(cut)
    assert (truncated.envelope.status, truncated["team"].reason) == ("incomplete", "out_of_answer_space")


def test_score_value_is_the_most_likely_level_so_shadow_agreement_is_right():
    s1 = FunctionDecider(lambda _i, q: ScoreAnswer(q.name, 0.3, (0.85, 0.0, 0.15), ("low", "mid", "high")))
    s2 = FunctionDecider(lambda _i, q: ScoreAnswer(q.name, 0.0, labels=("low", "mid", "high")), system="s2.reasoning")
    question = som.Score("urgency", "How urgent?", ["low", "mid", "high"])
    result = som.Gate(s1, s2, question, mode="shadow")("x")
    assert result.s1.answers["urgency"].value == 0
    assert result.agreed is True


def test_margin_for_predicates_is_the_gap_between_outcomes():
    s1 = FunctionDecider(lambda _i, q: PredicateAnswer(q.name, 0.6))
    s2 = FunctionDecider(lambda _i, q: PredicateAnswer(q.name, None, raw_value=True), system="s2.reasoning")
    gate = som.Gate(s1, s2, som.Predicate("refund", "Is this a refund request?"), threshold=0.5, metric="margin")
    result = gate("x")
    assert result.escalation is not None
    assert result.escalation.threshold.observed == pytest.approx(0.2)


def test_refused_flag_when_s2_also_refuses():
    s1 = FunctionDecider(lambda _i, q: Refusal(q.name))
    s2 = FunctionDecider(lambda _i, q: Refusal(q.name, "policy"), system="s2.reasoning")
    result = som.Gate(s1, s2, TEAM)("x")
    assert (result.refused, result.value, result.served_by) == (True, None, "s2")


def test_metadata_keys_cannot_collide_with_store_fields_and_reach_envelopes():
    store = som.TraceStore()
    s1 = FunctionDecider(lambda _i, q: som.ChoiceAnswer(q.name, "cards", {"billing": 0.01, "cards": 0.99}))
    result = som.Gate(s1, s1, TEAM, store=store)("x", metadata={"question": "q-17", "ticket": "T-1"})
    assert result.s1.envelope.metadata == {"question": "q-17", "ticket": "T-1"}
    assert store.of_kind("gate")[0]["metadata"]["ticket"] == "T-1"


def test_retry_after_accepts_http_dates_and_is_capped():
    assert _retry_delay("Wed, 21 Oct 2015 07:28:00 GMT", 0) == 0.0  # a date in the past waits zero
    assert _retry_delay("3600", 0) == 60.0
    assert _retry_delay(None, 2) == 4.0


def test_typesafe_fills_the_missing_side_of_predicate_criteria():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "model": "jev-1.14.0",
                "answers": {"spam": {"type": "noul", "noul": 0.1}},
                "usage": {"input_tokens": 10, "output_tokens": 1},
            },
        )

    adapter = som.TypeSafe(api_key="t", client=httpx.Client(transport=httpx.MockTransport(handler)))
    adapter.decide("hi", [som.Predicate("spam", "Is this spam?", true_means="unsolicited advertising")])
    assert seen[0]["questions"]["spam"]["criteria"] == {
        "true": "unsolicited advertising",
        "false": "not: unsolicited advertising",
    }


def test_predicate_outcome_descriptions_reach_vendors_without_criteria_fields():
    contract = som.Predicate("spam", "Is this spam?", true_means="ads", false_means="a real conversation").to_contract()
    assert contract["instructions"] == "Is this spam? (true means: ads; false means: a real conversation)"


def test_price_lookup_matches_dated_snapshots_only():
    assert pricing.lookup("openai", "gpt-5-mini-2025-08-07") is pricing.lookup("openai", "gpt-5-mini")
    with pytest.raises(pricing.UnknownPriceError):
        pricing.lookup("openai", "gpt-5-mini-search-preview")


def test_breakdown_items_follow_the_null_iff_unknown_rule():
    with pytest.raises(ValueError, match="exactly when"):
        som.envelope.CostItem("s1.decision", 0.1, "unknown")
    with pytest.raises(ValueError, match="currencies"):
        som.Cost.total(
            [
                ("s1.decision", som.Cost(1.0, "list_price", currency="EUR"), None),
                ("s2.reasoning", som.Cost(1.0, "list_price"), None),
            ]
        )


def test_usage_weighted_breakeven():
    assert som.gate.usage_weighted_breakeven(0.001, 0.010, 0.020) == pytest.approx(0.45)
