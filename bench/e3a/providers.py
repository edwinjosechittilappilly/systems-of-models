"""Cached E3a teacher, question writer, and Jev providers.

Replaying a cache never constructs an API client.  Costs on results are the
original call costs; the shared budget tracks only new provider spend.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from bench.common.budget import Budget
from bench.common.cache import CACHE_DIR, CachedDecider, JsonCache, Mode
from bench.e3a.agent import Agent, PROMPT
from bench.tasks.environment import PolicyKB, SupportEnvironment
from som.compile.traces import AgentStep, AgentTrace
from som.compile.writer import OpenAIQuestionWriter
from som.envelope import Cost, Envelope, Usage
from som.pricing import lookup
from som.trace import TraceStore

MODEL = "gpt-6.1-terra"


class _OpenAIClient:
    """Defer credentials and client creation until a cache miss."""

    def __init__(self, client: Any = None) -> None:
        self.client = client
        self.responses = self

    def create(self, **kwargs: Any) -> Any:
        if self.client is None:
            from openai import OpenAI
            self.client = OpenAI(max_retries=0)
        return self.client.responses.create(**kwargs)


class _Jev:
    name = "typesafe/jev-1.14.0"
    system = "s1.decision"

    def __init__(self, budget: Budget, client: Any = None) -> None:
        self.budget = budget
        self.client = client
        self.inner: Any = None
        self.pending_cost: float | None = None

    def decide(self, input: Any, questions: Any, *, trace_id: str | None = None) -> Any:
        cap = self.budget.caps.get("typesafe")
        if cap is not None and self.budget.spent.get("typesafe", 0.0) >= cap:
            raise RuntimeError("TypeSafe budget exhausted")
        if self.inner is None:
            from som.adapters.typesafe import TypeSafe
            self.inner = TypeSafe("jev-1.14.0", client=self.client, max_retries=0)
        decision = self.inner.decide(input, questions, trace_id=trace_id)
        self.pending_cost = decision.envelope.cost.amount
        if self.pending_cost is None:
            raise RuntimeError("TypeSafe returned an unpriced decision; cannot book spend")
        return decision


class _BudgetedDecider(CachedDecider):
    def __init__(self, inner: _Jev, cache: JsonCache, budget: Budget) -> None:
        super().__init__(inner, cache)
        self.budget = budget

    def decide(self, input: Any, questions: Any, *, trace_id: str | None = None, sample: int = 0) -> Any:
        self.inner.pending_cost = None
        try:
            return super().decide(input, questions, trace_id=trace_id, sample=sample)
        finally:
            amount = self.inner.pending_cost
            self.inner.pending_cost = None
            if amount is not None:
                self.budget.charge("typesafe", amount)


class _Writer:
    def __init__(self, cache: JsonCache, budget: Budget, client: _OpenAIClient) -> None:
        self.cache, self.budget, self.client = cache, budget, client
        self.last_cost: Cost | None = None
        self.last_latency_ms: float | None = None

    def __call__(self, context: dict[str, Any]) -> dict[str, str]:
        fresh = False

        def call(request: dict[str, Any]) -> dict[str, Any]:
            nonlocal fresh
            if self.budget.spent.get("openai", 0.0) + 1.0 > self.budget.caps["openai"]:
                raise RuntimeError("OpenAI budget reserve exhausted")
            started = time.perf_counter()
            response = self.client.create(**request)
            latency = (time.perf_counter() - started) * 1000
            data = response.model_dump(mode="json", by_alias=True, exclude_none=True)
            data["output_text"] = response.output_text
            fresh = True
            return {"response": data, "latency_ms": latency}

        # OpenAIQuestionWriter builds the canonical request. Its response proxy
        # caches the actual SDK response, including usage, before parsing output.
        owner = self

        class Responses:
            def create(self, **request: Any) -> Any:
                recorded = owner.cache.get_or_call(request, lambda: call(request))
                data = recorded["response"]
                u = data.get("usage")
                if not isinstance(u, dict) or "input_tokens" not in u or "output_tokens" not in u:
                    raise RuntimeError("OpenAI writer returned no usage; cannot book spend")
                usage = Usage(input_tokens=u["input_tokens"], output_tokens=u["output_tokens"],
                              cached_tokens=(u.get("input_tokens_details") or {}).get("cached_tokens", 0),
                              reasoning_tokens=(u.get("output_tokens_details") or {}).get("reasoning_tokens", 0),
                              model_calls=1)
                owner.last_cost = lookup("openai", MODEL).cost(usage)
                owner.last_latency_ms = recorded["latency_ms"]
                if fresh:
                    owner.budget.charge("openai", owner.last_cost.amount)
                return SimpleNamespace(output_text=data.get("output_text"))

        self.last_cost = None
        self.last_latency_ms = None
        return dict(OpenAIQuestionWriter(MODEL, client=SimpleNamespace(responses=Responses()))(context))


@dataclass
class TeacherResult:
    envelope: Envelope
    trace: AgentTrace
    route: dict[str, Any] | None
    verified: bool
    events: list[dict[str, Any]]


class E3aProviders:
    def __init__(self, mode: Mode, budget: Budget, *, cache_dir: Path = CACHE_DIR,
                 openai_client: Any = None, typesafe_client: Any = None) -> None:
        self.budget = budget
        self.client = _OpenAIClient(openai_client)
        self.agent_cache = JsonCache("e3a_agent_v2_gpt-6_1-terra", mode=mode, directory=cache_dir)
        self.s1 = _BudgetedDecider(_Jev(budget, typesafe_client),
                                   JsonCache("e3a_s1_jev", mode=mode, directory=cache_dir), budget)
        self.writer = _Writer(JsonCache("e3a_writer_gpt-6_1-terra", mode=mode, directory=cache_dir),
                              budget, self.client)

    def teacher(self, text: str, account_id: str, kb: PolicyKB, *, instructions: str = PROMPT) -> TeacherResult:
        env, store = SupportEnvironment(kb), TraceStore()
        agent = Agent(MODEL, cache=self.agent_cache, budget=self.budget, store=store,
                      client=self.client, instructions=instructions)
        envelope = agent.run(text, env)
        steps = [AgentStep(r["tool"], r["arguments"], r["result"]) for r in store.of_kind("agent_step")]
        trace = AgentTrace(envelope.trace_ref.trace_id, text, steps)
        verified = False
        for event in env.events:
            if event["tool"] == "route_ticket":
                break
            if event["tool"] == "verify_identity" and event.get("account_id") == account_id:
                verified = True
        return TeacherResult(envelope, trace, env.routes[-1] if env.routes else None, verified, env.events)
