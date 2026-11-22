"""Pinned predicate serialization for the archived E1/E2 requests.

The original contract kept outcome criteria outside the instructions. Jev sent
those criteria in a separate native field; OpenAI requests did not include them.
"""

from __future__ import annotations

import som


def legacy_predicate_contract(predicate):
    """Return the exact pre-dc4d084 contract, including structured Jev instructions."""
    return {"type": "predicate", "name": predicate.name, "instructions": predicate.instructions}


class ArchivedPredicate(som.Predicate):
    """A Predicate whose cache key and OpenAI contract match the archived run."""

    def to_contract(self):
        return legacy_predicate_contract(self)
