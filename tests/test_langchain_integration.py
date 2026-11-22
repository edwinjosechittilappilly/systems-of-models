import asyncio
import threading
import time
from importlib import import_module

import pytest

from som.gate import Gate
from som.questions import Choice, ChoiceAnswer
from som.testing import FunctionDecider

pytest.importorskip("langchain_core")
Runnable = import_module("langchain_core.runnables").Runnable
RunnableLambda = import_module("langchain_core.runnables").RunnableLambda
BaseCallbackHandler = import_module("langchain_core.callbacks").BaseCallbackHandler
GateRunnable = import_module("som.integrations.langchain").GateRunnable


def make_runnable():
    question = Choice("team", "Which team?", ["billing", "cards"])
    s1 = FunctionDecider(lambda _input, q: ChoiceAnswer(q.name, "billing", {"billing": 0.6, "cards": 0.4}))
    s2 = FunctionDecider(lambda _input, q: ChoiceAnswer(q.name, "cards"), system="s2.reasoning")
    return GateRunnable(Gate(s1, s2, question), max_concurrency=2)


def test_runnable_supports_invoke_batch_and_composition():
    runnable = make_runnable()
    assert isinstance(runnable, Runnable)
    assert runnable.invoke("ticket").served_by == "s2"
    assert [result.value for result in runnable.batch(["one", "two"])] == ["cards", "cards"]
    chain = runnable | RunnableLambda(lambda result: result.value)
    assert chain.invoke("ticket") == "cards"


def test_runnable_supports_async_invoke_and_batch():
    async def exercise():
        runnable = make_runnable()
        assert (await runnable.ainvoke("ticket")).value == "cards"
        results = await runnable.abatch(["one", "two"])
        assert [result.served_by for result in results] == ["s2", "s2"]

    asyncio.run(exercise())


class RecordingHandler(BaseCallbackHandler):
    def __init__(self):
        self.starts = []
        self.ends = []
        self.errors = []

    def on_chain_start(self, serialized, inputs, **kwargs):
        self.starts.append((inputs, kwargs["tags"], kwargs["metadata"]))

    def on_chain_end(self, outputs, **kwargs):
        self.ends.append(outputs)

    def on_chain_error(self, error, **kwargs):
        self.errors.append(error)


def test_runnable_propagates_config_to_sync_and_async_callbacks():
    runnable = make_runnable()
    handler = RecordingHandler()
    config = {"callbacks": [handler], "tags": ["ticket"], "metadata": {"source": "test"}}

    sync_result = runnable.invoke("sync", config=config)
    async_result = asyncio.run(runnable.ainvoke("async", config=config))

    assert handler.starts == [
        ("sync", ["ticket"], {"source": "test"}),
        ("async", ["ticket"], {"source": "test"}),
    ]
    assert handler.ends == [sync_result, async_result]
    assert not handler.errors


def test_runnable_reports_provider_errors_to_callbacks():
    def fail(_input, _question):
        raise ValueError("provider failed")

    question = Choice("team", "Which team?", ["billing", "cards"])
    runnable = GateRunnable(Gate(FunctionDecider(fail), make_runnable().gate.s2, question))
    handler = RecordingHandler()
    config = {"callbacks": [handler]}
    with pytest.raises(ValueError, match="provider failed"):
        runnable.invoke("sync", config=config)
    with pytest.raises(ValueError, match="provider failed"):
        asyncio.run(runnable.ainvoke("async", config=config))
    assert [str(error) for error in handler.errors] == ["provider failed", "provider failed"]
    assert not handler.ends


def test_runnable_sync_batch_respects_concurrency_and_per_input_config():
    lock = threading.Lock()
    active = 0
    peak = 0

    def answer(_input, question):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        try:
            time.sleep(0.03)
            return ChoiceAnswer(question.name, "billing", {"billing": 1.0})
        finally:
            with lock:
                active -= 1

    question = Choice("team", "Which team?", ["billing", "cards"])
    runnable = GateRunnable(Gate(FunctionDecider(answer), make_runnable().gate.s2, question), max_concurrency=2)
    handler = RecordingHandler()
    configs = [{"callbacks": [handler], "metadata": {"item": index}, "max_concurrency": 8} for index in range(4)]
    results = runnable.batch(["one", "two", "three", "four"], config=configs)
    assert [result.value for result in results] == ["billing"] * 4
    assert 1 < peak <= 2
    assert sorted(start[2]["item"] for start in handler.starts) == [0, 1, 2, 3]
    assert len(handler.ends) == 4
    assert configs[0]["max_concurrency"] == 8

    peak = 0
    runnable.batch(["one", "two"], config={"max_concurrency": 1})
    assert peak == 1


def test_runnable_async_batch_can_be_reused_across_event_loops():
    def answer(_input, question):
        time.sleep(0.03)
        return ChoiceAnswer(question.name, "billing", {"billing": 1.0})

    question = Choice("team", "Which team?", ["billing", "cards"])
    runnable = GateRunnable(Gate(FunctionDecider(answer), make_runnable().gate.s2, question), max_concurrency=1)

    async def exercise():
        return await runnable.abatch(["one", "two", "three"])

    for _ in range(2):
        assert [result.value for result in asyncio.run(exercise())] == ["billing"] * 3
