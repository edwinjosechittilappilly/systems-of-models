import asyncio
from importlib import import_module

import pytest

from som.gate import Gate
from som.questions import Choice, ChoiceAnswer
from som.testing import FunctionDecider

pytest.importorskip("langchain_core")
Runnable = import_module("langchain_core.runnables").Runnable
RunnableLambda = import_module("langchain_core.runnables").RunnableLambda
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
