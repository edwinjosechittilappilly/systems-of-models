import numpy as np
import pytest

import som
from bench.common import stats
from bench.common.budget import Budget, BudgetExceeded
from bench.common.cache import CachedDecider, CacheMiss, JsonCache
from som.testing import FunctionDecider

TEAM = som.Choice("team", "Which team?", ["billing", "cards"])


def decider() -> FunctionDecider:
    return FunctionDecider(
        lambda _i, q: som.ChoiceAnswer(q.name, "cards", {"billing": 0.2, "cards": 0.8}, 0.6),
        name="test/s1",
        cost_per_call=0.001,
        latency_ms=12.0,
    )


def test_cache_records_once_and_replays_identically(tmp_path):
    inner = decider()
    first = CachedDecider(inner, JsonCache("unit", mode="record", directory=tmp_path)).decide("x", [TEAM])
    replay = CachedDecider(inner, JsonCache("unit", mode="replay", directory=tmp_path)).decide("x", [TEAM])
    assert inner.calls == 1
    assert replay["team"] == first["team"]
    assert (replay.envelope.cost.amount, replay.envelope.latency_ms) == (0.001, 12.0)
    replay.envelope.validate()


def test_replay_refuses_to_call_the_network(tmp_path):
    with pytest.raises(CacheMiss):
        CachedDecider(decider(), JsonCache("unit", mode="replay", directory=tmp_path)).decide("new", [TEAM])


def test_cache_samples_are_independent_recordings(tmp_path):
    inner = decider()
    cached = CachedDecider(inner, JsonCache("unit", mode="record", directory=tmp_path))
    cached.decide("x", [TEAM], sample=0)
    cached.decide("x", [TEAM], sample=1)
    cached.decide("x", [TEAM], sample=1)
    assert inner.calls == 2


def test_budget_stops_new_spend_at_the_cap():
    budget = Budget({"openai": 0.01})
    budget.charge("openai", 0.006)
    with pytest.raises(BudgetExceeded):
        budget.charge("openai", 0.006)


def test_risk_coverage_and_aurc_rank_confident_errors_as_worse():
    correct = [True, True, False, False]
    good_signal = [0.9, 0.8, 0.2, 0.1]
    bad_signal = [0.1, 0.2, 0.8, 0.9]
    assert stats.aurc(good_signal, correct) < stats.aurc(bad_signal, correct)
    coverage, risk = stats.risk_coverage(good_signal, correct)
    assert coverage[-1] == 1.0
    assert risk[-1] == 0.5


def test_ece_is_zero_when_confidence_matches_accuracy():
    confidence = [0.75] * 40
    correct = [True] * 30 + [False] * 10
    assert stats.ece(confidence, correct, bins=1) == pytest.approx(0.0)


def test_wilson_and_clopper_pearson_bounds():
    low, high = stats.wilson(50, 100)
    assert low < 0.5 < high
    assert stats.clopper_pearson_upper(0, 100) == pytest.approx(1 - 0.05 ** (1 / 100), rel=1e-6)


def test_auroc_and_brier():
    assert stats.auroc([0.9, 0.8, 0.1], [True, True, False]) == 1.0
    probs = np.array([[1.0, 0.0], [0.0, 1.0]])
    assert stats.brier(probs, [0, 1]) == 0.0
