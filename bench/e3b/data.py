"""Published tau2-bench agent trajectories (Sierra Research, MIT licence), pinned to one commit.

E3b mines decisions from these real agent traces instead of traces we generate. Eight files: four agent models
(claude-3-7-sonnet, gpt-4.1, gpt-4.1-mini, o4-mini) x two domains (retail, airline), four trials per task, all with
gpt-4.1 as the user simulator. Each task carries gold actions (``evaluation_criteria.actions``).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from bench.common.data import DATA_DIR

COMMIT = "768f3d8fe8528b4f32a5096f9ed008ae50f48ead"
_RAW = "https://raw.githubusercontent.com/sierra-research/tau2-bench/{commit}/data/tau2/results/final/{name}"
MODELS = {
    "claude-3-7-sonnet": ("claude-3-7-sonnet-20250219", "default"),
    "gpt-4.1": ("gpt-4.1-2025-04-14", "default"),
    "gpt-4.1-mini": ("gpt-4.1-mini-2025-04-14", "base"),
    "o4-mini": ("o4-mini-2025-04-16", "default"),
}
DOMAINS = ("retail", "airline")


def file_name(model: str, domain: str) -> str:
    full, variant = MODELS[model]
    return f"{full}_{domain}_{variant}_gpt-4.1-2025-04-14_4trials.json"


def fetch(model: str, domain: str) -> Path:
    """Download one results file (once) and pin its SHA-256 in bench/data/CHECKSUMS.json."""
    name = file_name(model, domain)
    path = DATA_DIR / "tau2" / name
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with httpx.stream("GET", _RAW.format(commit=COMMIT, name=name), follow_redirects=True, timeout=120) as r:
            r.raise_for_status()
            with path.open("wb") as handle:
                for chunk in r.iter_bytes():
                    handle.write(chunk)
    checksums_path = DATA_DIR / "CHECKSUMS.json"
    checksums = json.loads(checksums_path.read_text()) if checksums_path.exists() else {}
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    key = f"tau2/{name}"
    if key in checksums and checksums[key] != digest:
        raise RuntimeError(f"{key}: checksum changed")
    checksums[key] = digest
    checksums_path.write_text(json.dumps(checksums, indent=2, sort_keys=True) + "\n")
    return path


@dataclass
class ToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any]
    result: Any = None
    result_index: int | None = None


@dataclass
class Turn:
    """One message. ``tool_calls`` are the agent's calls in this message, with their results attached."""

    index: int
    role: str
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)


@dataclass
class Episode:
    episode_id: str
    model: str
    domain: str
    task_id: str
    trial: int
    reward: float
    turns: list[Turn]
    gold_actions: list[dict[str, Any]]

    def transcript(self, until: int | None = None) -> str:
        """User/assistant text (no tool payloads) up to, not including, turn ``until``."""
        lines = []
        for turn in self.turns[:until]:
            if turn.role in ("user", "assistant") and turn.content:
                lines.append(f"{turn.role}: {turn.content}")
        return "\n".join(lines)


def _parse_result(content: Any) -> Any:
    if isinstance(content, str):
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return content
    return content


def load(model: str, domain: str) -> Iterator[Episode]:
    raw = json.loads(fetch(model, domain).read_text())
    tasks = {str(task["id"]): task for task in raw["tasks"]}
    for sim in raw["simulations"]:
        results = {
            m.get("id"): (index, _parse_result(m.get("content")))
            for index, m in enumerate(sim["messages"])
            if m["role"] == "tool"
        }
        turns = []
        for index, message in enumerate(sim["messages"]):
            if message["role"] == "tool":
                continue
            calls = [
                ToolCall(
                    call["id"],
                    call["name"],
                    call.get("arguments") or {},
                    results.get(call["id"], (None, None))[1],
                    results.get(call["id"], (None, None))[0],
                )
                for call in (message.get("tool_calls") or [])
            ]
            turns.append(Turn(index, message["role"], message.get("content") or "", calls))
        task = tasks[str(sim["task_id"])]
        yield Episode(
            episode_id=f"{model}/{domain}/{sim['task_id']}/{sim['trial']}",
            model=model,
            domain=domain,
            task_id=str(sim["task_id"]),
            trial=int(sim["trial"]),
            reward=float((sim.get("reward_info") or {}).get("reward") or 0.0),
            turns=turns,
            gold_actions=list((task.get("evaluation_criteria") or {}).get("actions") or []),
        )
