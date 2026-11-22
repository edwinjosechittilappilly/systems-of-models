"""Spend guard: every new (uncached) paid call is charged here before results are used; the run stops at the cap."""

from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass, field


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class Budget:
    """USD caps per provider for *new* spend in this process. Replayed calls cost nothing new."""

    caps: dict[str, float]
    spent: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def charge(self, provider: str, amount: float | None) -> None:
        if not amount:
            return
        with self._lock:
            self.spent[provider] += amount
            cap = self.caps.get(provider)
            if cap is not None and self.spent[provider] > cap:
                raise BudgetExceeded(f"{provider}: new spend ${self.spent[provider]:.4f} exceeds cap ${cap:.2f}")

    def summary(self) -> dict[str, float]:
        return {provider: round(amount, 6) for provider, amount in self.spent.items()}
