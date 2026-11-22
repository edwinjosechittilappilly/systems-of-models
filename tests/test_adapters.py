"""Adapters against recorded, secret-free provider responses (tests/fixtures). Live variants are marked ``live``."""

import json
import os
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

import som
from som.questions import ChoiceAnswer, PredicateAnswer, Refusal, ScoreAnswer

FIXTURES = Path(__file__).parent / "fixtures"
TEXT = "I see two charges for the same coffee on my statement, can you refund one?"
TEAM = som.Choice(
    "team",
    "Which team should handle this ticket?",
    {
        "billing": "charges, refunds, invoices",
        "cards": "lost, stolen or declined cards",
        "fraud": "unauthorised activity",
    },
)
FITS = som.Predicate(
    "fits",
    "Is this ticket about a bank account or card?",
    true_means="a banking support request",
    false_means="anything else",
)
URGENCY = som.Score("urgency", "How urgent is this ticket?", ["can wait", "this week", "today"])
QUESTIONS = [TEAM, FITS, URGENCY]


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_typesafe_sends_the_documented_request_and_maps_every_answer_type():
    recorded = fixture("typesafe_systemone.json")
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=recorded["response"])

    adapter = som.TypeSafe("jev-preview", api_key="test", client=httpx.Client(transport=httpx.MockTransport(handler)))
    decision = adapter.decide(TEXT, QUESTIONS)

    assert json.loads(seen[0].content) == recorded["request"]
    assert seen[0].headers["authorization"] == "Bearer test"
    team, fits, urgency = (decision[q.name] for q in QUESTIONS)
    assert isinstance(team, ChoiceAnswer) and team.choice == "billing" and team.top_probability == 1.0
    assert isinstance(fits, PredicateAnswer) and fits.probability == pytest.approx(0.84)
    assert isinstance(urgency, ScoreAnswer) and urgency.labels == ("can wait", "this week", "today")
    envelope = decision.envelope
    assert envelope.implementation.model == "jev-1.14.0"  # the versioned model behind the alias
    assert envelope.cost.basis == "list_price"
    assert envelope.cost.amount == pytest.approx(428 * 0.042 / 1e6)
    assert envelope.confidence == pytest.approx(0.6)  # lowest chosen-answer probability: urgency level 1
    envelope.validate()


