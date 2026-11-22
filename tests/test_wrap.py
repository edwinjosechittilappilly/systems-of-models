"""The wrapper observes SDK calls without changing provider results or requests."""

import asyncio
import gc
import json
import time
import warnings
import weakref
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import openai
import pytest

from som.trace import TraceStore
from som.wrap import envelope_of, wrap


def client(responses=None, chat=None):
    return SimpleNamespace(
        responses=SimpleNamespace(create=responses, with_raw_response=object()),
        chat=SimpleNamespace(completions=SimpleNamespace(create=chat, with_raw_response=object())),
        beta=object(),
        models=object(),
    )


def test_responses_are_native_and_recorded_with_usage_and_trace():
    response = SimpleNamespace(
        id="resp_wrap_1",
        model="gpt-6.1-terra",
        status="completed",
        usage=SimpleNamespace(
            input_tokens=100,
            output_tokens=20,
            input_tokens_details=SimpleNamespace(cached_tokens=10),
            output_tokens_details=SimpleNamespace(reasoning_tokens=5),
        ),
    )
    create = Mock(return_value=response)
    store = TraceStore()
    observed = wrap(client(responses=create), store=store)
    assert observed.responses.create(model="gpt-6.1-terra", input="hello") is response
    create.assert_called_once_with(model="gpt-6.1-terra", input="hello")
    result = envelope_of(response)
    assert result is not None
    assert result.system == "s2.reasoning"
    assert result.id == response.id
    assert result.cost.usage.input_tokens == 100
    assert result.cost.usage.reasoning_tokens == 5
    assert result.body["reasoning"]["reasoning_tokens"] == 5
    assert result.implementation.model == response.model
    assert result.latency_ms >= 0
    assert len(result.trace_ref.trace_id) == 32
    assert store.records[0]["envelope"] == result.to_dict()
    result.validate()


def test_chat_unknown_price_warns_and_preserves_call():
    response = SimpleNamespace(
        id="chat_wrap_1",
        model="unpriced-model",
        usage=SimpleNamespace(
            prompt_tokens=12,
            completion_tokens=3,
        ),
    )
    create = Mock(return_value=response)
    with pytest.warns(UserWarning, match="no rate card"):
        assert wrap(client(chat=create)).chat.completions.create(model="unpriced-model", messages=[]) is response
    create.assert_called_once_with(model="unpriced-model", messages=[])
    result = envelope_of(response)
    assert result.cost.basis == "unknown"
    assert result.cost.usage.input_tokens == 12
    assert result.implementation.endpoint == "POST /v1/chat/completions"


def test_public_resources_and_non_create_methods_are_delegated():
    sdk = pytest.importorskip("openai")
    original = sdk.OpenAI(api_key="unused")
    observed = wrap(original)
    for name in ("models", "files", "audio", "images", "embeddings", "beta", "batches"):
        assert getattr(observed, name) is getattr(original, name)
    assert observed.responses.with_raw_response is original.responses.with_raw_response
    assert observed.chat.completions.with_raw_response is original.chat.completions.with_raw_response
    assert observed.responses.retrieve == original.responses.retrieve
    assert observed.chat.completions.retrieve == original.chat.completions.retrieve
    original.close()


class Stream:
    def __init__(self, events):
        self.events = iter(events)
        self.closed = False

    def __iter__(self):
        return self.events

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def test_stream_yields_native_events_and_records_final_usage():
    usage = SimpleNamespace(prompt_tokens=30, completion_tokens=4)
    events = [
        SimpleNamespace(id="stream_chat_1", model="gpt-6.1-terra", usage=None),
        SimpleNamespace(id="stream_chat_1", model="gpt-6.1-terra", usage=usage),
    ]
    native = Stream(events)
    store = TraceStore()
    create = Mock(return_value=native)
    stream = wrap(client(chat=create), store=store).chat.completions.create(
        model="gpt-6.1-terra",
        messages=[],
        stream=True,
        stream_options={"include_usage": True},
    )
    assert envelope_of(stream) is None
    assert list(stream) == events
    result = envelope_of(stream)
    assert result.status == "completed"
    assert result.cost.usage.output_tokens == 4
    assert len(store.records) == 1
    stream.close()
    assert native.closed and len(store.records) == 1


