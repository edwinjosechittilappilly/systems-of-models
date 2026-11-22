"""Offline tests using response shapes from the Anthropic and Google Gen AI SDKs."""

import inspect
from types import SimpleNamespace as NS

import pytest
from anthropic._models import validate_type
from anthropic.resources.messages import Messages
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from google.genai.types import GenerateContentConfig

from som import Choice, Predicate, Score
from som.adapters.anthropic import Anthropic
from som.adapters.gemini import Gemini
from som.pricing import RateCard
from som.questions import Refusal

QUESTIONS = [
    Choice("team", "Which team?", {"billing": "Charges", "cards": "Cards"}),
    Predicate("fits", "Is this banking?"),
    Score("urgency", "How urgent?", ["low", "high"]),
]
CARD = RateCard(2, 10, "https://example.com/prices", "2026-01-01", 0.5)
TEXT = '{"team":"billing","fits":true,"urgency":1}'


def test_anthropic_messages_structured_output_and_usage():
    calls = []
    response = NS(
        id="msg_123",
        model="claude-snapshot",
        content=[NS(type="thinking", thinking="private"), NS(type="text", text=TEXT)],
        stop_reason="end_turn",
        usage=NS(input_tokens=100, cache_read_input_tokens=20, cache_creation_input_tokens=0, output_tokens=30),
    )

    def create(**kwargs):
        calls.append(kwargs)
        return response

    adapter = Anthropic("claude", client=NS(messages=NS(create=create)), rate_card=CARD, max_tokens=500)
    decision = adapter.decide("refund", QUESTIONS)
    request = calls[0]
    inspect.signature(Messages.create).bind(None, **request)
    validate_type(type_=MessageCreateParamsNonStreaming, value=request)
    assert request["model"] == "claude" and request["max_tokens"] == 500
    assert request["messages"][0]["role"] == "user" and "refund" in request["messages"][0]["content"]
    schema = request["output_config"]["format"]["schema"]
    assert schema["required"] == ["team", "fits", "urgency"]
    assert schema["properties"]["team"]["enum"] == ["billing", "cards"]
    assert (decision["team"].value, decision["fits"].value, decision["urgency"].value) == ("billing", True, 1.0)
    envelope = decision.envelope
    assert envelope.id == "msg_123" and envelope.implementation.model == "claude-snapshot"
    assert envelope.cost.usage.input_tokens == 120 and envelope.cost.usage.cached_tokens == 20
    assert envelope.cost.amount == pytest.approx((100 * 2 + 20 * 0.5 + 30 * 10) / 1e6)
    envelope.validate()


def test_anthropic_cache_creation_is_not_mispriced_and_truncation_refuses():
    response = {
        "content": [{"type": "text", "text": '{"team":'}],
        "model": "claude",
        "stop_reason": "max_tokens",
        "usage": {"input_tokens": 5, "cache_creation_input_tokens": 10, "output_tokens": 2},
    }
    adapter = Anthropic("claude", client=NS(messages=NS(create=lambda **_: response)), rate_card=CARD)
    with pytest.warns(UserWarning, match="cache creation pricing"):
        decision = adapter.decide("refund", QUESTIONS)
    assert decision.envelope.status == "incomplete"
    assert decision.envelope.cost.basis == "unknown" and decision.envelope.cost.usage.input_tokens == 15
    assert all(isinstance(answer, Refusal) for answer in decision.answers.values())
    assert all(answer.reason == "out_of_answer_space" for answer in decision.answers.values())
    decision.envelope.validate()


def test_anthropic_context_window_exceeded_is_incomplete():
    response = {
        "content": [{"type": "text", "text": '{"team":'}],
        "stop_reason": "model_context_window_exceeded",
        "usage": {},
    }
    adapter = Anthropic("claude", client=NS(messages=NS(create=lambda **_: response)), rate_card=CARD)
    decision = adapter.decide("input", QUESTIONS)
    assert decision.envelope.status == "incomplete"
    assert all(
        isinstance(answer, Refusal) and answer.reason == "out_of_answer_space" for answer in decision.answers.values()
    )
    decision.envelope.validate()


