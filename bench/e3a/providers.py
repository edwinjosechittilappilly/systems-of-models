"""Cached E3a teacher, question writer, and Jev providers.

Replaying a cache never constructs an API client.  Costs on results are the
original call costs; the shared budget tracks only new provider spend.
"""

from __future__ import annotations

import json
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from bench.common.budget import Budget
from bench.common.cache import CACHE_DIR, CachedDecider, JsonCache, Mode
from bench.e3a.agent import PROMPT, Agent
from bench.e3a.spend import paid_call, request_reserve
from bench.tasks.environment import PolicyKB, SupportEnvironment

from som.compile.traces import AgentStep, AgentTrace
from som.compile.writer import OpenAIQuestionWriter
from som.envelope import Cost, Envelope, Usage
from som.pricing import lookup
from som.trace import TraceStore

MODEL = "gpt-6.1-terra"


class _TokenWindow:
    """Conservatively reserve UTF-8 bytes plus maximum output in a rolling minute."""

    def __init__(self, limit: int = 400_000) -> None:
        self.limit = limit
        self.events: deque[tuple[float, int]] = deque()
        self.lock = threading.Lock()

    def acquire(self, request: dict[str, Any]) -> None:
        estimate = len(json.dumps(request, ensure_ascii=False, default=str).encode()) + int(
            request.get("max_output_tokens", 8000)
        )
        if estimate > self.limit:
            raise ValueError("request exceeds E3a per-minute token reservation")
        while True:
            with self.lock:
                now = time.monotonic()
                while self.events and self.events[0][0] <= now - 60:
                    self.events.popleft()
                if sum(amount for _, amount in self.events) + estimate <= self.limit:
                    self.events.append((now, estimate))
                    return
                delay = max(0.001, self.events[0][0] + 60 - now)
            time.sleep(delay)


_OPENAI_WINDOW = _TokenWindow()


class _OpenAIClient:
    """Defer credentials and client creation until a cache miss."""

    def __init__(self, client: Any = None) -> None:
        self.client = client
        self.responses = self

    def create(self, **kwargs: Any) -> Any:
        _OPENAI_WINDOW.acquire(kwargs)
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

    def decide(self, input: Any, questions: Any, *, trace_id: str | None = None) -> Any:
        if self.inner is None:
            from som.adapters.typesafe import TypeSafe

            self.inner = TypeSafe("jev-1.14.0", client=self.client, max_retries=0)
        body = self.inner.request_body(input, questions)
        if len(json.dumps(body, ensure_ascii=False, default=str).encode("utf-8")) > 100_000:
            raise RuntimeError("TypeSafe request exceeds budget reservation size")
        with paid_call(self.budget, "typesafe", 0.05) as settle:
            decision = self.inner.decide(input, questions, trace_id=trace_id)
            settle(decision.envelope.cost.amount)
            return decision


class _BudgetedDecider(CachedDecider):
    def __init__(self, inner: _Jev, cache: JsonCache, budget: Budget) -> None:
        super().__init__(inner, cache)


