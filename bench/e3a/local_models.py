"""Cached local embeddings and warm-up-only nearest-neighbour baseline.

Embedding and surrogate measurements replay original local execution times,
not the much shorter cache lookup time. They are not dollar charges: hardware
and energy costs are not estimated.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from bench.common.cache import JsonCache, request_key
from som.compile import EmbeddingSurrogate, ollama_embedder
from som.questions import Question
from som.systems import Decision, Input

EMBEDDING_NAMESPACE = "e3a_embedding_embeddinggemma_v1"
SURROGATE_TIMING_NAMESPACE = "e3a_surrogate_timings_v1"


@dataclass(frozen=True)
class EmbeddingMeasurement:
    latency_ms: float = 0.0
    cpu_seconds: float = 0.0
    server_duration_ns: int = 0
    prompt_eval_count: int = 0
    cost_usd: float = 0.0


class CachedEmbedder:
    """Cache each model/text pair independently, allowing offline batch replay.

    ``last_measurement`` is the sum of the original measurements for each
    requested text, including cache hits. CPU covers only the Python process;
    Ollama server elapsed time is reported separately and is not CPU time.
    """

    def __init__(
        self,
        cache: JsonCache,
        *,
        model: str = "embeddinggemma",
        embed: Callable[[Sequence[str]], Sequence[Sequence[float]]] | None = None,
    ) -> None:
        if not model:
            raise ValueError("model must not be empty")
        self.cache = cache
        self.model = model
        self.embed = embed if embed is not None else ollama_embedder(model)
        self.timing_cache = JsonCache(SURROGATE_TIMING_NAMESPACE, mode=cache.mode, directory=cache.path.parent)
        self.last_measurement = EmbeddingMeasurement()
        self.last_elapsed_ms = 0.0
        self.last_cpu_seconds = 0.0

    def __call__(self, texts: Sequence[str]) -> list[list[float]]:
        started, cpu_started = time.perf_counter(), time.process_time()
        vectors: list[list[float]] = []
        latency = cpu = 0.0
        duration = tokens = 0
        for text in texts:
            def call() -> dict[str, Any]:
                started, cpu_started = time.perf_counter(), time.process_time()
                if hasattr(self.embed, "with_metadata"):
                    rows, metadata = self.embed.with_metadata([text])
                else:
                    rows, metadata = self.embed([text]), {}
                elapsed = (time.perf_counter() - started) * 1000
                cpu_elapsed = time.process_time() - cpu_started
                vector = _validated_vector(rows, 1)[0]
                return {"vector": vector, "latency_ms": elapsed, "cpu_seconds": cpu_elapsed,
                        "server_duration_ns": int(metadata.get("total_duration", 0)),
                        "prompt_eval_count": int(metadata.get("prompt_eval_count", 0))}

            record = self.cache.get_or_call({"model": self.model, "text": text}, call)
            vectors.append(_validated_vector([record["vector"]], 1)[0])
            latency += record["latency_ms"]
            cpu += record["cpu_seconds"]
            duration += record["server_duration_ns"]
            tokens += record["prompt_eval_count"]
        if vectors and any(len(row) != len(vectors[0]) for row in vectors):
            raise ValueError("embedding vectors must have the same dimension")
        self.last_measurement = EmbeddingMeasurement(latency, cpu, duration, tokens)
        self.last_elapsed_ms = (time.perf_counter() - started) * 1000
        self.last_cpu_seconds = time.process_time() - cpu_started
        return vectors


def _validated_vector(rows: Sequence[Sequence[float]], count: int) -> list[list[float]]:
    if len(rows) != count:
        raise ValueError("embedder must return one vector per input")
    result = []
    for row in rows:
        if not row or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in row):
            raise ValueError("embedding must contain finite numbers")
        result.append([float(v) for v in row])
    return result


class _MeasuredSurrogate(EmbeddingSurrogate):
    """Recompute predictions but replay the original measured execution times."""

    def __init__(self, embedder: CachedEmbedder, classes: Sequence[str]) -> None:
        super().__init__(embedder, classes, name=f"ollama/{embedder.model}-logistic")
        self._embedder = embedder
        self._timings = embedder.timing_cache
        self._fit_key: str | None = None

    def _record_timing(self, key: dict[str, Any], latency: float, cpu: float) -> dict[str, float]:
        measurement = self._embedder.last_measurement
        return self._timings.get_or_call(
            key,
            lambda: {
                "latency_ms": max(0.0, latency - self._embedder.last_elapsed_ms + measurement.latency_ms),
                "cpu_seconds": max(0.0, cpu - self._embedder.last_cpu_seconds + measurement.cpu_seconds),
            },
        )

    def fit(self, inputs: Sequence[Input], labels: Sequence[str]) -> _MeasuredSurrogate:
        key = {"operation": "fit", "model": self._embedder.model, "classes": self.classes,
               "inputs": inputs, "labels": labels}
        super().fit(inputs, labels)
        timing = self._record_timing(key, float(self.fit_metadata["latency_ms"]),
                                     float(self.fit_metadata["cpu_seconds"]))
        self.fit_metadata.update(latency_ms=str(timing["latency_ms"]), cpu_seconds=str(timing["cpu_seconds"]))
        self._fit_key = request_key(key)
        return self

    def decide(self, input: Input, questions: Sequence[Question], *, trace_id: str | None = None) -> Decision:
        decision = super().decide(input, questions, trace_id=trace_id)
        key = {"operation": "decide", "fit": self._fit_key, "input": input,
               "questions": [question.to_contract() for question in questions]}
        timing = self._record_timing(key, decision.envelope.latency_ms,
                                     float(decision.envelope.metadata["cpu_seconds"]))
        decision.envelope.latency_ms = timing["latency_ms"]
        decision.envelope.metadata["cpu_seconds"] = str(timing["cpu_seconds"])
        return decision


def make_surrogate(embedder: CachedEmbedder, classes: Sequence[str]) -> EmbeddingSurrogate:
    """Construct the library classifier with record/replay of local timing only."""
    return _MeasuredSurrogate(embedder, classes)


@dataclass(frozen=True)
class KnnPrediction:
    label: str | None
    similarity: float | None
    served: bool
    latency_ms: float
    cpu_seconds: float


class KnnCache:
    """1-NN cache with a threshold selected solely from sequential warm-up.

    Each warm-up example is scored against *earlier* examples only; the lowest
    observed similarity with empirical error <= epsilon is chosen. This is a
    tuning rule, not a statistical risk guarantee. Subsequent teacher-labelled
    examples can be added without retuning. Invalidation permanently disables
    serving until a new warm-up fit is explicitly supplied.
    """

    def __init__(self, embedder: CachedEmbedder, *, epsilon: float) -> None:
        if not 0 < epsilon < 1:
            raise ValueError("epsilon must lie strictly between 0 and 1")
        self.embedder = embedder
        self.epsilon = epsilon
        self.threshold: float | None = None
        self._entries: list[tuple[list[float], str]] = []
        self.fit_latency_ms = 0.0
        self.fit_cpu_seconds = 0.0
        self._state = request_key({"model": embedder.model, "epsilon": epsilon, "entries": []})

    def _nearest(self, vector: list[float]) -> tuple[str | None, float | None]:
        norm = math.sqrt(sum(x * x for x in vector))
        if not norm:
            return None, None
        best_label, best_score = None, None
        for other, label in self._entries:
            if len(vector) != len(other):
                raise ValueError("embedding dimension differs from cache")
            other_norm = math.sqrt(sum(x * x for x in other))
            if not other_norm:
                continue
            score = sum(x * y for x, y in zip(vector, other, strict=True)) / (norm * other_norm)
            score = max(-1.0, min(1.0, score))
            if best_score is None or score > best_score:
                best_label, best_score = label, score
        return best_label, best_score

    def fit_warmup(self, texts: Sequence[str], labels: Sequence[str]) -> float | None:
        if len(texts) != len(labels) or not texts:
            raise ValueError("warm-up texts and labels must be nonempty and equal length")
        if any(not isinstance(label, str) for label in labels):
            raise ValueError("labels must be strings")
        started, cpu_started = time.perf_counter(), time.process_time()
        vectors = self.embedder(texts)
        embedding_wall = (time.perf_counter() - started) * 1000
        embedding_cpu = time.process_time() - cpu_started
        self._entries = []
        observations: list[tuple[float, bool]] = []
        for vector, label in zip(vectors, labels, strict=True):
            predicted, similarity = self._nearest(vector)
            if similarity is not None:
                observations.append((similarity, predicted != label))
            self._entries.append((vector, label))
        self.threshold = None
        for threshold in sorted({score for score, _ in observations}):
            selected = [error for score, error in observations if score >= threshold]
            if sum(selected) / len(selected) <= self.epsilon:
                self.threshold = threshold
                break
        latency = (time.perf_counter() - started) * 1000 - embedding_wall + self.embedder.last_measurement.latency_ms
        cpu = time.process_time() - cpu_started - embedding_cpu + self.embedder.last_measurement.cpu_seconds
        key = {"operation": "knn_fit", "model": self.embedder.model, "epsilon": self.epsilon,
               "texts": texts, "labels": labels}
        timing = self.embedder.timing_cache.get_or_call(key, lambda: {"latency_ms": latency, "cpu_seconds": cpu})
        self.fit_latency_ms, self.fit_cpu_seconds = timing["latency_ms"], timing["cpu_seconds"]
        self._state = request_key(key)
        return self.threshold

    def predict(self, text: str) -> KnnPrediction:
        started, cpu_started = time.perf_counter(), time.process_time()
        vector = self.embedder([text])[0]
        embedding_wall = (time.perf_counter() - started) * 1000
        embedding_cpu = time.process_time() - cpu_started
        label, similarity = self._nearest(vector)
        latency = (time.perf_counter() - started) * 1000 - embedding_wall + self.embedder.last_measurement.latency_ms
        cpu = time.process_time() - cpu_started - embedding_cpu + self.embedder.last_measurement.cpu_seconds
        key = {"operation": "knn_predict", "state": self._state, "text": text}
        timing = self.embedder.timing_cache.get_or_call(key, lambda: {"latency_ms": latency, "cpu_seconds": cpu})
        return KnnPrediction(
            label, similarity,
            self.threshold is not None and similarity is not None and similarity >= self.threshold,
            timing["latency_ms"], timing["cpu_seconds"],
        )

    def add(self, text: str, label: str) -> None:
        if not isinstance(label, str):
            raise ValueError("label must be a string")
        vector = self.embedder([text])[0]
        if self._entries and len(vector) != len(self._entries[0][0]):
            raise ValueError("embedding dimension differs from cache")
        self._entries.append((vector, label))
        self._state = request_key({"previous": self._state, "text": text, "label": label})

    def invalidate(self) -> None:
        self._entries.clear()
        self.threshold = None
        self._state = request_key({"model": self.embedder.model, "epsilon": self.epsilon, "entries": []})
