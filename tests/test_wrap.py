"""The wrapper observes SDK calls without changing provider results or requests."""

import asyncio
import warnings
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from som.trace import TraceStore
from som.wrap import envelope_of, wrap


def client(responses=None, chat=None):
    return SimpleNamespace(
        responses=SimpleNamespace(create=responses, with_raw_response=object()),
        chat=SimpleNamespace(completions=SimpleNamespace(create=chat, with_raw_response=object())),
        beta=object(), models=object(),
    )


def test_responses_are_native_and_recorded_with_usage_and_trace():
    response = SimpleNamespace(id="resp_wrap_1", model="gpt-6.1-terra", status="completed", usage=SimpleNamespace(
        input_tokens=100, output_tokens=20, input_tokens_details=SimpleNamespace(cached_tokens=10),
        output_tokens_details=SimpleNamespace(reasoning_tokens=5),
    ))
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
    assert result.implementation.model == response.model
    assert result.latency_ms >= 0
    assert len(result.trace_ref.trace_id) == 32
    assert store.records[0]["envelope"] == result.to_dict()
    result.validate()


def test_chat_unknown_price_warns_and_preserves_call():
    response = SimpleNamespace(id="chat_wrap_1", model="unpriced-model", usage=SimpleNamespace(
        prompt_tokens=12, completion_tokens=3,
    ))
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
    events = [SimpleNamespace(id="stream_chat_1", model="gpt-6.1-terra", usage=None),
              SimpleNamespace(id="stream_chat_1", model="gpt-6.1-terra", usage=usage)]
    native = Stream(events)
    store = TraceStore()
    create = Mock(return_value=native)
    stream = wrap(client(chat=create), store=store).chat.completions.create(
        model="gpt-6.1-terra", messages=[], stream=True, stream_options={"include_usage": True},
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
            model="gpt-6.1-terra", stream=True,
        )
    next(stream)
    stream.close()
    assert envelope_of(stream).status == "incomplete"
    assert envelope_of(stream).cost.usage is None


def test_responses_stream_final_event_usage():
    final = SimpleNamespace(id="response_stream_1", model="gpt-6.1-terra", status="completed", usage=SimpleNamespace(
        input_tokens=5, output_tokens=6,
    ))
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
    monkeypatch.setattr(module, "span", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("broken telemetry")))
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


def test_current_otel_span_is_annotated_without_prompt_text():
    trace = pytest.importorskip("opentelemetry.trace")
    sdk_trace = pytest.importorskip("opentelemetry.sdk.trace")
    provider = sdk_trace.TracerProvider()
    response = SimpleNamespace(id="otel_response", model="gpt-6.1-terra", usage=None)
    with provider.get_tracer("test").start_as_current_span("caller") as current:
        assert wrap(client(responses=Mock(return_value=response))).responses.create(
            model="gpt-6.1-terra", input="private prompt",
        ) is response
        assert trace.get_current_span() is current
        assert current.attributes["gen_ai.response.id"] == "otel_response"
        assert current.attributes["som.system"] == "s2.reasoning"
        assert "private prompt" not in str(current.attributes)
    provider.shutdown()