def test_early_stream_close_is_incomplete_and_chat_hints_usage():
    native = Stream([SimpleNamespace(id="early", model="gpt-6.1-terra", usage=None)])
    with pytest.warns(UserWarning, match="include_usage"):
        stream = wrap(client(chat=Mock(return_value=native))).chat.completions.create(
            model="gpt-6.1-terra",
            stream=True,
        )
    next(stream)
    stream.close()
    assert envelope_of(stream).status == "incomplete"
    assert envelope_of(stream).cost.usage is None


def test_responses_stream_final_event_usage():
    final = SimpleNamespace(
        id="response_stream_1",
        model="gpt-6.1-terra",
        status="completed",
        usage=SimpleNamespace(
            input_tokens=5,
            output_tokens=6,
        ),
    )
    event = SimpleNamespace(type="response.completed", response=final)
    native = Stream([event])
    stream = wrap(client(responses=Mock(return_value=native))).responses.create(model="gpt-6.1-terra", stream=True)
    with stream as current:
        assert next(current) is event
    assert envelope_of(stream).status == "completed"
    assert envelope_of(stream).cost.usage.output_tokens == 6


def test_instrumentation_errors_do_not_change_result_or_provider_exception(monkeypatch):
    import importlib

    module = importlib.import_module("som.wrap")
    response = SimpleNamespace(id="safe_1", model="unknown", usage=SimpleNamespace(input_tokens=1, output_tokens=1))
    monkeypatch.setattr(module, "annotate", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("telemetry")))
    store = Mock()
    store.add_envelope.side_effect = RuntimeError("broken store")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        observed = wrap(client(responses=Mock(return_value=response)), store=store)
        assert observed.responses.create(model="unknown") is response
    assert envelope_of(response).cost.basis == "unknown"
    failure = RuntimeError("provider failed")
    with pytest.raises(RuntimeError) as caught:
        wrap(client(responses=Mock(side_effect=failure))).responses.create(model="x")
    assert caught.value is failure


def test_cache_is_bounded_and_uses_response_ids():
    responses = [SimpleNamespace(id=f"cache_{i}", model="gpt-6.1-terra", usage=None) for i in range(1026)]
    observed = wrap(client(responses=Mock(side_effect=responses)))
    for response in responses:
        assert observed.responses.create(model="gpt-6.1-terra") is response
    assert envelope_of(responses[0]) is None
    assert envelope_of(SimpleNamespace(id="cache_1025")) is envelope_of(responses[-1])


def test_async_calls_and_streams():
    class AsyncStream:
        def __init__(self, event):
            self.event = event
            self.closed = False

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.event is None:
                raise StopAsyncIteration
            event, self.event = self.event, None
            return event

        async def close(self):
            self.closed = True

    async def exercise():
        response = SimpleNamespace(id="async_1", model="gpt-6.1-terra", usage=None)
        event = SimpleNamespace(type="response.completed", response=response)
        native = AsyncStream(event)

        async def create(**kwargs):
            return native if kwargs.get("stream") else response

        observed = wrap(client(responses=create))
        assert await observed.responses.create(model="gpt-6.1-terra") is response
        stream = await observed.responses.create(model="gpt-6.1-terra", stream=True)
        assert [item async for item in stream] == [event]
        assert envelope_of(stream).status == "completed"
        await stream.close()
        assert native.closed

    asyncio.run(exercise())


