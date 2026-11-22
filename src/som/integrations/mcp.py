"""Expose typed decisions through the optional official MCP Python SDK."""

from __future__ import annotations

from typing import Any

from som.adapters.openai import OpenAIDecisions
from som.adapters.typesafe import TypeSafe
from som.questions import Choice, Option, Predicate, Question, Score
from som.systems import Decider, Input


def configured_decider(spec: str) -> Decider:
    """Create a System 1 adapter from ``provider:model``."""
    provider, separator, model = spec.partition(":")
    if not separator or not model:
        raise ValueError("S1 must be provider:model, for example typesafe:jev-1.14.0")
    if provider == "typesafe":
        return TypeSafe(model)
    if provider in ("openai", "openai-decisions"):
        return OpenAIDecisions(model)
    raise ValueError(f"unsupported S1 provider: {provider}")


def parse_question(data: dict[str, Any]) -> Question:
    """Parse a question in the S1 contract representation."""
    kind, name, instructions = data["type"], data["name"], data["instructions"]
    if not all(isinstance(value, str) and value for value in (kind, name, instructions)):
        raise ValueError("question type, name and instructions must be nonempty strings")
    if kind == "predicate":
        return Predicate(name, instructions, data.get("true_means"), data.get("false_means"))
    if kind == "choice":
        choices = data["choices"]
        if not isinstance(choices, list) or any(
            not isinstance(c, dict) or not isinstance(c.get("value"), str) for c in choices
        ):
            raise ValueError("choices must be a list of objects with string values")
        return Choice(name, instructions, [Option(c["value"], c.get("description")) for c in choices])
    if kind == "score":
        levels = data["levels"]
        if not isinstance(levels, list) or any(
            not isinstance(level, dict) or not isinstance(level.get("label"), str) for level in levels
        ):
            raise ValueError("levels must be a list of objects with string labels")
        return Score(name, instructions, [level["label"] for level in levels])
    raise ValueError(f"unsupported question type: {kind}")


def decide(decider: Decider, input: Input, questions: list[dict[str, Any]]) -> dict[str, Any]:
    """Answer contract-shaped questions and return typed answers and their envelope."""
    parsed = [parse_question(question) for question in questions]
    if not parsed or len({question.name for question in parsed}) != len(parsed):
        raise ValueError("questions must be nonempty and have unique names")
    decision = decider.decide(input, parsed)
    return {
        "answers": {name: {**answer.to_contract(), "value": answer.value} for name, answer in decision.answers.items()},
        "envelope": decision.envelope.to_dict(),
    }


def create_server(decider: Decider) -> Any:
    """Create a FastMCP server without importing MCP unless this integration is used."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as error:
        raise ImportError("MCP support requires the official 'mcp' package: pip install mcp") from error

    server = FastMCP("systems-of-models")

    @server.tool(name="decide")
    def decide_tool(
        input: str | dict[str, Any] | list[dict[str, Any]], questions: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Answer typed S1 questions about input; return answers and the decision envelope."""
        return decide(decider, input, questions)

    return server
