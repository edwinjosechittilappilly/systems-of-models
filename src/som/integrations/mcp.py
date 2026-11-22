"""Expose typed decisions through the optional official MCP Python SDK."""

from __future__ import annotations

import json
from importlib import import_module
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


def _parse_request(input: Input, questions: list[dict[str, Any]]) -> list[Question]:
    try:
        size = len(json.dumps(input, ensure_ascii=False))
    except (TypeError, ValueError, RecursionError) as error:
        raise ValueError("input must be JSON serializable") from error
    if size > 65_536:
        raise ValueError("input must not exceed 65536 characters when serialized as JSON")
    if not 1 <= len(questions) <= 32:
        raise ValueError("questions must contain between 1 and 32 items")
    for question in questions:
        for key in ("choices", "levels"):
            if key in question and (not isinstance(question[key], list) or len(question[key]) > 32):
                raise ValueError(f"{key} must be a list of at most 32 items")
    try:
        parsed = [parse_question(question) for question in questions]
    except (KeyError, TypeError) as error:
        raise ValueError(f"invalid question: {error}") from error
    if len({question.name for question in parsed}) != len(parsed):
        raise ValueError("questions must have unique names")
    return parsed


def _answer(decider: Decider, input: Input, parsed: list[Question]) -> dict[str, Any]:
    decision = decider.decide(input, parsed)
    return {
        "answers": {name: {**answer.to_contract(), "value": answer.value} for name, answer in decision.answers.items()},
        "envelope": decision.envelope.to_dict(),
    }


def decide(decider: Decider, input: Input, questions: list[dict[str, Any]]) -> dict[str, Any]:
    """Answer contract-shaped questions and return typed answers and their envelope."""
    return _answer(decider, input, _parse_request(input, questions))


def create_server(decider: Decider) -> Any:
    """Create an MCP server without importing the optional SDK until needed."""
    try:
        try:
            server_module = import_module("mcp.server.mcpserver")
            exceptions_module = import_module("mcp.server.mcpserver.exceptions")
            server_class = server_module.MCPServer
        except ImportError:
            server_module = import_module("mcp.server.fastmcp")
            exceptions_module = import_module("mcp.server.fastmcp.exceptions")
            server_class = server_module.FastMCP
    except ImportError as error:
        raise ImportError("MCP support requires the official 'mcp' package: pip install mcp") from error
    tool_error = exceptions_module.ToolError

    from typing import Annotated, Literal

    from pydantic import BaseModel, Field

    class OptionSpec(BaseModel):
        value: str = Field(min_length=1, max_length=4096)
        description: str | None = Field(default=None, max_length=4096)

    class LevelSpec(BaseModel):
        label: str = Field(min_length=1, max_length=4096)

    class PredicateSpec(BaseModel):
        type: Literal["predicate"]
        name: str = Field(min_length=1, max_length=4096)
        instructions: str = Field(min_length=1, max_length=4096)
        true_means: str | None = Field(default=None, max_length=4096)
        false_means: str | None = Field(default=None, max_length=4096)

    class ChoiceSpec(BaseModel):
        type: Literal["choice"]
        name: str = Field(min_length=1, max_length=4096)
        instructions: str = Field(min_length=1, max_length=4096)
        choices: list[OptionSpec] = Field(min_length=2, max_length=32)

    class ScoreSpec(BaseModel):
        type: Literal["score"]
        name: str = Field(min_length=1, max_length=4096)
        instructions: str = Field(min_length=1, max_length=4096)
        levels: list[LevelSpec] = Field(min_length=2, max_length=32)

    server = server_class("systems-of-models")

    def decide_tool(input: Any, questions: Any) -> dict[str, Any]:
        """Answer typed S1 questions about input; return answers and the decision envelope."""
        try:
            parsed = _parse_request(input, [question.model_dump(exclude_none=True) for question in questions])
        except ValueError as error:
            raise tool_error(str(error)) from error
        return _answer(decider, input, parsed)

    # The SDK resolves function annotations outside this local scope.
    decide_tool.__annotations__["input"] = (
        Annotated[str, Field(max_length=65_536)] | dict[str, Any] | list[dict[str, Any]]
    )
    decide_tool.__annotations__["questions"] = Annotated[
        list[PredicateSpec | ChoiceSpec | ScoreSpec], Field(min_length=1, max_length=32)
    ]
    server.tool(name="decide")(decide_tool)

    return server
