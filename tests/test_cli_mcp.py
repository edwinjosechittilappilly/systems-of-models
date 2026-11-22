"""Public CLI and MCP decision interfaces."""

import asyncio
import json
from importlib.resources import files
from typing import Any

import pytest

from som import cli
from som.integrations.mcp import create_server, decide, parse_question
from som.questions import ChoiceAnswer, PredicateAnswer
from som.testing import FunctionDecider


def test_breakeven_reports_conditional_cost_and_savings(capsys: pytest.CaptureFixture[str]) -> None:
    assert (
        cli.main(
            [
                "breakeven",
                "--c1",
                "0.00004",
                "--c2",
                "0.004",
                "--escalated-c2",
                "0.005",
                "--overhead",
                "0.00001",
                "--escalation-rate",
                "0.2",
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert "99.00%" in output
    assert "79.00%" in output
    assert "$0.00105000" in output
    assert "73.75%" in output


def test_breakeven_rejects_invalid_cost() -> None:
    with pytest.raises(SystemExit) as error:
        cli.main(["breakeven", "--c1", "0", "--c2", "0"])
    assert error.value.code == 2
    with pytest.raises(SystemExit) as error:
        cli.main(["breakeven", "--c1", "nan", "--c2", "1"])
    assert error.value.code == 2


def test_ask_prints_s1_envelope(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    system = FunctionDecider(lambda _input, q: ChoiceAnswer(q.name, "billing", {"billing": 0.9, "cards": 0.1}))
    monkeypatch.setattr(cli, "configured_decider", lambda _spec: system)
    assert cli.main(["ask", "charged twice", "--choice", "team=billing,cards", "--s1", "typesafe:jev-1.14.0"]) == 0
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["system"] == "s1.decision"
    assert envelope["body"]["answers"][0]["choice"] == "billing"


def test_ask_rejects_bad_choice() -> None:
    with pytest.raises(SystemExit) as error:
        cli.main(["ask", "text", "--choice", "bad", "--s1", "typesafe:model"])
    assert error.value.code == 2


def test_ask_strips_choice_options(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def answer(_input: Any, question: Any) -> ChoiceAnswer:
        assert question.values == ["billing", "cards"]
        return ChoiceAnswer(question.name, "billing", {"billing": 0.9, "cards": 0.1})

    monkeypatch.setattr(cli, "configured_decider", lambda _spec: FunctionDecider(answer))
    assert cli.main(["ask", "text", "--choice", "team=billing, cards", "--s1", "typesafe:model"]) == 0
    assert json.loads(capsys.readouterr().out)["body"]["answers"][0]["choice"] == "billing"


def test_demo_replays_recorded_gate_results(capsys: pytest.CaptureFixture[str]) -> None:
    rows = [json.loads(line) for line in files("som").joinpath("demo", "gate.jsonl").read_text().splitlines()]
    assert len(rows) == 20
    assert {row["served_by"] for row in rows} == {"s1", "s2"}
    for row in rows:
        assert row["s1"]["implementation"]["model"] == "jev-1.14.0"
        assert row["s2"]["implementation"]["model"].startswith("gpt-6.1-terra")
        assert row["gate_cost"] == pytest.approx(
            row["s1"]["cost"]["amount"] + (row["s2_cost"] if row["served_by"] == "s2" else 0)
        )
    assert cli.main(["demo"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert "served_by" in lines[0] and "savings" in lines[0]
    assert len(lines) == len(rows) + 1


def test_mcp_decide_returns_typed_answers_and_envelope() -> None:
    system = FunctionDecider(lambda _input, q: PredicateAnswer(q.name, 0.85))
    result = decide(system, "charged twice", [{"type": "predicate", "name": "refund", "instructions": "Refund?"}])
    assert result["answers"]["refund"] == {
        "type": "predicate",
        "name": "refund",
        "probability": 0.85,
        "value": True,
    }
    assert result["envelope"]["system"] == "s1.decision"


def test_mcp_rejects_duplicate_questions_and_choices() -> None:
    question: dict[str, Any] = {"type": "predicate", "name": "p", "instructions": "Question?"}
    system = FunctionDecider(lambda _input, q: PredicateAnswer(q.name, 0.5))
    with pytest.raises(ValueError, match="unique"):
        decide(system, "text", [question, question])
    with pytest.raises(ValueError, match="distinct"):
        parse_question(
            {
                "type": "choice",
                "name": "x",
                "instructions": "Choose",
                "choices": [
                    {"value": "a"},
                    {"value": "a"},
                ],
            }
        )


def test_mcp_server_exposes_decide_tool() -> None:
    system = FunctionDecider(lambda _input, q: PredicateAnswer(q.name, 0.5))
    tools = asyncio.run(create_server(system).list_tools())
    assert [tool.name for tool in tools] == ["decide"]
    schema = tools[0].input_schema
    questions = schema["properties"]["questions"]
    assert questions["minItems"] == 1
    assert questions["maxItems"] == 32
    serialized = json.dumps(schema)
    for field in ("predicate", "choice", "score", "instructions", "choices", "levels", "label", "description"):
        assert field in serialized


def test_mcp_server_validates_and_reports_actionable_errors() -> None:
    from mcp.server.mcpserver.exceptions import ToolError

    system = FunctionDecider(lambda _input, q: PredicateAnswer(q.name, 0.5))
    server = create_server(system)
    predicate = {"type": "predicate", "name": "p", "instructions": "Question?"}
    with pytest.raises(ToolError, match="unique"):
        asyncio.run(server.call_tool("decide", {"input": "text", "questions": [predicate, predicate]}))
    choice = {
        "type": "choice",
        "name": "c",
        "instructions": "Choose",
        "choices": [{"value": "a"}, {"value": "a"}],
    }
    with pytest.raises(ToolError, match="distinct"):
        asyncio.run(server.call_tool("decide", {"input": "text", "questions": [choice]}))
    with pytest.raises(ToolError):
        asyncio.run(server.call_tool("decide", {"input": "text", "questions": [predicate] * 33}))
    with pytest.raises(ToolError):
        asyncio.run(server.call_tool("decide", {"input": {"text": "x" * 65_536}, "questions": [predicate]}))
    with pytest.raises(ToolError):
        asyncio.run(server.call_tool("decide", {"input": "text", "questions": [{**choice, "choices": []}]}))


def test_mcp_server_calls_real_tool() -> None:
    system = FunctionDecider(lambda _input, q: PredicateAnswer(q.name, 0.85))
    server = create_server(system)
    result = asyncio.run(
        server.call_tool(
            "decide",
            {
                "input": "charged twice",
                "questions": [{"type": "predicate", "name": "refund", "instructions": "Refund?"}],
            },
        )
    )
    assert result.structured_content["answers"]["refund"]["probability"] == 0.85