class _Writer:
    def __init__(self, cache: JsonCache, budget: Budget, client: _OpenAIClient) -> None:
        self.cache, self.budget, self.client = cache, budget, client
        self.last_cost: Cost | None = None
        self.last_latency_ms: float | None = None
        self.actual_model: str | None = None

    def __call__(self, context: dict[str, Any]) -> dict[str, str]:
        retry = context.get("_e3a_retry")
        context = {key: value for key, value in context.items() if key != "_e3a_retry"}

        def call(request: dict[str, Any]) -> dict[str, Any]:
            with paid_call(self.budget, "openai", request_reserve(request)) as settle:
                started = time.perf_counter()
                response = self.client.create(**request)
                latency = (time.perf_counter() - started) * 1000
                data = response.model_dump(mode="json", by_alias=True, exclude_none=True)
                u = data.get("usage")
                if not isinstance(u, dict) or "input_tokens" not in u or "output_tokens" not in u:
                    raise RuntimeError("OpenAI writer returned no usage; cannot book spend")
                usage = Usage(
                    input_tokens=u["input_tokens"],
                    output_tokens=u["output_tokens"],
                    cached_tokens=(u.get("input_tokens_details") or {}).get("cached_tokens", 0),
                )
                settle(lookup("openai", MODEL).cost(usage).amount)
                data["output_text"] = response.output_text
                return {"response": data, "latency_ms": latency}

        # OpenAIQuestionWriter builds the canonical request. Its response proxy
        # caches the actual SDK response, including usage, before parsing output.
        owner = self

        class Responses:
            def create(self, **request: Any) -> Any:
                request["max_output_tokens"] = 2048
                request["instructions"] += (
                    " Return short strings only: at most 12 words for the name and 40 words for each other field."
                )
                if "choices" in context:
                    schema = request["text"]["format"]["schema"]
                    schema["properties"] = {key: schema["properties"][key] for key in ("name", "instructions")}
                    schema["required"] = ["name", "instructions"]
                key = request if retry is None else {"request": request, "retry": retry}
                recorded = owner.cache.get_or_call(key, lambda: call(request))
                data = recorded["response"]
                u = data.get("usage")
                if not isinstance(u, dict) or "input_tokens" not in u or "output_tokens" not in u:
                    raise RuntimeError("OpenAI writer returned no usage; cannot book spend")
                usage = Usage(
                    input_tokens=u["input_tokens"],
                    output_tokens=u["output_tokens"],
                    cached_tokens=(u.get("input_tokens_details") or {}).get("cached_tokens", 0),
                    reasoning_tokens=(u.get("output_tokens_details") or {}).get("reasoning_tokens", 0),
                    model_calls=1,
                )
                owner.last_cost = lookup("openai", MODEL).cost(usage)
                owner.last_latency_ms = recorded["latency_ms"]
                actual = data.get("model")
                if not isinstance(actual, str) or not actual:
                    raise RuntimeError("writer response does not identify a model")
                if owner.actual_model is None:
                    owner.actual_model = actual
                elif owner.actual_model != actual:
                    raise RuntimeError(f"writer model changed: {owner.actual_model} -> {actual}")
                if data.get("status") == "incomplete":
                    raise ValueError(f"writer response incomplete: {data.get('incomplete_details')}")
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
    def __init__(
        self,
        mode: Mode,
        budget: Budget,
        *,
        cache_dir: Path = CACHE_DIR,
        openai_client: Any = None,
        typesafe_client: Any = None,
    ) -> None:
        self.budget = budget
        self.actual_model: str | None = None
        self._model_lock = threading.Lock()
        self.client = _OpenAIClient(openai_client)
        self.agent_cache = JsonCache("e3a_agent_v2_gpt-6_1-terra", mode=mode, directory=cache_dir)
        self.s1 = _BudgetedDecider(
            _Jev(budget, typesafe_client), JsonCache("e3a_s1_jev", mode=mode, directory=cache_dir), budget
        )
        self.writer = _Writer(
            JsonCache("e3a_writer_gpt-6_1-terra", mode=mode, directory=cache_dir), budget, self.client
        )

    def teacher(
        self, text: str, account_id: str, kb: PolicyKB, *, instructions: str = PROMPT, sample: int = 0
    ) -> TeacherResult:
        env, store = SupportEnvironment(kb), TraceStore()
        agent = Agent(
            MODEL,
            cache=self.agent_cache,
            budget=self.budget,
            store=store,
            client=self.client,
            instructions=instructions,
            sample=sample,
        )
        envelope = agent.run(text, env)
        actual = envelope.implementation.model if envelope.implementation else None
        if actual is None:
            raise RuntimeError("teacher response does not identify a model")
        with self._model_lock:
            if self.actual_model is None:
                self.actual_model = actual
            elif self.actual_model != actual:
                raise RuntimeError(f"teacher model changed: {self.actual_model} -> {actual}")
        steps = [AgentStep(r["tool"], r["arguments"], r["result"]) for r in store.of_kind("agent_step")]
        trace = AgentTrace(envelope.trace_ref.trace_id, text, steps)
        verified = False
        for event in env.events:
            if event["tool"] == "route_ticket":
                break
            if event["tool"] == "verify_identity" and event.get("account_id") == account_id:
                verified = True
        return TeacherResult(envelope, trace, env.routes[-1] if env.routes else None, verified, env.events)
