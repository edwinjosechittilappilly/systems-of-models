"""System 1 question types and typed answers (the S1 contract), independent of any vendor."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_\-]{0,63}$")


def _check_name(name: str) -> None:
    """Question names key answers in the S1 contract, which restricts them to an identifier pattern."""
    if not isinstance(name, str) or not _NAME.match(name):
        raise ValueError(f"question name {name!r} must match {_NAME.pattern} (letters, digits, _ or -; max 64)")


@dataclass(frozen=True)
class Option:
    value: str
    description: str | None = None


def _options(options: Sequence[str] | Mapping[str, str] | Sequence[Option]) -> tuple[Option, ...]:
    if isinstance(options, Mapping):
        return tuple(Option(str(value), description) for value, description in options.items())
    return tuple(option if isinstance(option, Option) else Option(str(option)) for option in options)


@dataclass(frozen=True)
class Predicate:
    """A yes/no judgement. ``true_means``/``false_means`` describe each outcome as a concrete situation."""

    name: str
    instructions: str
    true_means: str | None = None
    false_means: str | None = None

    def __post_init__(self) -> None:
        _check_name(self.name)

    def to_contract(self) -> dict[str, Any]:
        """S1 contract form. The contract has no criteria field, so outcome descriptions travel in the
        instructions; every vendor then sees the same question."""
        instructions = self.instructions
        if self.true_means or self.false_means:
            parts = [
                f"true means: {self.true_means}" if self.true_means else "",
                f"false means: {self.false_means}" if self.false_means else "",
            ]
            instructions = f"{instructions} ({'; '.join(p for p in parts if p)})"
        return {"type": "predicate", "name": self.name, "instructions": instructions}


@dataclass(frozen=True)
class Choice:
    """Pick one option. Pass a list of values or a ``{value: description}`` mapping."""

    name: str
    instructions: str
    options: tuple[Option, ...]

    def __init__(
        self, name: str, instructions: str, options: Sequence[str] | Mapping[str, str] | Sequence[Option]
    ) -> None:
        _check_name(name)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "instructions", instructions)
        object.__setattr__(self, "options", _options(options))
        if len(self.options) < 2 or len({o.value for o in self.options}) != len(self.options):
            raise ValueError(f"choice {name!r} needs at least two distinct options")

    @property
    def values(self) -> list[str]:
        return [option.value for option in self.options]

    def to_contract(self) -> dict[str, Any]:
        choices = [
            {"value": o.value, **({"description": o.description} if o.description else {})} for o in self.options
        ]
        return {"type": "choice", "name": self.name, "instructions": self.instructions, "choices": choices}


@dataclass(frozen=True)
class Score:
    """Rate against ordered levels, lowest first. Each level is a situation that reads well on its own."""

    name: str
    instructions: str
    levels: tuple[str, ...]

    def __init__(self, name: str, instructions: str, levels: Sequence[str]) -> None:
        _check_name(name)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "instructions", instructions)
        object.__setattr__(self, "levels", tuple(levels))
        if len(self.levels) < 2:
            raise ValueError(f"score {name!r} needs at least two levels")

    def to_contract(self) -> dict[str, Any]:
        return {
            "type": "score",
            "name": self.name,
            "instructions": self.instructions,
            "levels": [{"label": label} for label in self.levels],
        }


Question = Predicate | Choice | Score


@dataclass(frozen=True)
class PredicateAnswer:
    name: str
    probability: float | None
    """Probability the statement is true; ``None`` when the system gave a bare answer (e.g. an LLM)."""
    raw_value: bool | None = None

    @property
    def value(self) -> bool:
        if self.probability is None:
            return bool(self.raw_value)
        return self.probability >= 0.5

    @property
    def top_probability(self) -> float | None:
        return None if self.probability is None else max(self.probability, 1 - self.probability)

    @property
    def confidence(self) -> float | None:
        return self.top_probability

    @property
    def margin(self) -> float | None:
        """``|p - (1 - p)|``: the gap between the two outcomes."""
        return None if self.probability is None else abs(2 * self.probability - 1)

    def to_contract(self) -> dict[str, Any]:
        return {"type": "predicate", "name": self.name, "probability": self.probability}


@dataclass(frozen=True)
class ChoiceAnswer:
    name: str
    choice: str
    probabilities: dict[str, float] = field(default_factory=dict)
    confidence: float | None = None
    """Vendor confidence: a statistic of how concentrated ``probabilities`` is, not P(correct)."""

    @property
    def value(self) -> str:
        return self.choice

    @property
    def top_probability(self) -> float | None:
        return self.probabilities.get(self.choice) if self.probabilities else None

    @property
    def margin(self) -> float | None:
        if len(self.probabilities) < 2:
            return None
        first, second = sorted(self.probabilities.values(), reverse=True)[:2]
        return first - second

    def to_contract(self) -> dict[str, Any]:
        return {
            "type": "choice",
            "name": self.name,
            "choice": self.choice,
            "probabilities": [{"value": v, "probability": p} for v, p in self.probabilities.items()],
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class ScoreAnswer:
    """``score`` is the probability-weighted mean level (may fall between levels). ``value`` is the most likely
    level, the one ``top_probability`` describes, so gating and agreement refer to the same answer."""

    name: str
    score: float
    probabilities: tuple[float, ...] = ()
    labels: tuple[str, ...] = ()
    confidence: float | None = None

    @property
    def value(self) -> int:
        if self.probabilities:
            return max(range(len(self.probabilities)), key=self.probabilities.__getitem__)
        return round(self.score)

    @property
    def top_probability(self) -> float | None:
        return max(self.probabilities) if self.probabilities else None

    @property
    def margin(self) -> float | None:
        if len(self.probabilities) < 2:
            return None
        first, second = sorted(self.probabilities, reverse=True)[:2]
        return first - second

    def to_contract(self) -> dict[str, Any]:
        return {
            "type": "score",
            "name": self.name,
            "score": self.score,
            "probabilities": [
                {"value": i, "label": label, "probability": p}
                for i, (label, p) in enumerate(zip(self.labels, self.probabilities, strict=True))
            ]
            if self.probabilities
            else [],
            "confidence": self.confidence,
        }


RefusalReason = Literal["policy", "out_of_answer_space", "insufficient_input", "unspecified"]


@dataclass(frozen=True)
class Refusal:
    name: str
    reason: RefusalReason = "unspecified"

    value = None
    top_probability = None
    confidence = None
    margin = None

    def to_contract(self) -> dict[str, Any]:
        return {"type": "refusal", "name": self.name, "reason": self.reason}


Answer = PredicateAnswer | ChoiceAnswer | ScoreAnswer | Refusal
