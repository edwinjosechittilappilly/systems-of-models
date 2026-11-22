"""Dated list prices, used when a provider reports token usage but not a charge.

An envelope's ``cost.basis`` is ``list_price`` when the amount comes from this table, ``local_measured`` for
self-hosted models, ``provider_reported`` only when the provider itself returned the charge, and ``unknown`` (with a
null amount) when there is no defensible number. Prices change: pass your own :class:`RateCard` to an adapter, or
register one with :func:`register`, rather than trusting a stale table.
"""

from __future__ import annotations

from dataclasses import dataclass

from som.envelope import Cost, Usage


class UnknownPriceError(LookupError):
    """No rate card for a model. Pass ``rate_card=`` to the adapter or call :func:`som.pricing.register`."""


@dataclass(frozen=True)
class RateCard:
    """USD per million tokens, read from ``source`` on ``retrieved_at`` (``YYYY-MM-DD``)."""

    input_per_m: float
    output_per_m: float
    source: str
    retrieved_at: str
    cached_input_per_m: float | None = None

    def cost(self, usage: Usage) -> Cost:
        cached = usage.cached_tokens or 0
        cached_rate = self.input_per_m if self.cached_input_per_m is None else self.cached_input_per_m
        amount = (
            (usage.input_tokens - cached) * self.input_per_m
            + cached * cached_rate
            + usage.output_tokens * self.output_per_m
        ) / 1_000_000
        return Cost(
            amount=amount,
            basis="list_price",
            rate_card={"source": self.source, "retrieved_at": self.retrieved_at},
            usage=usage,
        )


_DATE = "2026-11-22"
_OPENAI = "https://developers.openai.com/api/docs/pricing"
_DECISIONS = "https://developers.openai.com/api/docs/guides/decisions"
_TYPESAFE = "https://docs.typesafe.ai/models"


def _card(input_per_m: float, output_per_m: float, source: str, cached: float | None = None) -> RateCard:
    return RateCard(input_per_m, output_per_m, source, _DATE, cached)


# (provider, model) -> rate card. Standard processing tier.
_CARDS: dict[tuple[str, str], RateCard] = {
    ("openai", "gpt-6-luna"): _card(0.10, 0.50, _OPENAI, 0.01),
    ("openai", "gpt-6.1-terra"): _card(1.00, 5.00, _OPENAI, 0.05),
    ("openai", "gpt-6.1-sol"): _card(2.00, 10.00, _OPENAI, 0.10),
    ("openai", "gpt-6.2-sol"): _card(2.00, 10.00, _OPENAI, 0.10),
    ("openai", "gpt-5.6-luna"): _card(0.20, 1.20, _OPENAI, 0.02),
    ("openai", "gpt-5.4-mini"): _card(0.75, 4.50, _OPENAI, 0.075),
    ("openai", "gpt-5.4-nano"): _card(0.20, 1.25, _OPENAI, 0.02),
    ("openai", "gpt-5-mini"): _card(0.25, 2.00, _OPENAI, 0.025),
    ("openai", "gpt-5-nano"): _card(0.05, 0.40, _OPENAI, 0.005),
    # Decisions endpoint: input only, output tokens are not charged.
    ("openai-decisions", "gpt-6-luna"): _card(0.10, 0.0, _DECISIONS, 0.01),
    # TypeSafe Jev: input only, output tokens are free.
    ("typesafe", "jev-1.14.0"): _card(0.042, 0.0, _TYPESAFE),
    ("typesafe", "jev-1.13.0"): _card(0.042, 0.0, _TYPESAFE),
    ("typesafe", "jev-latest"): _card(0.042, 0.0, _TYPESAFE),
    ("typesafe", "jev-preview"): _card(0.042, 0.0, _TYPESAFE),
}


def register(provider: str, model: str, card: RateCard) -> None:
    """Add or replace the rate card for ``provider``/``model``."""
    _CARDS[(provider, model)] = card


def lookup(provider: str, model: str) -> RateCard:
    """Return the rate card for a model, also matching dated snapshots such as ``gpt-6.1-terra-2026-09-30``."""
    card = _CARDS.get((provider, model))
    if card is not None:
        return card
    for (known_provider, known_model), known_card in _CARDS.items():
        if known_provider == provider and model.startswith(known_model + "-"):
            return known_card
    raise UnknownPriceError(f"no rate card for {provider}/{model}; pass rate_card= or call som.pricing.register")


def local_cost(usage: Usage) -> Cost:
    """Cost of a self-hosted call counting API charges only, which are zero. Hardware and energy are not metered,
    and the rate card says so."""
    return Cost(
        amount=0.0,
        basis="local_measured",
        rate_card={"source": "self-hosted: API charges only; compute not metered", "retrieved_at": _DATE},
        usage=usage,
    )
