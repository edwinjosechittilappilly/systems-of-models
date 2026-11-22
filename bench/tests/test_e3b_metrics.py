import math

import numpy as np
import pytest

from bench.e3b import metrics


def test_discovery_counts_unique_identifiers_and_undefined_denominators():
    result = metrics.discovery_metrics(["a", "a", "b"], ["a", "c", "c"])
    assert result == {"tp": 1, "fp": 1, "fn": 1, "precision": 0.5, "recall": 0.5}
    empty = metrics.discovery_metrics([], [])
    assert (empty["tp"], empty["fp"], empty["fn"]) == (0, 0, 0)
    assert math.isnan(empty["precision"]) and math.isnan(empty["recall"])
    assert metrics.discovery_metrics(["a"], [])["precision"] == 0


def test_threshold_calibration_uses_whole_ties_and_can_recover_after_failure():
    assert metrics.calibrate_threshold([0.9, 0.9], [True, False]) == math.inf
    # One error among the top two fails, but one error among twenty meets 5%.
    assert metrics.calibrate_threshold([0.9, 0.8] + [0.7] * 18, [True, False] + [True] * 18) == 0.7
    assert metrics.calibrate_threshold([], []) == math.inf
    assert metrics.calibrate_threshold([0.9], [False]) == math.inf
    assert metrics.calibrate_threshold([0.9], [True]) == 0.9


def test_tied_risk_curve_and_step_aurc_are_order_independent():
    confidence = [0.9, 0.9, 0.4, 0.1]
    coverage, risk = metrics.risk_coverage(confidence, [True, False, True, False])
    np.testing.assert_allclose(coverage, [0.5, 0.75, 1])
    np.testing.assert_allclose(risk, [0.5, 1 / 3, 0.5])
    assert metrics.aurc(confidence, [True, False, True, False]) == pytest.approx(11 / 24)
    assert metrics.aurc(confidence, [False, True, True, False]) == pytest.approx(11 / 24)
    assert math.isnan(metrics.aurc([], []))
    assert len(metrics.risk_coverage([], [])[0]) == 0


def test_wilson_and_cluster_bootstrap_intervals():
    assert metrics.wilson(50, 100) == pytest.approx((0.4038315, 0.5961685))
    assert all(math.isnan(x) for x in metrics.wilson(0, 0))
    assert metrics.cluster_bootstrap([1, 1, 1], ["a", "a", "b"], resamples=100) == (1, 1)
    # Within-cluster values never separate: every resample has mean exactly 1/2.
    assert metrics.cluster_bootstrap([0, 1, 0, 1], ["a", "a", "b", "b"], resamples=100) == (0.5, 0.5)
    assert all(math.isnan(x) for x in metrics.cluster_bootstrap([], []))
    assert metrics.cluster_bootstrap([0, 1], ["a", "b"], seed=7) == metrics.cluster_bootstrap(
        [0, 1], ["a", "b"], seed=7
    )


def test_aurc_bootstrap_resamples_whole_tasks_and_handles_empty_data():
    # Both clusters have the same ordered outcomes; every resample has AURC 1/4.
    interval = metrics.aurc_cluster_bootstrap(
        [0.9, 0.1, 0.9, 0.1],
        [True, False, True, False],
        ["a", "a", "b", "b"],
        resamples=100,
        seed=3,
    )
    assert interval == pytest.approx((0.25, 0.25))
    assert all(math.isnan(x) for x in metrics.aurc_cluster_bootstrap([], [], []))
    with pytest.raises(ValueError, match="same length"):
        metrics.aurc_cluster_bootstrap([0.9], [True], [])
    with pytest.raises(ValueError, match="same length"):
        metrics.aurc_cluster_bootstrap([0.9], [], ["a"])


def test_summary_counts_refusals_and_missing_labels_separately():
    result = metrics.summary_metrics(
        ["a", None, "b", "a"],
        ["a", "a", "b", None],
        ["b", "a", None, "a"],
        ["x", "x", "y", "z"],
        training_majority="b",
        resamples=100,
    )
    assert (result["n"], result["served"], result["coverage"]) == (4, 3, 0.75)
    assert result["majority_label"] == "b"
    assert (result["teacher"]["n"], result["teacher"]["correct"], result["teacher"]["accuracy"]) == (2, 2, 1)
    assert (result["gold"]["n"], result["gold"]["correct"], result["gold"]["accuracy"]) == (2, 1, 0.5)
    assert (result["majority_teacher"]["n"], result["majority_teacher"]["correct"]) == (3, 1)
    assert (result["majority_gold"]["n"], result["majority_gold"]["correct"]) == (3, 1)
    assert result["teacher"]["cluster_bootstrap_ci"] == (1, 1)
    assert result["gold"]["wilson_ci"][0] < 0.5 < result["gold"]["wilson_ci"][1]


def test_empty_and_all_refusal_summaries_do_not_invent_accuracy():
    empty = metrics.summary_metrics([], [], [], [], training_majority=None)
    assert empty["n"] == empty["served"] == 0
    assert math.isnan(empty["coverage"])
    assert math.isnan(empty["teacher"]["accuracy"])
    assert empty["majority_label"] is None
    refused = metrics.summary_metrics([None], ["a"], ["a"], ["x"], training_majority="a", resamples=10)
    assert refused["coverage"] == 0
    assert refused["teacher"]["n"] == 0
    assert math.isnan(refused["teacher"]["accuracy"])
    assert refused["majority_gold"]["accuracy"] == 1


def test_invalid_lengths_values_and_interval_options_are_rejected():
    with pytest.raises(ValueError, match="same length"):
        metrics.calibrate_threshold([0.5], [])
    with pytest.raises(ValueError, match="finite probabilities"):
        metrics.risk_coverage([float("nan")], [True])
    with pytest.raises(ValueError, match="max_error"):
        metrics.calibrate_threshold([], [], max_error=-0.1)
    with pytest.raises(ValueError, match="same length"):
        metrics.cluster_bootstrap([1], [], resamples=1)
    with pytest.raises(ValueError, match="resamples"):
        metrics.cluster_bootstrap([1], ["a"], resamples=0)
    with pytest.raises(ValueError, match="successes"):
        metrics.wilson(2, 1)
    with pytest.raises(ValueError, match="same length"):
        metrics.summary_metrics(["a"], [], [], [], training_majority="a")
