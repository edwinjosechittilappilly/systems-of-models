"""The one interface every adapter implements: answer typed questions about an input, return an envelope."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from som.envelope import Envelope, SystemId
from som.questions import Answer, Question

Input = str | Mapping[str, Any] | Sequence[Mapping[str, Any]]
"""A string, a structured state object, or a list of chat messages."""


@dataclass
class Decision:
    """Typed answers keyed by question name, plus the envelope of the call that produced them."""

    envelope: Envelope
    answers: dict[str, Answer]

    def __getitem__(self, name: str) -> Answer:
        return self.answers[name]


@runtime_checkable
class Decider(Protocol):
    """Anything that answers typed questions: a System 1 decision model, or a reasoning model with structured output.

    ``name`` identifies the provider and model, e.g. ``"typesafe/jev-preview"``; ``system`` is the contract tier it
    answers as (``"s1.decision"`` or ``"s2.reasoning"``).
    """

    name: str
    system: SystemId

    def decide(self, input: Input, questions: Sequence[Question], *, trace_id: str | None = None) -> Decision: ...
