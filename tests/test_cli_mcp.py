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
    with pytest.raises(ValueError, match="positive"):
        cli.main(["breakeven", "--c1", "0", "--c2", "0"])
    with pytest.raises(SystemExit):
        cli.main(["breakeven", "--c1", "nan", "--c2", "1"])


def test_ask_prints_s1_envelope(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    system = FunctionDecider(lambda _input, q: ChoiceAnswer(q.name, "billing", {"billing": 0.9, "cards": 0.1}))
    monkeypatch.setattr(cli, "configured_decider", lambda _spec: system)
    assert cli.main(["ask", "charged twice", "--choice", "team=billing,cards", "--s1", "typesafe:jev-1.14.0"]) == 0
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["system"] == "s1.decision"
    assert envelope["body"]["answers"][0]["choice"] == "billing"


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
    pytest.importorskip("mcp.server.fastmcp")
    system = FunctionDecider(lambda _input, q: PredicateAnswer(q.name, 0.5))
    tools = asyncio.run(create_server(system).list_tools())
    assert [tool.name for tool in tools] == ["decide"]
