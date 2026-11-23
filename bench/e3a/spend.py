"""Durable, process-restart-safe accounting for new E3a model spend."""

from __future__ import annotations

import fcntl
import json
import math
import os
import re
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from bench.common.budget import Budget, BudgetExceeded
from bench.common.cache import CACHE_DIR

_CALL_LOCK = threading.Lock()


@contextmanager
def paid_call(budget: Budget, provider: str, reserve: float):
    """Serialize paid calls, reserving headroom before sending a request.

    An interrupted or unpriced call is conservatively charged its reservation.
    Journaled budgets also serialize and reload across benchmark processes.
    """
    with _CALL_LOCK:
        lock = None
        if isinstance(budget, JournaledBudget):
            lock = budget.path.with_suffix(budget.path.suffix + ".lock").open("a")
            fcntl.flock(lock, fcntl.LOCK_EX)
            budget.reload()
        try:
            if isinstance(budget, JournaledBudget) and budget.pending:
                raise BudgetExceeded("budget has an unsettled paid call; reconcile provider billing before continuing")
            cap = budget.caps.get(provider)
            if cap is not None and budget.spent.get(provider, 0.0) + reserve > cap:
                raise BudgetExceeded(f"{provider}: budget reserve exhausted (cap ${cap:.2f})")
            prior_spend = budget.spent.get(provider, 0.0)
            reservation = uuid.uuid4().hex
            if isinstance(budget, JournaledBudget):
                budget.adjust(provider, reserve, reservation=reservation, phase="reserve")
            else:
                budget.charge(provider, reserve)
            settled = False

            def settle(amount: float | None) -> None:
                nonlocal settled
                if amount is None or not math.isfinite(amount) or amount < 0:
                    raise RuntimeError(f"{provider}: paid cost is unknown")
                delta = amount - reserve
                if isinstance(budget, JournaledBudget):
                    budget.adjust(provider, delta, reservation=reservation, phase="settle")
                else:
                    with budget._lock:
                        budget.spent[provider] = prior_spend + amount
                settled = True
                if amount > reserve:
                    raise BudgetExceeded(f"{provider}: call exceeded its budget reservation")

            try:
                yield settle
            except Exception as exc:
                if not settled:
                    message = re.sub(r"org-[A-Za-z0-9_-]+", "org-REDACTED", str(exc))
                    raise BudgetExceeded(f"{provider}: budget reserved for unpriced call: {message}") from None
                raise
        finally:
            if lock is not None:
                fcntl.flock(lock, fcntl.LOCK_UN)
                lock.close()


def request_reserve(request: dict) -> float:
    """Bound request size so the fixed reservation has ample list-price headroom."""
    if len(json.dumps(request, ensure_ascii=False, default=str).encode("utf-8")) > 100_000:
        raise BudgetExceeded("OpenAI request exceeds budget reservation size")
    if int(request.get("max_output_tokens", 0)) > 8000:
        raise BudgetExceeded("OpenAI request exceeds budget reservation output limit")
    return 1.0



class JournaledBudget(Budget):
    """Persist reservations and settlements across processes and restarts.

    Cache replay does not reserve spend. The journal contains amounts and
    reservation identifiers, never prompts or credentials. Pilot spend is
    supplied separately because its collection predates this journal.
    """

    def __init__(
        self, caps: dict[str, float], *, initial: dict[str, float], path: Path = CACHE_DIR / "e3a_spend_v2.jsonl"
    ) -> None:
        super().__init__(caps)
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initial = dict(initial)
        self.reload()
        self.started_spend = dict(self.spent)

    def reload(self) -> None:
        self.spent.clear()
        self.pending: set[str] = set()
        for provider, amount in self.initial.items():
            self.spent[provider] += amount
        if self.path.exists():
            with self.path.open() as handle:
                for line in handle:
                    if line.strip():
                        record = json.loads(line)
                        self.spent[record["provider"]] += float(record["amount"])
                        if record.get("phase") == "reserve":
                            self.pending.add(record["reservation"])
                        elif record.get("phase") == "settle":
                            self.pending.discard(record["reservation"])

    def adjust(self, provider: str, amount: float, *, reservation: str | None = None, phase: str | None = None) -> None:
        with self._lock:
            with self.path.open("a") as handle:
                record = {"provider": provider, "amount": amount, "at": time.time()}
                if reservation is not None:
                    record.update(reservation=reservation, phase=phase)
                handle.write(json.dumps(record) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            self.spent[provider] += amount
            cap = self.caps.get(provider)
            if cap is not None and self.spent[provider] > cap:
                raise BudgetExceeded(f"{provider}: recorded spend exceeds cap ${cap:.2f}")

    def charge(self, provider: str, amount: float | None) -> None:
        if amount is None or not math.isfinite(amount) or amount < 0:
            raise ValueError("cannot record unknown or negative spend")
        self.adjust(provider, amount)

    def new_spend(self) -> dict[str, float]:
        return {provider: value - self.started_spend.get(provider, 0.0) for provider, value in self.spent.items()}
