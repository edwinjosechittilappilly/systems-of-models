import asyncio
import threading
import time

import pytest

from som.aio import AsyncGate
from som.gate import Gate
from som.questions import Choice, ChoiceAnswer
from som.testing import FunctionDecider
from som.trace import TraceStore

QUESTION = Choice("team", "Which team?", ["billing", "cards"])


def make_gate(probability=0.6, *, store=None):
    s1 = FunctionDecider(
        lambda _input, q: ChoiceAnswer(q.name, "billing", {"billing": probability, "cards": 1 - probability})
    )
    s2 = FunctionDecider(lambda _input, q: ChoiceAnswer(q.name, "cards"), system="s2.reasoning")
    return Gate(s1, s2, QUESTION, store=store)


def test_async_gate_preserves_escalation_and_metadata():
    store = TraceStore()
    gate = AsyncGate(make_gate(store=store))
    result = asyncio.run(gate("ticket", metadata={"source": "test"}))
    assert (result.value, result.served_by) == ("cards", "s2")
    assert result.escalation.reason == "low_confidence"
    assert result.s2.envelope.trace_ref.trace_id == result.s1.envelope.trace_ref.trace_id
    assert store.of_kind("gate")[0]["metadata"]["source"] == "test"


def test_async_gate_preserves_shadow_mode():
    gate = make_gate(probability=0.99)
    gate.mode = "shadow"
    result = asyncio.run(AsyncGate(gate)("ticket"))
    assert (result.served_by, result.value, result.escalation) == ("s2", "cards", None)


def test_async_gate_propagates_provider_error_and_releases_slot():
    def answer(input, question):
        if input == "bad":
            raise RuntimeError("provider failed")
        return ChoiceAnswer(question.name, "billing", {"billing": 1.0})

    async def exercise():
        gate = AsyncGate(Gate(FunctionDecider(answer), make_gate().s2, QUESTION), max_concurrency=1)
        with pytest.raises(RuntimeError, match="provider failed"):
            await gate("bad")
        assert (await gate("good")).value == "billing"

    asyncio.run(exercise())


def test_async_batch_preserves_input_order():
    s1 = FunctionDecider(lambda input, q: ChoiceAnswer(q.name, str(input), {str(input): 1.0}))
    s2 = FunctionDecider(lambda _input, q: ChoiceAnswer(q.name, "cards"), system="s2.reasoning")
    results = asyncio.run(AsyncGate(Gate(s1, s2, QUESTION), max_concurrency=2).batch(["cards", "billing"]))
    assert [result.value for result in results] == ["cards", "billing"]


def test_async_gate_rejects_nonpositive_concurrency():
    with pytest.raises(ValueError, match="max_concurrency"):
        AsyncGate(make_gate(), max_concurrency=0)


def test_cancelled_call_holds_slot_until_worker_finishes():
    async def exercise():
        loop = asyncio.get_running_loop()
        started = asyncio.Event()
        second_started = asyncio.Event()
        release = threading.Event()

        def answer(input, q):
            if input == "first":
                loop.call_soon_threadsafe(started.set)
                if not release.wait(5):
                    raise TimeoutError("worker was not released")
            else:
                loop.call_soon_threadsafe(second_started.set)
            return ChoiceAnswer(q.name, "billing", {"billing": 1.0})

        gate = AsyncGate(Gate(FunctionDecider(answer), make_gate().s2, QUESTION), max_concurrency=1)
        first = asyncio.create_task(gate("first"))
        try:
            await asyncio.wait_for(started.wait(), 2)
            first.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first
            second = asyncio.create_task(gate("second"))
            await asyncio.sleep(0.05)
            assert not second_started.is_set()
            release.set()
            result = await asyncio.wait_for(second, 2)
            assert result.value == "billing"
            assert second_started.is_set()
        finally:
            release.set()

    asyncio.run(exercise())


def test_async_gate_can_be_reused_under_contention_across_event_loops():
    def answer(_input, question):
        time.sleep(0.03)
        return ChoiceAnswer(question.name, "billing", {"billing": 1.0})

    gate = AsyncGate(Gate(FunctionDecider(answer), make_gate().s2, QUESTION), max_concurrency=1)

    async def exercise():
        return await gate.batch(["one", "two", "three"])

    for _ in range(2):
        assert [result.value for result in asyncio.run(exercise())] == ["billing"] * 3
