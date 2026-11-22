"""Systems of Models: typed contracts, gates and escalation for LLM systems.

    import som
    gate = som.Gate(
        s1=som.TypeSafe("jev-1.14.0"),
        s2=som.OpenAIResponses("gpt-6.1-terra"),
        question=som.Choice("team", "Which team should handle this ticket?", ["billing", "cards", "fraud"]),
    )
    result = gate("I was charged twice for my card")
    result.value, result.served_by, result.cost.amount

Every call also yields an :class:`Envelope` that validates against the bundled JSON Schemas.
"""

from importlib.metadata import version

from som.adapters import OpenAIChat, OpenAIDecisions, OpenAIResponses, TypeSafe
from som.envelope import CONTRACT_VERSION, Cost, Envelope, Escalation, TraceRef, Usage
from som.gate import Gate, GateResult, breakeven_rate
from som.questions import Choice, ChoiceAnswer, Predicate, PredicateAnswer, Refusal, Score, ScoreAnswer
from som.systems import Decider, Decision
from som.trace import TraceStore

__version__ = version("systems-of-models")

__all__ = [
    "CONTRACT_VERSION",
    "Choice",
    "ChoiceAnswer",
    "Cost",
    "Decider",
    "Decision",
    "Envelope",
    "Escalation",
    "Gate",
    "GateResult",
    "OpenAIChat",
    "OpenAIDecisions",
    "OpenAIResponses",
    "Predicate",
    "PredicateAnswer",
    "Refusal",
    "Score",
    "ScoreAnswer",
    "TraceRef",
    "TraceStore",
    "TypeSafe",
    "Usage",
    "__version__",
    "breakeven_rate",
]
