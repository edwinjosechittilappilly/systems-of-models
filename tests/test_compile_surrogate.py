import json

import httpx
import pytest

from som import Choice, Predicate
from som.compile.surrogate import EmbeddingSurrogate, ollama_embedder
from som.systems import Decider

QUESTION = Choice("route", "Which team?", ["billing", "cards"])


def embed(texts):
    return [[float("bill" in text), float("card" in text)] for text in texts]


def trained():
    pytest.importorskip("sklearn")
    return EmbeddingSurrogate(embed, ["billing", "cards"]).fit(
        ["bill", "billing", "card", "cards"], ["billing", "billing", "cards", "cards"]
    )


def test_classifier_returns_choice_probabilities_and_valid_envelope():
    model = trained()
    assert isinstance(model, Decider)
    decision = model.decide("billing", [QUESTION], trace_id="1" * 32)
    answer = decision["route"]
    assert answer.value == "billing"
    assert set(answer.probabilities) == {"billing", "cards"}
    assert sum(answer.probabilities.values()) == pytest.approx(1)
    assert answer.probabilities["billing"] > answer.probabilities["cards"]
    assert decision.envelope.trace_ref.trace_id == "1" * 32
    assert decision.envelope.cost.basis == "local_measured"
    assert decision.envelope.cost.amount == 0
    assert model.fit_cost.basis == "local_measured"
    assert model.fit_cost.amount == 0
    assert float(model.fit_metadata["latency_ms"]) >= 0
    assert "total_duration" not in decision.envelope.metadata
    assert float(decision.envelope.metadata["cpu_seconds"]) >= 0
    assert decision.envelope.metadata["cpu_scope"] == "current_process"
    decision.envelope.validate()


def test_classifier_validates_inputs_and_question_space():
    model = EmbeddingSurrogate(embed, ["billing", "cards"])
    with pytest.raises(RuntimeError, match="fitted"):
        model.decide("card", [QUESTION])
    with pytest.raises(ValueError, match="equal length"):
        model.fit(["card"], [])
    with pytest.raises(ValueError, match="classes"):
        model.fit(["bill", "card"], ["billing", "other"])
    with pytest.raises(ValueError, match="distinct labels"):
        model.fit(["bill", "bill"], ["billing", "billing"])
    model = trained()
    with pytest.raises(ValueError, match="choice question"):
        model.decide("bill", [Predicate("route", "Billing?")])
    with pytest.raises(ValueError, match="choice question"):
        model.decide("bill", [Choice("route", "Which?", ["billing", "other"])])


def test_invalid_embedding_and_failed_refit_preserves_previous_model():
    model = trained()
    model.embed = lambda texts: [[1.0, float("nan")] for _ in texts]
    with pytest.raises(ValueError, match="finite"):
        model.fit(["bill", "card"], ["billing", "cards"])
    model.embed = embed
    assert model.decide("bill", [QUESTION])["route"].value == "billing"
    model.embed = lambda texts: [[1.0] for _ in texts]
    with pytest.raises(ValueError, match="dimension"):
        model.decide("bill", [QUESTION])


def test_sklearn_is_imported_only_when_fitting(monkeypatch):
    import som.compile.surrogate as surrogate

    original = surrogate.importlib.import_module

    def missing(name, *args, **kwargs):
        if name == "sklearn.linear_model":
            raise ImportError("no sklearn")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(surrogate.importlib, "import_module", missing)
    model = EmbeddingSurrogate(embed, ["billing", "cards"])
    with pytest.raises(ImportError, match="scikit-learn"):
        model.fit(["bill", "card"], ["billing", "cards"])


def test_ollama_batch_request_and_response_are_offline():
    def respond(request):
        assert str(request.url) == "http://localhost:11434/api/embed"
        assert json.loads(request.content) == {"model": "nomic", "input": ["one", "two"]}
        return httpx.Response(200, json={"embeddings": [[1, 2], [3, 4]]})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        embedder = ollama_embedder("nomic", client=client)
        assert embedder([]) == []
        assert embedder(["one", "two"]) == [[1.0, 2.0], [3.0, 4.0]]


def test_ollama_fit_and_decisions_account_for_each_response():
    pytest.importorskip("sklearn")
    responses = iter([(1000, 20), (2000, 3), (None, None), (4000, 5)])

    def respond(request):
        duration, tokens = next(responses)
        texts = json.loads(request.content)["input"]
        payload = {"embeddings": embed(texts)}
        if duration is not None:
            payload.update(total_duration=duration, prompt_eval_count=tokens)
        return httpx.Response(200, json=payload)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        model = EmbeddingSurrogate(ollama_embedder("nomic", client=client), ["billing", "cards"])
        assert model.fit_cost is None
        model.fit(["bill", "card"], ["billing", "cards"])
        assert model.fit_cost.basis == "local_measured"
        assert model.fit_cost.usage.input_tokens == 20
        assert model.fit_metadata["total_duration"] == "1000"
        assert model.fit_metadata["prompt_eval_count"] == "20"
        assert float(model.fit_metadata["cpu_seconds"]) >= 0
        first = model.decide("bill", [QUESTION]).envelope
        second = model.decide("card", [QUESTION]).envelope
        third = model.decide("bill", [QUESTION]).envelope
        assert first.cost.usage.input_tokens == 3
        assert first.metadata["total_duration"] == "2000"
        assert first.metadata["prompt_eval_count"] == "3"
        assert second.cost.usage.input_tokens == 0
        assert "total_duration" not in second.metadata
        assert "prompt_eval_count" not in second.metadata
        assert third.cost.usage.input_tokens == 5
        assert third.metadata["total_duration"] == "4000"
        assert first.metadata["total_duration"] == "2000"
        assert model.fit_metadata["total_duration"] == "1000"
        first.validate()


@pytest.mark.parametrize(("key", "value"), [("total_duration", -1), ("prompt_eval_count", True)])
def test_ollama_rejects_invalid_accounting(key, value):
    payload = {"embeddings": [[1, 2]], key: value}
    with (
        httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))) as client,
        pytest.raises(ValueError, match=key),
    ):
        ollama_embedder("nomic", client=client)(["one"])


@pytest.mark.parametrize("payload", [{}, {"embeddings": []}, {"embeddings": [[1, 2], [3]]}])
def test_ollama_rejects_malformed_embeddings(payload):
    with (
        httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))) as client,
        pytest.raises(ValueError, match="embed"),
    ):
        ollama_embedder("nomic", client=client)(["one", "two"])


def test_ollama_propagates_http_errors():
    with (
        httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(503))) as client,
        pytest.raises(httpx.HTTPStatusError),
    ):
        ollama_embedder("nomic", client=client)(["one"])
