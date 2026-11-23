import numpy as np
import pytest

from bench.e3a.promotion_grid import promote
from som.compile.lifecycle import CompiledDecision
from som.questions import ChoiceAnswer


@pytest.mark.parametrize("rule", ["margin", "upper_bound"])
@pytest.mark.parametrize("epsilon", [0.1, 0.15, 0.2])
def test_vectorized_promotion_matches_compiled_decision(rule, epsilon):
    rng = np.random.default_rng(123)
    for _ in range(25):
        scores = rng.choice([0.55, 0.7, 0.9, 1.0], size=100)
        errors = rng.random(100) < 0.12
        gate = CompiledDecision(epsilon=epsilon, alpha=0.0125, n_cal=50, n_val=50, audit_rate=1, tau_rule=rule)
        gate.start_shadow()
        for score, error in zip(scores, errors, strict=True):
            answer = ChoiceAnswer("entry", "a", {"a": score})
            reference = ChoiceAnswer("entry", "b" if error else "a")
            gate.observe_shadow(answer, reference)
        assert promote(scores, errors, 50, epsilon, rule) == gate.attempt_promotion().promoted
