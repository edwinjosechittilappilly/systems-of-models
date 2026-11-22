"""Non-invasive observability for OpenAI Responses and Chat Completions calls.

Responses and stream events remain SDK objects. Stream proxies forward the SDK's
iteration, close and context-manager interfaces while observing their lifecycle.
"""

from __future__ import annotations

import inspect
import secrets
import threading
import time
import warnings
import weakref
from collections import OrderedDict
from collections.abc import Mapping
from contextlib import suppress
from typing import Any, cast

from som.adapters._common import envelope, price, s2_body
from som.envelope import Cost, Envelope, SystemId, TraceRef, Usage
from som.trace import TraceStore, _otel, annotate

_CACHE_SIZE = 1024
_cache: OrderedDict[str, tuple[weakref.ReferenceType[Any] | None, Envelope]] = OrderedDict()
# Re-entrant: an unfinished stream collected by the GC while this thread holds the lock records itself via __del__.
_lock = threading.RLock()


def _get(value: Any, *path: str) -> Any:
    for part in path:
        if value is None:
            return None
        value = value.get(part) if isinstance(value, Mapping) else getattr(value, part, None)
    return value


def envelope_of(response: object) -> Envelope | None:
    """Return the recently observed envelope for a response or completed stream, if retained."""
    try:
        response_id = _get(response, "id")
        with _lock:
            if isinstance(response_id, str) and response_id in _cache:
                _cache.move_to_end(response_id)
                return _cache[response_id][1]
            # Snapshot: a stream collected inside this loop may record itself and change the cache.
            entries: list[tuple[str, tuple[weakref.ReferenceType[Any] | None, Envelope]]] = list(_cache.items())
            for key, (observed, result) in reversed(entries):
                if observed is not None and observed() is response:
                    _cache.move_to_end(key)
                    found: Envelope = result
                    return found
    except Exception:
        return None
    return None


class _Observation:
    """A detached span: it never becomes the caller's current span."""

    def __init__(self, model: Any) -> None:
        self.started = time.perf_counter()
        self.otel_span: Any = None
        self.ref = TraceRef(trace_id=secrets.token_hex(16), span_id=secrets.token_hex(8))
        if _otel is not None:
            try:
                current = _otel.get_current_span().get_span_context()
                self.otel_span = _otel.get_tracer("systems-of-models").start_span(f"chat openai/{model}")
                ids = self.otel_span.get_span_context()
                if ids.is_valid:
                    self.ref = TraceRef(trace_id=format(ids.trace_id, "032x"), span_id=format(ids.span_id, "016x"))
                elif current.is_valid:
                    self.ref = TraceRef(trace_id=format(current.trace_id, "032x"), span_id=self.ref.span_id)
            except Exception:
                pass

    def end(self, result: Envelope | None = None) -> None:
        if self.otel_span is not None:
            try:
                if result is not None:
                    with _otel.use_span(self.otel_span, end_on_exit=False):
                        annotate(result, "chat")
            except Exception:
                pass
            finally:
                with suppress(Exception):
                    self.otel_span.end()