def test_typesafe_retries_rate_limits_then_succeeds(monkeypatch):
    monkeypatch.setattr("som.adapters.typesafe.time.sleep", lambda _s: None)
    recorded = fixture("typesafe_systemone.json")["response"]
    statuses = iter([429, 529, 200])

    def handler(_request: httpx.Request) -> httpx.Response:
        status = next(statuses)
        return httpx.Response(status, json=recorded if status == 200 else {"detail": "slow down"})

    adapter = som.TypeSafe(api_key="test", client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert adapter.decide(TEXT, QUESTIONS)["team"].value == "billing"


def test_typesafe_surfaces_api_errors_instead_of_answering():
    adapter = som.TypeSafe(
        api_key="bad", client=httpx.Client(transport=httpx.MockTransport(lambda _r: httpx.Response(401)))
    )
    with pytest.raises(httpx.HTTPStatusError):
        adapter.decide(TEXT, QUESTIONS)


def fake_openai(**resources: object) -> SimpleNamespace:
    return SimpleNamespace(**resources)


def test_openai_decisions_maps_answers_and_prices_input_tokens_only():
    recorded = fixture("openai_decisions.json")
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return recorded

    adapter = som.OpenAIDecisions(client=fake_openai(decisions=SimpleNamespace(create=create)))
    decision = adapter.decide(TEXT, QUESTIONS)
    assert calls[0]["questions"][0]["choices"][0] == {"value": "billing", "description": "charges, refunds, invoices"}
    assert decision["team"].value == recorded["answers"][0]["choice"]
    assert isinstance(decision["urgency"], ScoreAnswer)
    usage = recorded["usage"]
    assert decision.envelope.cost.amount == pytest.approx(usage["input_tokens"] * 0.10 / 1e6)
    decision.envelope.validate()


def test_openai_responses_parses_structured_output_and_records_reasoning_tokens():
    recorded = fixture("openai_responses.json")
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return {**recorded, "output_text": json.dumps({"team": "billing", "fits": True, "urgency": 0})}

    adapter = som.OpenAIResponses(client=fake_openai(responses=SimpleNamespace(create=create)))
    decision = adapter.decide(TEXT, QUESTIONS)
    schema = calls[0]["text"]["format"]["schema"]
    assert schema["properties"]["team"]["enum"] == ["billing", "cards", "fraud"]
    assert schema["required"] == ["team", "fits", "urgency"] and schema["additionalProperties"] is False
    assert (decision["team"].value, decision["fits"].value, decision["urgency"].value) == ("billing", True, 0.0)
    envelope = decision.envelope
    assert envelope.system == "s2.reasoning" and envelope.confidence is None
    assert (
        envelope.body["reasoning"]["reasoning_tokens"] == recorded["usage"]["output_tokens_details"]["reasoning_tokens"]
    )
    envelope.validate()


def test_openai_responses_reads_the_answer_from_raw_json_without_output_text():
    # Raw API JSON (proxies, recorded responses) has no SDK `output_text` property; the text lives in output items.
    recorded = fixture("openai_responses.json")
    assert "output_text" not in recorded
    adapter = som.OpenAIResponses(client=fake_openai(responses=SimpleNamespace(create=lambda **_: recorded)))
    decision = adapter.decide(TEXT, QUESTIONS)
    text = next(part["text"] for item in recorded["output"] for part in item.get("content") or [])
    assert decision["team"].value == json.loads(text)["team"]


def test_an_answer_outside_the_answer_space_becomes_a_refusal():
    recorded = fixture("openai_responses.json")
    adapter = som.OpenAIResponses(
        client=fake_openai(
            responses=SimpleNamespace(create=lambda **_: {**recorded, "output_text": '{"team": "legal"}'})
        )
    )
    assert isinstance(adapter.decide(TEXT, [TEAM])["team"], Refusal)


def test_openai_chat_covers_compatible_servers_and_cost_bases():
    recorded = fixture("openai_chat.json")
    completions = SimpleNamespace(create=lambda **_: recorded)
    client = fake_openai(chat=SimpleNamespace(completions=completions))

    hosted = som.OpenAIChat("gpt-6-luna", client=client).decide("My card was declined", [TEAM])
    assert hosted["team"].value == "cards" and hosted.envelope.cost.basis == "list_price"
    hosted.envelope.validate()

    local = som.OpenAIChat("qwen3.5:2b", client=client, provider="ollama", local=True).decide("x", [TEAM])
    assert (local.envelope.cost.basis, local.envelope.cost.amount) == ("local_measured", 0.0)

    routed = {**recorded, "usage": {**recorded["usage"], "cost": 0.00042}}
    openrouter = som.OpenAIChat(
        "openai/gpt-5-nano",
        client=fake_openai(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_: routed))),
        provider="openrouter",
    ).decide("x", [TEAM])
    assert (openrouter.envelope.cost.basis, openrouter.envelope.cost.amount) == ("provider_reported", 0.00042)


def test_unpriced_model_records_unknown_cost_with_a_warning():
    recorded = fixture("openai_chat.json")
    client = fake_openai(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_: recorded)))
    with pytest.warns(UserWarning, match="no rate card"):
        decision = som.OpenAIChat("some-new-model", client=client, provider="acme").decide("x", [TEAM])
    assert (decision.envelope.cost.basis, decision.envelope.cost.amount) == ("unknown", None)
    decision.envelope.validate()


live = pytest.mark.live


@live
@pytest.mark.skipif(not os.environ.get("TYPESAFE_API_KEY"), reason="needs TYPESAFE_API_KEY")
def test_live_typesafe():
    decision = som.TypeSafe("jev-preview").decide(TEXT, QUESTIONS)
    assert decision["team"].value == "billing"
    decision.envelope.validate()


@live
@pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"), reason="needs OPENAI_API_KEY")
def test_live_openai_gate_end_to_end():
    gate = som.Gate(som.OpenAIDecisions(), som.OpenAIResponses(), TEAM, fit=FITS, threshold=0.99)
    result = gate(TEXT)
    assert result.value == "billing"
    result.s1.envelope.validate()
    if result.s2 is not None:
        result.s2.envelope.validate()
