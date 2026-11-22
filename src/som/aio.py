"""Run a synchronous gate without blocking the event loop."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from threading import Lock
from weakref import WeakValueDictionary

from som.gate import Gate, GateResult
from som.systems import Input


class AsyncGate:
    """Execute a :class:`Gate` in worker threads, with bounded in-flight calls.

    Cancellation cannot stop an already running synchronous provider call. Its
    semaphore slot remains occupied until the worker actually finishes.
    """

    def __init__(self, gate: Gate, *, max_concurrency: int = 10) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be positive")
        self.gate = gate
        self._max_concurrency = max_concurrency
        self._semaphores: WeakValueDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore] = WeakValueDictionary()
        self._semaphores_lock = Lock()

    async def __call__(self, input: Input, *, metadata: Mapping[str, str] | None = None) -> GateResult:
        loop = asyncio.get_running_loop()
        with self._semaphores_lock:
            semaphore = self._semaphores.get(loop)
            if semaphore is None:
                semaphore = asyncio.Semaphore(self._max_concurrency)
                self._semaphores[loop] = semaphore
        await semaphore.acquire()
        try:
            task = asyncio.create_task(asyncio.to_thread(self.gate, input, metadata=metadata))
        except BaseException:
            semaphore.release()
            raise

        def release(completed: asyncio.Task[GateResult]) -> None:
            semaphore.release()
            if not completed.cancelled():
                completed.exception()

        task.add_done_callback(release)
        return await asyncio.shield(task)

    async def batch(self, inputs: Sequence[Input], *, metadata: Mapping[str, str] | None = None) -> list[GateResult]:
        """Run inputs concurrently and return results in input order."""
        return list(await asyncio.gather(*(self(input, metadata=metadata) for input in inputs)))
