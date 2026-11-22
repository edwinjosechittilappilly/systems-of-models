from concurrent.futures import ThreadPoolExecutor

import pytest

from bench.common.budget import BudgetExceeded
from bench.e3a.spend import JournaledBudget


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