def _record(
    target: object,
    response: Any,
    request: Mapping[str, Any],
    endpoint: str,
    observation: _Observation,
    store: TraceStore | None,
    incomplete: bool,
) -> None:
    """Instrumentation must not change a provider call's result or exception."""
    try:
        raw_usage = _get(response, "usage")
        usage = None
        if raw_usage is not None:
            chat = endpoint == "chat"
            input_key = "prompt_tokens" if chat else "input_tokens"
            output_key = "completion_tokens" if chat else "output_tokens"
            usage = Usage(
                input_tokens=int(_get(raw_usage, input_key) or 0),
                output_tokens=int(_get(raw_usage, output_key) or 0),
                cached_tokens=_get(raw_usage, input_key + "_details", "cached_tokens"),
                reasoning_tokens=_get(raw_usage, output_key + "_details", "reasoning_tokens"),
            )
        model = str(_get(response, "model") or request.get("model") or "unknown")
        if usage is None:
            cost = Cost.unknown()
        else:
            try:
                cost = price("openai", model, usage, rate_card=None, fallback_model=request.get("model"))
            except Exception:
                cost = Cost.unknown(usage)
        response_id = _get(response, "id")
        status = _get(response, "status")
        choices = _get(response, "choices") or ()
        chat_incomplete = endpoint == "chat" and any(
            _get(choice, "finish_reason") in ("length", "content_filter") for choice in choices
        )

        def build(ref: TraceRef) -> Envelope:
            system: SystemId = "s2.reasoning"
            return envelope(
                system=system,
                body=s2_body("", None, reasoning_tokens=usage.reasoning_tokens if usage else None, effort=None),
                cost=cost,
                latency_ms=(time.perf_counter() - observation.started) * 1000,
                trace_ref=ref,
                provider="openai",
                model=model,
                endpoint="POST /v1/chat/completions" if endpoint == "chat" else "POST /v1/responses",
                status="incomplete"
                if incomplete or chat_incomplete or status in ("incomplete", "failed", "cancelled")
                else "completed",
                response_id=response_id if isinstance(response_id, str) else None,
            )

        result = build(observation.ref)
        key = response_id if isinstance(response_id, str) and response_id else result.id
        observed: weakref.ReferenceType[Any] | None = None
        if _get(target, "id") != key:
            with suppress(TypeError):
                observed = weakref.ref(target)
        with _lock:
            _cache[key] = (observed, result)
            _cache.move_to_end(key)
            while len(_cache) > _CACHE_SIZE:
                _cache.popitem(last=False)
        if store is not None:
            with suppress(Exception):
                store.add_envelope(result)
        observation.end(result)
    except Exception:
        # Telemetry must never affect the provider's result or exception.
        observation.end()


class _Stream:
    def __init__(
        self,
        stream: Any,
        request: Mapping[str, Any],
        endpoint: str,
        observation: _Observation,
        store: TraceStore | None,
    ) -> None:
        self._stream = stream
        self._request = request
        self._endpoint = endpoint
        self._observation = observation
        self._store = store
        self._response: Any = None
        self._finished = False
        self._terminal = False
        self._incomplete = False
        self._iterator: Any = None

    @property  # type: ignore[misc]  # Proxy class is intentionally read-only.
    def __class__(self) -> type:
        return cast(type, self._stream.__class__)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._stream, name)

    def _observe(self, event: Any) -> None:
        try:
            event_type = _get(event, "type")
            response = _get(event, "response")
            if response is not None:
                self._response = response
                if event_type in ("response.completed", "response.incomplete", "response.failed"):
                    self._terminal = event_type == "response.completed"
            elif self._endpoint == "chat":
                if any(
                    _get(choice, "finish_reason") in ("length", "content_filter")
                    for choice in (_get(event, "choices") or ())
                ):
                    self._incomplete = True
                # The final usage chunk also carries the response id and model.
                if self._response is None or _get(event, "usage") is not None:
                    self._response = event
                if _get(event, "usage") is not None:
                    self._terminal = True
        except Exception:
            pass

    def _finish(self, incomplete: bool) -> None:
        if not self._finished:
            self._finished = True
            _record(
                self,
                self._response,
                self._request,
                self._endpoint,
                self._observation,
                self._store,
                incomplete or self._incomplete,
            )

    def __del__(self) -> None:
        with suppress(Exception):
            self._finish(not self._terminal)

    def __iter__(self) -> _Stream:
        if self._iterator is None:
            self._iterator = iter(self._stream)
        return self

    def __next__(self) -> Any:
        try:
            if self._iterator is None:
                self._iterator = iter(self._stream)
            event = next(self._iterator)
        except StopIteration:
            self._finish(False)
            raise
        except BaseException:
            self._finish(True)
            raise
        self._observe(event)
        return event

    def close(self) -> Any:
        try:
            return self._stream.close()
        finally:
            self._finish(not self._terminal)

    def __enter__(self) -> _Stream:
        self._stream.__enter__()
        return self

    def __exit__(self, *args: Any) -> Any:
        try:
            return self._stream.__exit__(*args)
        finally:
            self._finish(not self._terminal)


