"""Deterministic support tools and the agent-free E3a substitution path."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping

from bench.tasks.policy import load_policy


def augment_ticket(text: str, *, ticket_id: str) -> dict:
    """Add reproducible, copyable fields to the text and structured ticket."""
    digest = hashlib.sha256(str(ticket_id).encode("utf-8")).hexdigest()
    account_id = f"acct_{digest[:16]}"
    words = _tokens(text)
    transaction = bool(
        words
        & {
            "payment",
            "payments",
            "transaction",
            "transactions",
            "charge",
            "charges",
            "purchase",
            "purchases",
            "transfer",
            "transfers",
            "withdrawal",
            "withdrawals",
        }
    )
    has_merchant = bool(words & {"payment", "payments", "purchase", "purchases", "merchant"})
    amount = (int(digest[16:24], 16) % 100000) / 100 if transaction else None
    merchant = f"merchant_{digest[24:40]}" if has_merchant else None
    details = [f"Account ID: {account_id}"]
    if amount is not None:
        details.append(f"Amount: {amount:.2f}")
    if merchant is not None:
        details.append(f"Merchant: {merchant}")
    return {
        "text": f"{text}\n" + "; ".join(details),
        "ticket_id": ticket_id,
        "account_id": account_id,
        "amount": amount,
        "merchant": merchant,
    }


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


class PolicyKB:
    """Frozen entries with deterministic lexical top-five search and exact ID lookup."""

    def __init__(self, granularity: int = 4, entries: Iterable[Mapping] | None = None):
        source = load_policy(granularity) if entries is None else entries
        self._entries = {}
        for item in source:
            entry = dict(item)
            required = {"id", "title", "department", "priority", "identity_check"}
            if not required.issubset(entry):
                raise ValueError(f"policy entry missing fields: {sorted(required - entry.keys())}")
            if entry["id"] in self._entries:
                raise ValueError(f"duplicate policy entry id: {entry['id']}")
            self._entries[entry["id"]] = entry

    def get_entry(self, entry_id: str) -> dict:
        return self._entries[entry_id].copy()

    def search_policy(self, query: str) -> list[dict]:
        query_tokens = _tokens(query)
        ranked = sorted(
            self._entries.values(),
            key=lambda entry: (
                entry["id"] != query,
                -len(query_tokens & _tokens(f"{entry['id']} {entry['title']}")),
                entry["id"],
            ),
        )
        return [entry.copy() for entry in ranked[:5]]


class SupportEnvironment:
    """One run's observable tools; constructing one never invokes an agent."""

    def __init__(self, kb: PolicyKB, accounts: Mapping[str, Mapping] | None = None):
        self.kb = kb
        self.accounts = {key: dict(value) for key, value in (accounts or {}).items()}
        self.verified_accounts: set[str] = set()
        self.routes: list[dict] = []
        self.events: list[dict] = []
        self.agent_calls = 0
        self.agent_cost = 0.0

    def search_policy(self, query: str) -> list[dict]:
        self.events.append({"tool": "search_policy", "query": query})
        return self.kb.search_policy(query)

    def get_account(self, account_id: str) -> dict:
        self.events.append({"tool": "get_account", "account_id": account_id})
        digest = hashlib.sha256(account_id.encode("utf-8")).hexdigest()
        defaults = {"status": "active", "balance": (int(digest[:8], 16) % 1000000) / 100}
        return {**defaults, **self.accounts.get(account_id, {}), "account_id": account_id}

    def verify_identity(self, account_id: str) -> dict:
        self.events.append({"tool": "verify_identity", "account_id": account_id})
        self.verified_accounts.add(account_id)
        return {"account_id": account_id, "verified": True}

    def route_ticket(
        self,
        department: str,
        priority: str,
        queue: str,
        note: str,
        account_id: str,
        amount: float | None = None,
        merchant: str | None = None,
    ) -> dict:
        route = {"department": department, "priority": priority, "queue": queue, "note": note, "account_id": account_id}
        if amount is not None:
            route["amount"] = amount
        if merchant is not None:
            route["merchant"] = merchant
        self.routes.append(route.copy())
        self.events.append({"tool": "route_ticket", **route})
        return route

    def substitute(
        self,
        entry_id: str,
        account_id: str,
        verify: bool,
        note: str = "",
        amount: float | None = None,
        merchant: str | None = None,
    ) -> dict:
        """Execute D1/D2 decisions without an agent; D2 is never inferred from gold."""
        if not isinstance(verify, bool):
            raise TypeError("verify must be a bool")
        matches = self.search_policy(entry_id)
        if not matches or matches[0]["id"] != entry_id:
            raise KeyError(entry_id)
        entry = matches[0]
        if verify:
            self.verify_identity(account_id)
        return self.route_ticket(
            entry["department"],
            entry["priority"],
            f"{entry['department']}_queue",
            note,
            account_id,
            amount,
            merchant,
        )
