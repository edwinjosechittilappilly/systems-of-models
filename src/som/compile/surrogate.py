"""A local embedding classifier implementing the System 1 decider interface.

The classifier is trained for a fixed choice space. Embedding and model
training are explicit; importing this module does not require scikit-learn.
"""

from __future__ import annotations

import importlib
import math
import time
from collections.abc import Callable, Sequence
from numbers import Real
from typing import Any

import httpx

from som.adapters._common import render_input
from som.envelope import Cost, Envelope, Implementation, SystemId
from som.questions import Choice, ChoiceAnswer, Question
from som.systems import Decision, Input
from som.trace import span

Embedder = Callable[[Sequence[str]], Sequence[Sequence[float]]]


def ollama_embedder(
    model: str,
    *,
    base_url: str = "http://localhost:11434",
    client: httpx.Client | None = None,
    timeout: float = 60.0,
) -> Embedder:
    """Return a batch embedder using Ollama's native ``/api/embed`` endpoint.

    An injected client remains owned by its caller. HTTP and malformed-response
    errors propagate rather than being converted to empty embeddings.
    """
    if not model:
        raise ValueError("model must not be empty")
    url = f"{base_url.rstrip('/')}/api/embed"

    def embed(texts: Sequence[str]) -> Sequence[Sequence[float]]:
        if not texts:
            return []
        if client is None:
            response = httpx.post(url, json={"model": model, "input": list(texts)}, timeout=timeout)
        else:
            response = client.post(url, json={"model": model, "input": list(texts)}, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or "embeddings" not in payload:
            raise ValueError("Ollama response does not contain embeddings")
        return _vectors(payload["embeddings"], len(texts))

    return embed


def _vectors(vectors: Any, count: int) -> list[list[float]]:
    if isinstance(vectors, (str, bytes, dict)):
        raise ValueError("embedder must return one vector per input")
    try:
        rows = list(vectors)
    except TypeError as exc:
        raise ValueError("embedder must return one vector per input") from exc
    if len(rows) != count:
        raise ValueError("embedder must return one vector per input")
    result: list[list[float]] = []
    dimension: int | None = None
    for vector in rows:
        if isinstance(vector, (str, bytes, dict)):
            raise ValueError("embedding vectors must be nonempty sequences")
        try:
            values = list(vector)
        except TypeError as exc:
            raise ValueError("embedding vectors must be nonempty sequences") from exc
        if not values:
            raise ValueError("embedding vectors must be nonempty sequences")
        if dimension is None:
            dimension = len(values)
        if len(values) != dimension:
            raise ValueError("embedding vectors must have the same dimension")
        if any(isinstance(x, bool) or not isinstance(x, Real) or not math.isfinite(x) for x in values):
            raise ValueError("embedding values must be finite numbers")
        result.append([float(x) for x in values])
    return result


class EmbeddingSurrogate:
    """Logistic-regression choice decider trained on examples for fixed classes.

    ``embed`` receives a batch of rendered inputs and returns one numeric
    vector per input. CPU time covers this Python process only; it cannot
    measure a separate embedding server or establish a dollar cost.
    """

    system: SystemId = "s1.decision"

    def __init__(self, embed: Embedder, classes: Sequence[str], *, name: str = "local/embedding-logistic") -> None:
        if (
            isinstance(classes, (str, bytes))
            or len(classes) < 2
            or any(not isinstance(label, str) for label in classes)
            or len(set(classes)) != len(classes)
        ):
            raise ValueError("classes must contain at least two distinct strings")
        self.classes = tuple(classes)
        self.embed = embed
        self.name = name
        self._model: Any = None
        self._dimension: int | None = None

    def fit(self, inputs: Sequence[Input], labels: Sequence[str]) -> EmbeddingSurrogate:
        """Fit from input/choice-label pairs, replacing the model only on success."""
        if len(inputs) != len(labels) or not inputs:
            raise ValueError("inputs and labels must be nonempty and have equal length")
        if any(label not in self.classes for label in labels):
            raise ValueError("training label is outside the declared classes")
        if len(set(labels)) < 2:
            raise ValueError("training requires at least two distinct labels")
        try:
            linear_model = importlib.import_module("sklearn.linear_model")
        except ImportError as exc:
            raise ImportError("EmbeddingSurrogate requires scikit-learn; install scikit-learn to train it") from exc
        vectors = _vectors(self.embed([render_input(value) for value in inputs]), len(inputs))
        model = linear_model.LogisticRegression(max_iter=1000, random_state=0)
        model.fit(vectors, list(labels))
        self._model, self._dimension = model, len(vectors[0])
        return self

    def decide(self, input: Input, questions: Sequence[Question], *, trace_id: str | None = None) -> Decision:
        if self._model is None:
            raise RuntimeError("EmbeddingSurrogate must be fitted before deciding")
        if len(questions) != 1 or not isinstance(questions[0], Choice) or set(questions[0].values) != set(self.classes):
            raise ValueError("surrogate requires one choice question matching its trained classes")
        question = questions[0]
        started = time.perf_counter()
        cpu_started = time.process_time()
        with span(f"decide {self.name}", trace_id=trace_id) as ref:
            vector = _vectors(self.embed([render_input(input)]), 1)[0]
            if len(vector) != self._dimension:
                raise ValueError("embedding dimension differs from training")
            probabilities = {value: 0.0 for value in question.values}
            probabilities.update(
                (str(label), float(probability))
                for label, probability in zip(self._model.classes_, self._model.predict_proba([vector])[0], strict=True)
            )
            selected = max(probabilities, key=probabilities.__getitem__)
            answer = ChoiceAnswer(question.name, selected, probabilities, confidence=probabilities[selected])
            provider, _, model_name = self.name.partition("/")
            envelope = Envelope(
                system="s1.decision",
                body={"answers": [answer.to_contract()]},
                cost=Cost.unknown(),
                latency_ms=(time.perf_counter() - started) * 1000,
                trace_ref=ref,
                confidence=answer.top_probability,
                confidence_basis="model_probability",
                implementation=Implementation(provider=provider, model=model_name or provider),
                metadata={"cpu_seconds": str(time.process_time() - cpu_started), "cpu_scope": "current_process"},
            )
        return Decision(envelope=envelope, answers={answer.name: answer})
