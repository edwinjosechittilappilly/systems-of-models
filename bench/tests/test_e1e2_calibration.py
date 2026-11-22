"""Calibration keeps valid probability distributions and fits only supplied labels."""

import numpy as np
import pandas as pd
import pytest
from bench.e1_e2.analysis import score_items
from bench.e1_e2.calibration import apply_isotonic, apply_temperature, fit_isotonic, fit_temperature
from bench.e1_e2.revised import clinc_fit


def test_temperature_one_preserves_probabilities():
    p = np.array([[0.1, 0.9], [0.8, 0.2]])
    np.testing.assert_allclose(apply_temperature(p, 1.0), p)


def test_isotonic_handles_certain_top_class():
    p = np.array([[1.0, 0.0], [0.9, 0.1], [0.1, 0.9], [0.6, 0.4]])
    model = fit_isotonic(p, [0, 1, 1, 1])
    calibrated = apply_isotonic(p, model)
    assert np.isfinite(calibrated).all()
    np.testing.assert_allclose(calibrated.sum(axis=1), 1.0)


def test_temperature_rejects_missing_mass():
    with pytest.raises(ValueError, match="positive mass"):
        fit_temperature([[0.0, 0.0]], [0])


def test_calibration_item_statistics_are_auditable():
    items = pd.DataFrame({"item_id": [9], "gold": ["a"]})
    result = score_items(items, np.array([[0.8, 0.2]]), np.array([0]), "banking77", "typesafe", "choice", "raw")
    assert result.loc[0, "item_id"] == 9
    assert result.loc[0, "brier"] == pytest.approx(0.08)
    assert result.loc[0, "nll"] == pytest.approx(-np.log(0.8))


def test_companion_predicate_contains_its_own_intent_list():
    jev = clinc_fit("typesafe")
    decisions = clinc_fit("decisions")
    assert isinstance(jev.instructions, dict)
    assert len(jev.instructions["intents"]) == 150
    assert all(intent in decisions.instructions for intent in jev.instructions["intents"])
