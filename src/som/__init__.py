"""Systems of Models: typed contracts, gates and escalation for LLM systems.

A :class:`Gate` asks a cheap System 1 decider a typed question and escalates to a stronger system when the answer
is not sure enough. Every call returns an :class:`Envelope` that validates against the bundled JSON Schemas.
"""

from importlib.metadata import version

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
    "Predicate",
    "PredicateAnswer",
    "Refusal",
    "Score",
    "ScoreAnswer",
    "TraceRef",
    "TraceStore",
    "Usage",
    "__version__",
    "breakeven_rate",
]