def test_otel_child_spans_cover_calls_and_streams_without_contaminating_parent(monkeypatch):
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test")
    monkeypatch.setattr(trace, "get_tracer", lambda *args, **kwargs: tracer)
    times = []

    def transport(request):
        times.append(time.time_ns())
        return _chat_http_response(request)

    store = TraceStore()
    native = openai.OpenAI(api_key="unused", http_client=httpx.Client(transport=httpx.MockTransport(transport)))
    observed = wrap(native, store=store)
    with tracer.start_as_current_span("caller") as parent:
        result = observed.chat.completions.create(
            model="gpt-6.1-terra", messages=[{"role": "user", "content": "private prompt"}]
        )
        stream = observed.chat.completions.create(
            model="gpt-6.1-terra", messages=[], stream=True, stream_options={"include_usage": True}
        )
        assert trace.get_current_span() is parent
        assert len(exporter.get_finished_spans()) == 1
        list(stream)
        assert trace.get_current_span() is parent
        assert not any(key.startswith(("gen_ai.", "som.")) for key in parent.attributes)
    spans = exporter.get_finished_spans()
    children = [item for item in spans if item.name != "caller"]
    assert len(children) == 2
    for child, during_call in zip(children, times, strict=True):
        assert child.parent.span_id == parent.get_span_context().span_id
        assert child.start_time <= during_call <= child.end_time
        assert child.attributes["gen_ai.response.id"] == result.id
        assert "private prompt" not in str(child.attributes)
    assert children[1].end_time >= times[1]
    assert envelope_of(stream).trace_ref.span_id == format(children[1].context.span_id, "016x")
    native.close()
    provider.shutdown()


def _chat_http_response(request):
    payload = json.loads(request.content)
    if payload.get("stream"):
        chunks = [
            {
                "id": "chat_real",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": "gpt-6.1-terra",
                "choices": [{"index": 0, "delta": {"content": "hello"}, "finish_reason": None}],
            },
            {
                "id": "chat_real",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": "gpt-6.1-terra",
                "choices": [{"index": 0, "delta": {}, "finish_reason": "length"}],
            },
            {
                "id": "chat_real",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": "gpt-6.1-terra",
                "choices": [],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 3,
                    "total_tokens": 13,
                    "completion_tokens_details": {"reasoning_tokens": 2},
                },
            },
        ]
        body = "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks) + "data: [DONE]\n\n"
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=body)
    return httpx.Response(
        200,
        json={
            "id": "chat_real",
            "object": "chat.completion",
            "created": 1,
            "model": "gpt-6.1-terra",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "hello"}, "finish_reason": "length"}],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 3,
                "total_tokens": 13,
                "completion_tokens_details": {"reasoning_tokens": 2},
            },
        },
    )


def test_real_openai_copy_stream_lifecycle_and_weak_cache():
    store = TraceStore()
    native = openai.OpenAI(
        api_key="unused", http_client=httpx.Client(transport=httpx.MockTransport(_chat_http_response))
    )
    observed = wrap(native, store=store)
    assert isinstance(observed, openai.OpenAI)
    for derived in (observed.copy(), observed.with_options(timeout=1)):
        assert isinstance(derived, openai.OpenAI)
        response = derived.chat.completions.create(model="gpt-6.1-terra", messages=[])
        result = envelope_of(response)
        assert result.status == "incomplete"
        assert result.body["reasoning"]["reasoning_tokens"] == 2
    response_ref = weakref.ref(response)
    del response
    gc.collect()
    assert response_ref() is None
    assert len(store.records) == 2
    stream = observed.chat.completions.create(
        model="gpt-6.1-terra", messages=[], stream=True, stream_options={"include_usage": True}
    )
    assert isinstance(stream, openai.Stream)
    assert len(list(stream)) == 3
    result = envelope_of(stream)
    assert result.status == "incomplete"
    assert result.body["reasoning"]["reasoning_tokens"] == 2
    stream_ref = weakref.ref(stream)
    del stream
    gc.collect()
    assert stream_ref() is None
    assert len(store.records) == 3
    abandoned = observed.chat.completions.create(
        model="gpt-6.1-terra", messages=[], stream=True, stream_options={"include_usage": True}
    )
    next(abandoned)
    del abandoned
    gc.collect()
    assert len(store.records) == 4
    assert store.records[-1]["envelope"]["status"] == "incomplete"
    native.close()


def test_collecting_an_unfinished_stream_while_holding_the_cache_lock_does_not_deadlock():
    import threading

    from som import wrap as wrap_module

    native = openai.OpenAI(
        api_key="unused", http_client=httpx.Client(transport=httpx.MockTransport(_chat_http_response))
    )
    store = TraceStore()
    stream = wrap(native, store=store).chat.completions.create(
        model="gpt-6.1-terra", messages=[], stream=True, stream_options={"include_usage": True}
    )
    next(stream)
    cycle: dict[str, object] = {"stream": stream}
    cycle["self"] = cycle  # only the cyclic collector can free the stream now
    del stream, cycle

    def collect_under_lock() -> None:
        with wrap_module._lock:
            gc.collect()

    worker = threading.Thread(target=collect_under_lock, daemon=True)
    worker.start()
    worker.join(timeout=5)
    assert not worker.is_alive()
    assert store.records[-1]["envelope"]["status"] == "incomplete"
    native.close()


