"""Route support tickets through a typed gate.

Run ``python examples/support_ticket.py`` for deterministic, offline examples. Install
``systems-of-models[openai]``, set TYPESAFE_API_KEY and OPENAI_API_KEY in the
environment, and pass ``--live`` to call the real providers (paid API calls).
The tickets below are synthetic; do not send private tickets without appropriate safeguards.
"""

from __future__ import annotations

import argparse
import json

import som
from som.questions import ChoiceAnswer, PredicateAnswer
from som.testing import FunctionDecider
from som.trace import TraceStore

TEAMS = {
    "billing": "Duplicate charges, refunds, and billing statements.",
    "cards": "Card activation, delivery, or card payment problems.",
    "fraud": "Unrecognized transactions or suspected unauthorized account activity.",
}
TEAM = som.Choice("team", "Which team should handle this support ticket?", TEAMS)
# Each question is evaluated independently: the predicate must name the options itself.
FITS = som.Predicate(
    "fits",
    "Does this support ticket belong to any of these teams: billing, cards, or fraud?",
    true_means="The ticket concerns billing, cards, or suspected fraud.",
    false_means="The ticket concerns a topic outside billing, cards, and suspected fraud.",
)

TICKETS = (
    "I was charged twice for the same coffee; please refund the duplicate.",
    "My card payment was declined and I do not recognize the attempted charge.",
    "What will the weather be like tomorrow?",
)


def offline_deciders():
    """Return illustrative fixed answers, not a classifier or a live model."""
    answers = {
        TICKETS[0]: ("billing", {"billing": 0.94, "cards": 0.04, "fraud": 0.02}, 0.98, "billing", True),
        TICKETS[1]: ("cards", {"billing": 0.05, "cards": 0.50, "fraud": 0.45}, 0.97, "fraud", True),
        TICKETS[2]: ("billing", {"billing": 0.90, "cards": 0.06, "fraud": 0.04}, 0.02, "billing", False),
    }

    def s1_answer(ticket, question):
        choice, probabilities, fit, _, _ = answers[ticket]
        if question.name == FITS.name:
            return PredicateAnswer(question.name, fit)
        return ChoiceAnswer(question.name, choice, probabilities)

    def s2_answer(ticket, question):
        _, _, _, choice, fit = answers[ticket]
        if question.name == FITS.name:
            return PredicateAnswer(question.name, None, raw_value=fit)
        return ChoiceAnswer(question.name, choice)

    # Fixed illustrative per-call prices, not measurements or provider prices.
    return (
        FunctionDecider(s1_answer, name="example/s1", cost_per_call=0.0001),
        FunctionDecider(s2_answer, system="s2.reasoning", name="example/s2", cost_per_call=0.01),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Use TypeSafe and OpenAI instead of offline stand-ins")
    parser.add_argument("--trace", help="Append trace records to this JSONL path (default: in memory)")
    args = parser.parse_args()

    if args.live:
        s1 = som.TypeSafe("jev-1.14.0")  # TYPESAFE_API_KEY
        s2 = som.OpenAIResponses("gpt-6.1-terra")  # OPENAI_API_KEY
    else:
        s1, s2 = offline_deciders()

    store = TraceStore(args.trace)
    gate = som.Gate(s1, s2, TEAM, fit=FITS, threshold=0.8, fit_threshold=0.5, store=store)
    print("Options:", ", ".join(TEAM.values))
    for ticket in TICKETS:
        result = gate(ticket)
        print(f"\nTicket: {ticket}")
        print(f"Served by: {result.served_by}; in scope: {result.in_scope}; route: {result.value}")
        if result.value is None:
            print("No route was served; send the ticket to a human for review.")
        print("Escalation:", json.dumps(result.escalation.to_dict() if result.escalation else None, indent=2))
        print("Total cost:", json.dumps(result.cost.to_dict(), indent=2))
        for role, decision in (("S1", result.s1), ("S2", result.s2)):
            if decision is not None:
                print(f"{role} envelope:", json.dumps(decision.envelope.to_dict(), indent=2))

    print(f"\nTrace store: {len(store.of_kind('gate'))} gate records, {len(store.of_kind('envelope'))} envelopes")
    if args.trace:
        print(f"Trace records appended to {args.trace}")


if __name__ == "__main__":
    main()
