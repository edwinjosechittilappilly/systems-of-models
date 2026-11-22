"""LangChain Runnable integration for a synchronous SOM gate.

Install ``systems-of-models[langchain]`` to use this module.
"""

from __future__ import annotations

from typing import Any

try:
    from langchain_core.runnables import Runnable, RunnableConfig
    from langchain_core.runnables.config import get_config_list
except ImportError as exc:
    raise ImportError("GateRunnable requires langchain-core; install systems-of-models[langchain]") from exc

from som.aio import AsyncGate
from som.gate import Gate, GateResult
from som.systems import Input


class GateRunnable(Runnable[Input, GateResult]):
    """Expose a gate as a LangChain runnable, preserving its complete result.

    ``max_concurrency`` bounds each synchronous batch and in-flight async calls
    per event loop. A lower LangChain batch configuration is also respected.
    """

    def __init__(self, gate: Gate, *, max_concurrency: int = 10) -> None:
        self.gate = gate
        self._max_concurrency = max_concurrency
        self._async_gate = AsyncGate(gate, max_concurrency=max_concurrency)

    def invoke(self, input: Input, config: RunnableConfig | None = None, **kwargs: Any) -> GateResult:
        return self._call_with_config(self.gate, input, config)

    async def ainvoke(self, input: Input, config: RunnableConfig | None = None, **kwargs: Any) -> GateResult:
        return await self._acall_with_config(self._async_gate, input, config)

    def batch(
        self,
        inputs: list[Input],
        config: RunnableConfig | list[RunnableConfig] | None = None,
        *,
        return_exceptions: bool = False,
        **kwargs: Any,
    ) -> list[GateResult]:
        if not inputs:
            return []
        configs = get_config_list(config, len(inputs))
        configured_max = configs[0].get("max_concurrency")
        configs[0]["max_concurrency"] = (
            min(configured_max, self._max_concurrency) if configured_max is not None else self._max_concurrency
        )
        return super().batch(inputs, configs, return_exceptions=return_exceptions, **kwargs)