class _AsyncStream(_Stream):
    def __aiter__(self) -> _AsyncStream:
        if self._iterator is None:
            self._iterator = self._stream.__aiter__()
        return self

    async def __anext__(self) -> Any:
        try:
            if self._iterator is None:
                self._iterator = self._stream.__aiter__()
            event = await self._iterator.__anext__()
        except StopAsyncIteration:
            self._finish(False)
            raise
        except BaseException:
            self._finish(True)
            raise
        self._observe(event)
        return event

    async def close(self) -> Any:
        try:
            return await self._stream.close()
        finally:
            self._finish(not self._terminal)

    async def __aenter__(self) -> _AsyncStream:
        await self._stream.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> Any:
        try:
            return await self._stream.__aexit__(*args)
        finally:
            self._finish(not self._terminal)


class _Resource:
    def __init__(self, resource: Any, store: TraceStore | None, endpoint: str) -> None:
        self._resource, self._store, self._endpoint = resource, store, endpoint

    @property  # type: ignore[misc]  # Proxy class is intentionally read-only.
    def __class__(self) -> type:
        return cast(type, self._resource.__class__)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._resource, name)

    def create(self, *args: Any, **kwargs: Any) -> Any:
        create = self._resource.create
        if inspect.iscoroutinefunction(inspect.unwrap(create)):
            result = create(*args, **kwargs)

            async def observe() -> Any:
                observation = _Observation(kwargs.get("model", "unknown"))
                try:
                    response = await result
                except BaseException:
                    observation.end()
                    raise
                return self._after(response, kwargs, observation, asynchronous=True)

            return observe()
        observation = _Observation(kwargs.get("model", "unknown"))
        try:
            result = create(*args, **kwargs)
        except BaseException:
            observation.end()
            raise
        if inspect.isawaitable(result):

            async def observe_result() -> Any:
                try:
                    response = await result
                except BaseException:
                    observation.end()
                    raise
                return self._after(response, kwargs, observation, asynchronous=True)

            return observe_result()
        return self._after(result, kwargs, observation, asynchronous=False)

    def _after(
        self, response: Any, request: Mapping[str, Any], observation: _Observation, *, asynchronous: bool
    ) -> Any:
        try:
            if request.get("stream"):
                if self._endpoint == "chat" and not _get(request, "stream_options", "include_usage"):
                    with suppress(Exception):
                        warnings.warn(
                            "Chat streams need stream_options={'include_usage': True} to report usage.", stacklevel=3
                        )
                cls = _AsyncStream if asynchronous else _Stream
                return cls(response, request, self._endpoint, observation, self._store)
            _record(response, response, request, self._endpoint, observation, self._store, False)
        except Exception:
            observation.end()
        return response


class _Chat:
    def __init__(self, chat: Any, store: TraceStore | None) -> None:
        self._chat = chat
        self.completions = _Resource(chat.completions, store, "chat")

    @property  # type: ignore[misc]  # Proxy class is intentionally read-only.
    def __class__(self) -> type:
        return cast(type, self._chat.__class__)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._chat, name)


class _Client:
    def __init__(self, client: Any, store: TraceStore | None) -> None:
        self._client = client
        self.responses = _Resource(client.responses, store, "responses")
        self.chat = _Chat(client.chat, store)
        self._store = store

    @property  # type: ignore[misc]  # Proxy class is intentionally read-only.
    def __class__(self) -> type:
        return cast(type, self._client.__class__)

    def copy(self, *args: Any, **kwargs: Any) -> _Client:
        return _Client(self._client.copy(*args, **kwargs), self._store)

    def with_options(self, *args: Any, **kwargs: Any) -> _Client:
        return _Client(self._client.with_options(*args, **kwargs), self._store)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)

    def __enter__(self) -> _Client:
        self._client.__enter__()
        return self

    def __exit__(self, *args: Any) -> Any:
        return self._client.__exit__(*args)

    async def __aenter__(self) -> _Client:
        await self._client.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> Any:
        return await self._client.__aexit__(*args)


def wrap(client: Any, *, store: TraceStore | None = None) -> Any:
    """Observe OpenAI calls without changing their arguments, responses or other resources."""
    return _Client(client, store)
