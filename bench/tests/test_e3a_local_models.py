"""Offline coverage of the E3a local model interfaces."""

import pytest

from bench.common.cache import CacheMiss, JsonCache
from bench.e3a.local_models import EMBEDDING_NAMESPACE, CachedEmbedder, KnnCache, make_surrogate
from som.questions import Choice


def test_embeddings_are_cached_per_text_and_replayed_with_original_accounting(tmp_path):
    calls = []

    class Embed:
        def with_metadata(self, texts):
            calls.extend(texts)
            return [[float(len(texts[0])), 1.0]], {"total_duration": "42", "prompt_eval_count": "3"}

        def __call__(self, texts):
            raise AssertionError("metadata path expected")

    cache = JsonCache(EMBEDDING_NAMESPACE, mode="record", directory=tmp_path)
    embed = CachedEmbedder(cache, embed=Embed())
    assert embed(["one", "two"]) == [[3.0, 1.0], [3.0, 1.0]]
    original = embed.last_measurement
    assert calls == ["one", "two"]
    assert original.server_duration_ns == 84
    assert original.prompt_eval_count == 6
    assert original.cost_usd == 0

    def no_network(_texts):
        raise AssertionError("replay must not call Ollama")

    replay = CachedEmbedder(JsonCache(EMBEDDING_NAMESPACE, mode="replay", directory=tmp_path), embed=no_network)
    assert replay(["two", "one"]) == [[3.0, 1.0], [3.0, 1.0]]
    assert replay.last_measurement == original
    with pytest.raises(CacheMiss):
        replay(["not recorded"])
    with pytest.raises(CacheMiss):
        CachedEmbedder(
            JsonCache(EMBEDDING_NAMESPACE, mode="replay", directory=tmp_path), model="another-model", embed=no_network
        )(["one"])


def test_surrogate_trains_on_teacher_labels_and_replays_offline(tmp_path):
    pytest.importorskip("sklearn")

    def vectors(texts):
        return [[1.0, 0.0] if "billing" in text else [0.0, 1.0] for text in texts]

    texts = ["billing one", "billing two", "cards one", "cards two"]
    labels = ["billing", "billing", "cards", "cards"]
    cache = JsonCache(EMBEDDING_NAMESPACE, mode="record", directory=tmp_path)
    embed = CachedEmbedder(cache, embed=vectors)
    model = make_surrogate(embed, ["billing", "cards"]).fit(texts, labels)
    question = Choice("route", "Which team?", ["billing", "cards"])
    decision = model.decide("billing one", [question])
    assert decision.answers["route"].value == "billing"
    assert model.fit_metadata["cpu_scope"] == "current_process"
    replay = CachedEmbedder(
        JsonCache(EMBEDDING_NAMESPACE, mode="replay", directory=tmp_path),
        embed=lambda _: pytest.fail("unexpected network call"),
    )
    restored = make_surrogate(replay, ["billing", "cards"]).fit(texts, labels)
    replayed = restored.decide("billing one", [question])
    assert replayed.answers["route"].probabilities == decision.answers["route"].probabilities
    assert replayed.envelope.latency_ms == decision.envelope.latency_ms
    assert replayed.envelope.metadata["cpu_seconds"] == decision.envelope.metadata["cpu_seconds"]
    assert restored.fit_metadata["latency_ms"] == model.fit_metadata["latency_ms"]
    assert restored.fit_metadata["cpu_seconds"] == model.fit_metadata["cpu_seconds"]
    with pytest.raises(CacheMiss):
        restored.decide("billing two", [question])


def test_knn_uses_prior_warmup_only_and_invalidation_disables_serving(tmp_path):
    vectors = {"a": [1.0, 0.0], "b": [0.8, 0.6], "c": [1.0, 0.0], "d": [0.0, 1.0]}
    embed = CachedEmbedder(
        JsonCache(EMBEDDING_NAMESPACE, directory=tmp_path), embed=lambda texts: [vectors[text] for text in texts]
    )
    knn = KnnCache(embed, epsilon=0.2)
    # b disagrees with a at 0.8; c agrees with a at 1.0.
    assert knn.fit_warmup(["a", "b", "c"], ["A", "B", "A"]) == pytest.approx(1.0)
    assert knn.predict("a").served
    knn.add("d", "D")
    prediction = knn.predict("d")
    assert prediction.served and prediction.label == "D"
    assert prediction.latency_ms >= 0 and prediction.cpu_seconds >= 0
    assert knn.threshold == pytest.approx(1.0)
    knn.invalidate()
    assert not knn.predict("a").served
    knn.add("a", "A")
    assert not knn.predict("a").served


def test_knn_no_threshold_when_warmup_has_only_errors_or_zero_vectors(tmp_path):
    vectors = {"a": [1.0, 0.0], "b": [1.0, 0.0], "zero": [0.0, 0.0]}
    embed = CachedEmbedder(
        JsonCache(EMBEDDING_NAMESPACE, directory=tmp_path), embed=lambda texts: [vectors[text] for text in texts]
    )
    knn = KnnCache(embed, epsilon=0.1)
    assert knn.fit_warmup(["a", "b"], ["A", "B"]) is None
    assert not knn.predict("a").served
    assert knn.fit_warmup(["zero", "a"], ["A", "A"]) is None
    assert not knn.predict("zero").served


def test_knn_replays_full_local_timing_while_recomputing_predictions(tmp_path):
    vectors = {"a": [1.0, 0.0], "b": [0.8, 0.6], "c": [1.0, 0.0]}
    embed = CachedEmbedder(
        JsonCache(EMBEDDING_NAMESPACE, directory=tmp_path),
        embed=lambda texts: [vectors[text] for text in texts],
    )
    first = KnnCache(embed, epsilon=0.2)
    first.fit_warmup(["a", "b", "c"], ["A", "B", "A"])
    result = first.predict("a")
    replay = CachedEmbedder(
        JsonCache(EMBEDDING_NAMESPACE, mode="replay", directory=tmp_path),
        embed=lambda _: pytest.fail("unexpected network call"),
    )
    second = KnnCache(replay, epsilon=0.2)
    second.fit_warmup(["a", "b", "c"], ["A", "B", "A"])
    assert (second.fit_latency_ms, second.fit_cpu_seconds) == (first.fit_latency_ms, first.fit_cpu_seconds)
    assert second.predict("a") == result
