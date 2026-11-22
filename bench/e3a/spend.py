"""Durable, process-restart-safe accounting for new E3a model spend."""

from __future__ import annotations

import json
import time
from pathlib import Path

from bench.common.budget import Budget, BudgetExceeded
from bench.common.cache import CACHE_DIR


class JournaledBudget(Budget):
    """Append every successful paid call before enforcing caps.

    Cache replay does not call ``charge``. The journal contains amounts only,
    never prompts or credentials. Pilot spend is supplied separately because its
    collection predates this journal. One benchmark process should write a
    given journal at a time; threads in that process are serialized.
    """

    def __init__(
        self, caps: dict[str, float], *, initial: dict[str, float], path: Path = CACHE_DIR / "e3a_spend_v2.jsonl"
    ) -> None:
        super().__init__(caps)
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for provider, amount in initial.items():
            self.spent[provider] += amount
        if path.exists():
            with path.open() as handle:
                for line in handle:
                    if line.strip():
                        record = json.loads(line)
                        self.spent[record["provider"]] += float(record["amount"])
        self.started_spend = dict(self.spent)

    def charge(self, provider: str, amount: float | None) -> None:
        if amount is None:
            raise ValueError("cannot record unknown spend")
        if amount < 0:
            raise ValueError("negative spend")
        with self._lock:
            self.spent[provider] += amount
            with self.path.open("a") as handle:
                handle.write(json.dumps({"provider": provider, "amount": amount, "at": time.time()}) + "\n")
                handle.flush()
            cap = self.caps.get(provider)
            if cap is not None and self.spent[provider] > cap:
                raise BudgetExceeded(f"{provider}: recorded spend exceeds cap ${cap:.2f}")

    def new_spend(self) -> dict[str, float]:
        return {provider: value - self.started_spend.get(provider, 0.0) for provider, value in self.spent.items()}
