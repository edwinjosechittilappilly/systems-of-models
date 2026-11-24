import json

import httpx
import pytest

from bench.common.budget import Budget
from bench.common.cache import CacheMiss
from bench.e3a.providers import E3aProviders
from bench.tasks.environment import PolicyKB
from som import Predicate


class Response:
    def __init__(self, data, output_text=""):
        self.data = data
        self.output_text = output_text

    def model_dump(self, **kwargs):
        return self.data.copy()


class OpenAIStub:
    def __init__(self):
        self.responses = self
        self.calls = []

    def create(self, **request):
        self.calls.append(request)
        usage = {"input_tokens": 1000, "output_tokens": 100, "input_tokens_details": {"cached_tokens": 200}}
        if "text" in request:
            return Response(
                {"usage": usage, "model": "gpt-6.1-terra"},
                json.dumps({"name": "route", "instructions": "Which route?", "true_means": "yes", "false_means": "no"}),
            )
        calls = [
            ("verify_identity", {"account_id": "acct"}),
            (
                "route_ticket",
                {
                    "department": "cards",
                    "priority": "normal",
                    "queue": "cards_queue",
                    "note": "policy",
                    "account_id": "acct",
                },
            ),
        ]
        return Response(
            {
                "model": "gpt-6.1-terra",
                "usage": usage,
                "output": [
                    {"type": "function_call", "name": name, "call_id": str(i), "arguments": json.dumps(args)}
                    for i, (name, args) in enumerate(calls)
                ],
            }
        )


def test_teacher_replays_same_agent_trace_and_account_specific_verification(tmp_path):
    client = OpenAIStub()
    budget = Budget({"openai": 55, "typesafe": 5})
    providers = E3aProviders("record", budget, cache_dir=tmp_path, openai_client=client)
    first = providers.teacher("ticket", "acct", PolicyKB())
    spent = budget.spent["openai"]
    again = providers.teacher("ticket", "other", PolicyKB())
    assert len(client.calls) == 1
    assert first.verified and not again.verified
    assert first.route["department"] == "cards"
    assert [step.tool for step in first.trace.steps] == ["verify_identity", "route_ticket"]
    assert first.envelope.cost.amount > 0
    assert again.envelope.cost.amount == first.envelope.cost.amount
    assert again.envelope.latency_ms == first.envelope.latency_ms
    assert budget.spent["openai"] == spent
    replay = E3aProviders("replay", Budget({"openai": 55, "typesafe": 5}), cache_dir=tmp_path)
    assert replay.teacher("ticket", "acct", PolicyKB()).verified
    with pytest.raises(CacheMiss):
        replay.teacher("missing", "acct", PolicyKB())


def test_writer_records_actual_usage_and_replays_without_credentials(tmp_path):
    client = OpenAIStub()
    budget = Budget({"openai": 55, "typesafe": 5})
    providers = E3aProviders("record", budget, cache_dir=tmp_path, openai_client=client)
    draft = providers.writer({"samples": [{"input": "x", "value": True}]})
    cost, latency = providers.writer.last_cost, providers.writer.last_latency_ms
    assert draft["name"] == "route"
    assert cost.usage.input_tokens == 1000
    assert cost.usage.cached_tokens == 200
    assert budget.spent["openai"] == cost.amount > 0
    replay_budget = Budget({"openai": 55, "typesafe": 5})
    replay = E3aProviders("replay", replay_budget, cache_dir=tmp_path)
    assert replay.writer({"samples": [{"input": "x", "value": True}]}) == draft
    assert replay.writer.last_cost.amount == cost.amount
    assert replay.writer.last_latency_ms == latency
    assert not replay_budget.spent
    assert len(client.calls) == 1


def test_choice_writer_requests_only_needed_fields_with_bounded_output(tmp_path):
    client = OpenAIStub()
    providers = E3aProviders("record", Budget({"openai": 55, "typesafe": 5}), cache_dir=tmp_path, openai_client=client)
    providers.writer({"samples": [{"input": "x", "value": "a"}], "choices": [{"value": "a"}]})
    request = client.calls[0]
    schema = request["text"]["format"]["schema"]
    assert schema["required"] == ["name", "instructions"]
    assert set(schema["properties"]) == {"name", "instructions"}
    assert request["max_output_tokens"] == 2048


def test_writer_retry_has_distinct_cache_identity_without_changing_prompt(tmp_path):
    client = OpenAIStub()
    budget = Budget({"openai": 55, "typesafe": 5})
    providers = E3aProviders("record", budget, cache_dir=tmp_path, openai_client=client)
    context = {"samples": [{"input": "x", "value": True}]}
    providers.writer(context)
    first_cost = budget.spent["openai"]
    providers.writer({**context, "_e3a_retry": 1})
    assert len(client.calls) == 2
    assert client.calls[0] == client.calls[1]
    assert budget.spent["openai"] == pytest.approx(2 * first_cost)
    providers.writer({**context, "_e3a_retry": 1})
    assert len(client.calls) == 2


def test_jev_new_spend_is_booked_once_and_replay_needs_no_key(tmp_path, monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "model": "jev-1.14.0",
                "usage": {"input_tokens": 1000, "output_tokens": 100},
                "answers": {"verify": {"type": "noul", "noul": 0.9}},
            },
        )

    budget = Budget({"openai": 55, "typesafe": 5})
    client = httpx.Client(transport=httpx.MockTransport(respond))
    providers = E3aProviders("record", budget, cache_dir=tmp_path, typesafe_client=client)
    question = Predicate("verify", "Verify identity?")
    result = providers.s1.decide("ticket", [question])
    assert budget.spent["typesafe"] == result.envelope.cost.amount > 0
    monkeypatch.delenv("TYPESAFE_API_KEY")
    replay_budget = Budget({"openai": 55, "typesafe": 5})
    replay = E3aProviders("replay", replay_budget, cache_dir=tmp_path)
    again = replay.s1.decide("ticket", [question])
    assert again["verify"] == result["verify"]
    assert again.envelope.cost.amount == result.envelope.cost.amount
    assert again.envelope.latency_ms == result.envelope.latency_ms
    assert len(calls) == 1 and not replay_budget.spent


def test_writer_stops_before_request_when_openai_reserve_is_exhausted(tmp_path):
    client = OpenAIStub()
    budget = Budget({"openai": 0.5, "typesafe": 5})
    providers = E3aProviders("record", budget, cache_dir=tmp_path, openai_client=client)
    with pytest.raises(RuntimeError, match="reserve exhausted"):
        providers.writer({"samples": []})
    assert not client.calls


def test_token_reservations_enforce_rolling_minute(monkeypatch):
    from bench.e3a import providers as module

    now = [0.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(module.time, "sleep", lambda delay: now.__setitem__(0, now[0] + delay))
    window = module._TokenWindow(limit=60)
    request = {"input": "x", "max_output_tokens": 1}
    window.acquire(request)
    assert now[0] == 0
    window.acquire(request)
    assert now[0] >= 60


def test_teacher_model_change_aborts_across_tickets(tmp_path):
    class ChangingClient(OpenAIStub):
        def create(self, **request):
            response = super().create(**request)
            if len(self.calls) > 1:
                response.data["model"] = "gpt-6.1-terra-other"
            return response

    providers = E3aProviders(
        "record", Budget({"openai": 55, "typesafe": 5}), cache_dir=tmp_path, openai_client=ChangingClient()
    )
    providers.teacher("first", "acct", PolicyKB())
    with pytest.raises(RuntimeError, match="teacher model changed"):
        providers.teacher("second", "acct", PolicyKB())