def test_real_async_openai_stream_and_early_collection():
    async def exercise():
        store = TraceStore()
        transport = httpx.MockTransport(_chat_http_response)
        native = openai.AsyncOpenAI(api_key="unused", http_client=httpx.AsyncClient(transport=transport))
        observed = wrap(native, store=store)
        assert isinstance(observed, openai.AsyncOpenAI)
        derived = observed.with_options(timeout=1).copy()
        response = await derived.chat.completions.create(model="gpt-6.1-terra", messages=[])
        assert envelope_of(response).status == "incomplete"
        stream = await observed.chat.completions.create(
            model="gpt-6.1-terra", messages=[], stream=True, stream_options={"include_usage": True}
        )
        assert isinstance(stream, openai.AsyncStream)
        assert len([event async for event in stream]) == 3
        assert envelope_of(stream).status == "incomplete"
        assert envelope_of(stream).cost.usage.reasoning_tokens == 2
        assert len(store.records) == 2
        abandoned = await observed.chat.completions.create(
            model="gpt-6.1-terra", messages=[], stream=True, stream_options={"include_usage": True}
        )
        await abandoned.__anext__()
        del abandoned
        gc.collect()
        assert len(store.records) == 3
        assert store.records[-1]["envelope"]["status"] == "incomplete"
        await native.close()

    asyncio.run(exercise())


def test_responses_stream_from_real_sdk_records_final_response():
    final = {
        "id": "resp_stream_real",
        "object": "response",
        "created_at": 1,
        "status": "completed",
        "model": "gpt-6.1-terra",
        "output": [],
        "usage": {
            "input_tokens": 5,
            "output_tokens": 6,
            "total_tokens": 11,
            "input_tokens_details": {"cached_tokens": 1},
            "output_tokens_details": {"reasoning_tokens": 2},
        },
    }
    event = {"type": "response.completed", "sequence_number": 1, "response": final}
    body = f"data: {json.dumps(event)}\n\ndata: [DONE]\n\n"
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, headers={"content-type": "text/event-stream"}, content=body)
    )
    native = openai.OpenAI(api_key="unused", http_client=httpx.Client(transport=transport))
    store = TraceStore()
    with wrap(native, store=store).responses.create(model="gpt-6.1-terra", input="hi", stream=True) as stream:
        assert next(stream).type == "response.completed"
    result = envelope_of(stream)
    assert result.status == "completed"
    assert result.cost.usage.input_tokens == 5
    assert result.body["reasoning"]["reasoning_tokens"] == 2
    assert len(store.records) == 1
    native.close()


def test_async_otel_stream_keeps_caller_current_until_close(monkeypatch):
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    async def exercise():
        provider = TracerProvider()
        exporter = InMemorySpanExporter()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        tracer = provider.get_tracer("async-test")
        monkeypatch.setattr(trace, "get_tracer", lambda *args, **kwargs: tracer)
        native = openai.AsyncOpenAI(
            api_key="unused", http_client=httpx.AsyncClient(transport=httpx.MockTransport(_chat_http_response))
        )
        pending = wrap(native).chat.completions.create(
            model="gpt-6.1-terra", messages=[], stream=True, stream_options={"include_usage": True}
        )
        with tracer.start_as_current_span("caller") as parent:
            stream = await pending
            async with stream:
                await stream.__anext__()
                assert trace.get_current_span() is parent
                assert not exporter.get_finished_spans()
            assert trace.get_current_span() is parent
            assert not parent.attributes
            assert envelope_of(stream).status == "incomplete"
        child = next(item for item in exporter.get_finished_spans() if item.name != "caller")
        assert child.parent.span_id == parent.get_span_context().span_id
        assert child.attributes["som.status"] == "incomplete"
        await native.close()
        provider.shutdown()

    asyncio.run(exercise())
