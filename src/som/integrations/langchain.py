"""LangChain Runnable integration for a synchronous SOM gate.

Install ``systems-of-models[langchain]`` to use this module.
"""

from __future__ import annotations

from typing import Any

try:
    from langchain_core.runnables import Runnable, RunnableConfig
except ImportError as exc:
    raise ImportError("GateRunnable requires langchain-core; install systems-of-models[langchain]") from exc

from som.aio import AsyncGate
from som.gate import Gate, GateResult
from som.systems import Input


class GateRunnable(Runnable[Input, GateResult]):
    """Expose a gate as a LangChain runnable, preserving its complete result."""

    def __init__(self, gate: Gate, *, max_concurrency: int = 10) -> None:
        self.gate = gate
        self._async_gate = AsyncGate(gate, max_concurrency=max_concurrency)

    def invoke(self, input: Input, config: RunnableConfig | None = None, **kwargs: Any) -> GateResult:
        return self.gate(input)

    async def ainvoke(self, input: Input, config: RunnableConfig | None = None, **kwargs: Any) -> GateResult:
        return await self._async_gate(input)
