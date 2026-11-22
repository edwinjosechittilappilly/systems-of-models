"""Cached Responses tool-use baseline for the controlled E3a task."""

from __future__ import annotations

import json
import time
from typing import Any

from bench.common.budget import Budget
from bench.common.cache import JsonCache
from bench.tasks.environment import SupportEnvironment
from openai import OpenAI

from som.envelope import Envelope, Implementation, TraceRef, Usage
from som.pricing import lookup
from som.trace import TraceStore

PROMPT = (
    "You are a banking support routing agent. Search the policy knowledge base to identify the policy "
    "governing the customer's request, then use get_policy to read its routing instructions. "
    "Look up the account. Follow the retrieved policy, including whether to verify identity, and route the ticket. "
    "The queue is the department followed by _queue. Preserve any amount and merchant provided. "
    "Do not invent customer information."
)


def instructions_for(prompt_version: str) -> str:
    """Make the visible config-change control an actual system-prompt change."""
    if prompt_version == "original":
        return PROMPT
    if prompt_version == "visible_shift":
        return PROMPT + " Note: the support routing configuration has been revised."
    raise ValueError(f"unknown prompt version: {prompt_version}")


def _tool(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "function",
        "name": name,
        "description": description,
        "parameters": {"type": "object", "properties": properties, "required": required, "additionalProperties": False},
        "strict": False,
    }


def _input_item(value: Any) -> Any:
    """Convert SDK output to valid input items, including older cache recordings."""
    if isinstance(value, dict):
        return {("async" if k == "async_" else k): _input_item(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_input_item(v) for v in value]
    return value


_S = {"type": "string"}
TOOLS = [
    _tool(
        "search_policy", "Search the policy knowledge base; returns the five best matches.", {"query": _S}, ["query"]
    ),
    _tool("get_policy", "Read the complete policy for a selected entry ID.", {"entry_id": _S}, ["entry_id"]),
    _tool("get_account", "Look up the customer account.", {"account_id": _S}, ["account_id"]),
    _tool("verify_identity", "Verify the customer's identity.", {"account_id": _S}, ["account_id"]),
    _tool(
        "route_ticket",
        "Route the customer ticket.",
        {
            "department": _S,
            "priority": _S,
            "queue": _S,
            "note": _S,
            "account_id": _S,
            "amount": {"type": ["number", "null"]},
            "merchant": {"type": ["string", "null"]},
        },
        ["department", "priority", "queue", "note", "account_id"],
    ),
]


class Agent:
    def __init__(
        self,
        model: str,
        *,
        cache: JsonCache,
        budget: Budget,
        store: TraceStore,
        client: Any = None,
        max_steps: int = 8,
        instructions: str = PROMPT,
    ) -> None:
        self.model, self.cache, self.budget, self.store = model, cache, budget, store
        self.client = client or OpenAI(max_retries=0)
        self.max_steps = max_steps
        self.actual_model: str | None = None
        self.instructions = instructions

    def run(self, text: str, env: SupportEnvironment) -> Envelope:
        trace = TraceRef.new()
        messages: list[dict[str, Any]] = [{"role": "user", "content": text}]
        usage = Usage(model_calls=0, tool_calls=0)
        steps: list[dict[str, Any]] = []
        started = time.perf_counter()
        measured_ms = 0.0
        outcome = "stopped_by_limit"
        for _ in range(self.max_steps):
            payload = {
                "model": self.model,
                "instructions": self.instructions,
                "input": messages,
                "tools": TOOLS,
                "max_output_tokens": 800,
                "reasoning": {"effort": "low"},
            }
            new_cost: list[float | None] = []

            def call(payload: dict[str, Any] = payload) -> dict[str, Any]:
                # Reserve headroom before each paid request.
                if self.budget.spent.get("openai", 0.0) + 1.0 > self.budget.caps["openai"]:
                    raise RuntimeError("OpenAI budget reserve exhausted")
                before = time.perf_counter()
                response = self.client.responses.create(**payload)
                elapsed = (time.perf_counter() - before) * 1000
                data = response.model_dump(mode="json", by_alias=True, exclude_none=True)
                u = data.get("usage") or {}
                priced = Usage(
                    input_tokens=u.get("input_tokens", 0),
                    output_tokens=u.get("output_tokens", 0),
                    cached_tokens=(u.get("input_tokens_details") or {}).get("cached_tokens", 0),
                )
                new_cost.append(lookup("openai", self.model).cost(priced).amount)
                return {"response": data, "latency_ms": elapsed}

            recorded = self.cache.get_or_call(payload, call)
            if new_cost:
                self.budget.charge("openai", new_cost[0])
            response = recorded["response"]
            measured_ms += recorded["latency_ms"]
            actual_model = response["model"]
            if self.actual_model is None:
                self.actual_model = actual_model
            if actual_model != self.actual_model:
                raise RuntimeError(f"model changed within run: {self.actual_model} -> {actual_model}")
            u = response.get("usage") or {}
            usage += Usage(
                input_tokens=u.get("input_tokens", 0),
                output_tokens=u.get("output_tokens", 0),
                cached_tokens=(u.get("input_tokens_details") or {}).get("cached_tokens", 0),
                reasoning_tokens=(u.get("output_tokens_details") or {}).get("reasoning_tokens", 0),
                model_calls=1,
            )
            output = response.get("output", [])
            messages.extend(_input_item(output))
            calls = [item for item in output if item.get("type") == "function_call"]
            if not calls:
                outcome = "succeeded" if env.routes else "failed"
                break
            for item in calls:
                name, call_id = item["name"], item["call_id"]
                args = json.loads(item["arguments"])
                try:
                    result = (
                        getattr(env, name)(**args) if name in {t["name"] for t in TOOLS} else {"error": "unknown tool"}
                    )
                except (ValueError, TypeError, KeyError) as exc:
                    result = {"error": str(exc)}
                self.store.add(
                    "agent_step", trace_id=trace.trace_id, input=text, tool=name, arguments=args, result=result
                )
                usage.tool_calls = (usage.tool_calls or 0) + 1
                steps.append(
                    {
                        "index": len(steps),
                        "action": {
                            "type": "tool_call",
                            "call_id": call_id,
                            "tool": {"type": "function", "name": name},
                            "arguments": args,
                        },
                        "observation": {"call_id": call_id, "content": [{"type": "text", "text": json.dumps(result)}]},
                    }
                )
                messages.append({"type": "function_call_output", "call_id": call_id, "output": json.dumps(result)})
            if env.routes:
                outcome = "succeeded"
                break
        cost = lookup("openai", self.model).cost(usage)
        envelope = Envelope(
            system="s4.agentic",
            body={
                "steps": steps,
                "outcome": {"status": outcome},
                "final_output": env.routes[-1] if env.routes else None,
            },
            cost=cost,
            latency_ms=measured_ms or (time.perf_counter() - started) * 1000,
            trace_ref=trace,
            status="completed" if outcome == "succeeded" else "incomplete",
            implementation=Implementation(
                provider="openai", model=self.actual_model or self.model, endpoint="responses"
            ),
        )
        envelope.validate()
        self.store.add_envelope(envelope, input=text)
        return envelope
