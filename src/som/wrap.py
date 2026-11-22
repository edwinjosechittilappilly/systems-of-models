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
from collections import OrderedDict
from collections.abc import Mapping
from contextlib import suppress
from typing import Any

from som.adapters._common import envelope, price, s2_body
from som.envelope import Cost, Envelope, SystemId, TraceRef, Usage
from som.trace import TraceStore, annotate, span

_CACHE_SIZE = 1024
_cache: OrderedDict[str, tuple[object, Envelope]] = OrderedDict()
_lock = threading.Lock()


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
            for key, (observed, result) in reversed(_cache.items()):
                if observed is response:
                    _cache.move_to_end(key)
                    return result
    except Exception:
        return None
    return None


def _record(
    target: object,
    response: Any,
    request: Mapping[str, Any],
    endpoint: str,
    started: float,
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

        def build(ref: TraceRef) -> Envelope:
            system: SystemId = "s2.reasoning"
            return envelope(
                system=system,
                body=s2_body("", None, reasoning_tokens=None, effort=None),
                cost=cost,
                latency_ms=(time.perf_counter() - started) * 1000,
                trace_ref=ref,
                provider="openai",
                model=model,
                endpoint="POST /v1/chat/completions" if endpoint == "chat" else "POST /v1/responses",
                status="incomplete" if incomplete or status in ("incomplete", "failed", "cancelled") else "completed",
                response_id=response_id if isinstance(response_id, str) else None,
            )

        result = None
        try:
            with span(f"chat openai/{model}") as ref:
                result = build(ref)
                with suppress(Exception):
                    annotate(result, "chat")
        except Exception:
            pass
        if result is None:
            result = build(TraceRef(trace_id=secrets.token_hex(16), span_id=secrets.token_hex(8)))
        key = response_id if isinstance(response_id, str) and response_id else result.id
        with _lock:
            _cache[key] = (target, result)
            _cache.move_to_end(key)
            while len(_cache) > _CACHE_SIZE:
                _cache.popitem(last=False)
        if store is not None:
            with suppress(Exception):
                store.add_envelope(result)
        with suppress(Exception):
            annotate(result, "chat")
    except Exception:
        # A telemetry backend, malformed provider object or warning-as-error must
        # never affect the application using the wrapped SDK.
        pass


class _Stream:
    def __init__(
        self, stream: Any, request: Mapping[str, Any], endpoint: str, started: float, store: TraceStore | None
    ) -> None:
        self._stream = stream
        self._request = request
        self._endpoint = endpoint
        self._started = started
        self._store = store
        self._response: Any = None
        self._finished = False
        self._terminal = False
        self._iterator: Any = None

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
            _record(self, self._response, self._request, self._endpoint, self._started, self._store, incomplete)

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

    def __getattr__(self, name: str) -> Any:
        return getattr(self._resource, name)

    def create(self, *args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        result = self._resource.create(*args, **kwargs)
        if inspect.isawaitable(result):

            async def observe() -> Any:
                response = await result
                return self._after(response, kwargs, started, asynchronous=True)

            return observe()
        return self._after(result, kwargs, started, asynchronous=False)

    def _after(self, response: Any, request: Mapping[str, Any], started: float, *, asynchronous: bool) -> Any:
        try:
            if request.get("stream"):
                if self._endpoint == "chat" and not _get(request, "stream_options", "include_usage"):
                    with suppress(Exception):
                        warnings.warn(
                            "Chat streams need stream_options={'include_usage': True} to report usage.", stacklevel=3
                        )
                cls = _AsyncStream if asynchronous else _Stream
                return cls(response, request, self._endpoint, started, self._store)
            _record(response, response, request, self._endpoint, started, self._store, False)
        except Exception:
            pass
        return response


class _Chat:
    def __init__(self, chat: Any, store: TraceStore | None) -> None:
        self._chat = chat
        self.completions = _Resource(chat.completions, store, "chat")

    def __getattr__(self, name: str) -> Any:
        return getattr(self._chat, name)


class _Client:
    def __init__(self, client: Any, store: TraceStore | None) -> None:
        self._client = client
        self.responses = _Resource(client.responses, store, "responses")
        self.chat = _Chat(client.chat, store)

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
