import math

import pytest

from bench.e3b.discovery import discovery_rows


def test_discovery_pools_unique_domain_kind_and_name_and_compares_baselines():
    rows = [
        {"domain": "retail", "kind": "branch", "name": "shared", "accepted": True, "judgement": True},
        {"domain": "retail", "kind": "branch", "name": "shared", "accepted": True, "judgement": True},
        {"domain": "retail", "kind": "tool_argument", "name": "shared", "accepted": False, "judgement": True},
        {"domain": "retail", "kind": "branch", "name": "noise", "accepted": True, "judgement": False},
        {"domain": "airline", "kind": "branch", "name": "shared", "accepted": False, "judgement": True},
        {"domain": "airline", "kind": "retrieval_choice", "name": "lookup", "accepted": True, "judgement": False},
    ]
    result = {(r["domain"], r["method"], r["kind"]): r for r in discovery_rows(rows)}
    assert len(result) == 18

    pooled = result["pooled", "miner", "all"]
    assert (pooled["candidates"], pooled["tp"], pooled["fp"], pooled["fn"]) == (5, 1, 2, 2)
    assert pooled["precision"] == pytest.approx(1 / 3)
    assert pooled["recall"] == pytest.approx(1 / 3)
    assert pooled["precision_ci"] == pytest.approx((0.06149194, 0.79234040))
    assert pooled["recall_ci"] == pytest.approx((0.06149194, 0.79234040))

    branch = result["pooled", "accept_branches", "all"]
    assert (branch["candidates"], branch["tp"], branch["fp"], branch["fn"]) == (5, 2, 1, 1)
    assert branch["precision"] == pytest.approx(2 / 3)
    assert branch["recall"] == pytest.approx(2 / 3)
    assert branch["precision_ci"] == pytest.approx((0.20765960, 0.93850806))
    all_candidates = result["pooled", "accept_all", "all"]
    assert (all_candidates["tp"], all_candidates["fp"], all_candidates["fn"]) == (3, 2, 0)
    assert all_candidates["precision"] == pytest.approx(0.6)
    assert all_candidates["recall"] == 1
    assert (result["retail", "miner", "branch"]["tp"], result["airline", "miner", "branch"]["fn"]) == (1, 1)


def test_empty_categories_and_undefined_ratios_are_retained():
    rows = [{"domain": "retail", "kind": "branch", "name": "negative", "accepted": True, "judgement": False}]
    result = {(r["domain"], r["method"], r["kind"]): r for r in discovery_rows(rows)}
    empty = result["retail", "miner", "retrieval_choice"]
    assert (empty["candidates"], empty["tp"], empty["fp"], empty["fn"]) == (0, 0, 0, 0)
    assert math.isnan(empty["precision"]) and math.isnan(empty["recall"])
    assert all(math.isnan(value) for value in empty["precision_ci"] + empty["recall_ci"])
    negative = result["retail", "miner", "branch"]
    assert negative["precision"] == 0
    assert math.isnan(negative["recall"])
    assert result["airline", "accept_all", "all"]["candidates"] == 0
    assert len(discovery_rows([])) == 18