def test_anthropic_policy_refusal_overrides_returned_answers():
    response = {
        "content": [{"type": "text", "text": TEXT}],
        "stop_reason": "refusal",
        "usage": {},
    }
    adapter = Anthropic("claude", client=NS(messages=NS(create=lambda **_: response)), rate_card=CARD)
    decision = adapter.decide("input", QUESTIONS)
    assert decision.envelope.status == "incomplete"
    assert all(isinstance(answer, Refusal) and answer.reason == "policy" for answer in decision.answers.values())
    decision.envelope.validate()


def test_gemini_generate_content_structured_output_and_thinking_usage():
    calls = []
    response = NS(
        response_id="response-123",
        model_version="gemini-snapshot",
        candidates=[NS(content=NS(parts=[NS(text="hidden", thought=True), NS(text=TEXT)]), finish_reason="STOP")],
        usage_metadata=NS(
            prompt_token_count=100,
            cached_content_token_count=20,
            candidates_token_count=30,
            thoughts_token_count=10,
        ),
    )

    def generate_content(**kwargs):
        calls.append(kwargs)
        return response

    adapter = Gemini("gemini", client=NS(models=NS(generate_content=generate_content)), rate_card=CARD)
    decision = adapter.decide("refund", QUESTIONS)
    request = calls[0]
    GenerateContentConfig.model_validate(request["config"])
    assert request["model"] == "gemini" and "refund" in request["contents"]
    assert request["config"]["response_mime_type"] == "application/json"
    assert request["config"]["response_json_schema"]["required"] == ["team", "fits", "urgency"]
    assert (decision["team"].value, decision["fits"].value, decision["urgency"].value) == ("billing", True, 1.0)
    envelope = decision.envelope
    assert envelope.id == "response-123" and envelope.implementation.model == "gemini-snapshot"
    assert envelope.cost.usage.output_tokens == 40 and envelope.cost.usage.reasoning_tokens == 10
    assert envelope.cost.amount == pytest.approx((80 * 2 + 20 * 0.5 + 40 * 10) / 1e6)
    envelope.validate()


@pytest.mark.parametrize("block_reason", ["SAFETY", "MODEL_ARMOR", "JAILBREAK"])
def test_gemini_blocked_response_refuses_without_inventing_output(block_reason):
    response = {"candidates": [], "prompt_feedback": {"block_reason": block_reason}, "usage_metadata": {}}
    adapter = Gemini("gemini", client=NS(models=NS(generate_content=lambda **_: response)), rate_card=CARD)
    decision = adapter.decide("input", QUESTIONS)
    assert decision.envelope.status == "incomplete"
    assert all(isinstance(answer, Refusal) for answer in decision.answers.values())
    assert all(answer.reason == "policy" for answer in decision.answers.values())
    decision.envelope.validate()


@pytest.mark.parametrize(
    "finish_reason",
    ["SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII", "MODEL_ARMOR", "IMAGE_RECITATION"],
)
def test_gemini_candidate_policy_refusal_overrides_returned_answers(finish_reason):
    response = {
        "candidates": [{"content": {"parts": [{"text": TEXT}]}, "finish_reason": NS(value=finish_reason)}],
        "usage_metadata": {},
    }
    adapter = Gemini("gemini", client=NS(models=NS(generate_content=lambda **_: response)), rate_card=CARD)
    decision = adapter.decide("input", QUESTIONS)
    assert decision.envelope.status == "incomplete"
    assert all(isinstance(answer, Refusal) and answer.reason == "policy" for answer in decision.answers.values())
    decision.envelope.validate()


def test_gemini_truncation_is_incomplete_not_policy_refusal():
    response = {
        "candidates": [{"content": {"parts": [{"text": '{"team":'}]}, "finish_reason": "MAX_TOKENS"}],
        "usage_metadata": {},
    }
    adapter = Gemini("gemini", client=NS(models=NS(generate_content=lambda **_: response)), rate_card=CARD)
    decision = adapter.decide("input", QUESTIONS)
    assert decision.envelope.status == "incomplete"
    assert all(
        isinstance(answer, Refusal) and answer.reason == "out_of_answer_space" for answer in decision.answers.values()
    )
    decision.envelope.validate()
