from concurrent.futures import ThreadPoolExecutor

import pytest

from bench.common.budget import BudgetExceeded
from bench.e3a.spend import JournaledBudget, paid_call


def test_spend_survives_restarts_and_exceeded_calls_are_recorded(tmp_path):
    path = tmp_path / "spend.jsonl"
    first = JournaledBudget({"openai": 1.0}, initial={"openai": 0.2}, path=path)
    first.charge("openai", 0.3)
    second = JournaledBudget({"openai": 1.0}, initial={"openai": 0.2}, path=path)
    assert second.spent["openai"] == 0.5
    with pytest.raises(BudgetExceeded):
        second.charge("openai", 0.6)
    third = JournaledBudget({"openai": 1.0}, initial={"openai": 0.2}, path=path)
    assert third.spent["openai"] == pytest.approx(1.1)


def test_spend_journal_serializes_concurrent_charges(tmp_path):
    path = tmp_path / "spend.jsonl"
    budget = JournaledBudget({"openai": 2.0}, initial={}, path=path)
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(lambda _: budget.charge("openai", 0.01), range(100)))
    replayed = JournaledBudget({"openai": 2.0}, initial={}, path=path)
    assert replayed.spent["openai"] == pytest.approx(1.0)
    assert len(path.read_text().splitlines()) == 100


def test_reservations_are_cumulative_across_budget_instances(tmp_path):
    path = tmp_path / "spend.jsonl"
    first = JournaledBudget({"openai": 75}, initial={"openai": 74.5}, path=path)
    second = JournaledBudget({"openai": 75}, initial={"openai": 74.5}, path=path)
    with paid_call(first, "openai", 0.4) as settle:
        settle(0.3)
    with pytest.raises(BudgetExceeded, match="reserve exhausted"), paid_call(second, "openai", 0.4):
        pytest.fail("request must not be sent")
    assert second.spent["openai"] == pytest.approx(74.8)


def test_unpriced_call_reservation_survives_restart_and_blocks_calls(tmp_path):
    path = tmp_path / "spend.jsonl"
    budget = JournaledBudget({"typesafe": 5}, initial={"typesafe": 1.8431}, path=path)
    with pytest.raises(BudgetExceeded, match="unpriced call"), paid_call(budget, "typesafe", 0.05):
        raise RuntimeError("missing usage")
    restarted = JournaledBudget({"typesafe": 5}, initial={"typesafe": 1.8431}, path=path)
    assert restarted.spent["typesafe"] == pytest.approx(1.8931)
    with pytest.raises(BudgetExceeded, match="unsettled"), paid_call(restarted, "typesafe", 0.05):
        pytest.fail("request must not be sent")
