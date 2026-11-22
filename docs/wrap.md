# Observing OpenAI calls

`som.wrap(client, store=...)` wraps an OpenAI or AsyncOpenAI client without changing the arguments or the SDK response objects. Calls to `responses.create` and `chat.completions.create`, including `stream=True`, produce an S2 envelope. Pass a `TraceStore` to retain records and use `som.envelope_of(response)` to look up a recent envelope. The bounded in-memory lookup may evict older envelopes; it does not retain provider responses or streams. A response ID permits lookup by ID; objects without an ID need to support weak references for identity lookup.

```python
from openai import OpenAI
from som import TraceStore, envelope_of, wrap

store = TraceStore()
client = wrap(OpenAI(), store=store)
response = client.responses.create(model="gpt-4.1-mini", input="Hello")
observation = envelope_of(response)
```

The proxy preserves `isinstance` checks for the wrapped client and stream, and `copy()` and `with_options()` return observed clients sharing the store. Other client resources are delegated. Only the two `create` methods above are observed: `parse`, `responses.stream()`, `with_raw_response`, `with_streaming_response`, and all other methods/resources are passed through without instrumentation. Proxy objects are not identical to the underlying SDK client or stream, and exact `type(obj)` checks do not see the SDK type.

Streaming records an envelope when exhausted, closed, or when its context manager exits. Closing or collecting a stream before completion records an incomplete envelope. Garbage collection timing is nondeterministic and does not replace closing the underlying network stream: use `with`/`async with` or explicitly close streams, especially after breaking out of iteration. Chat streams need `stream_options={"include_usage": True}` for provider usage and pricing; without it usage is unknown. An interrupted stream may not contain a final usage event. A `length` or `content_filter` chat finish reason is incomplete.

With the optional OpenTelemetry API and a configured SDK, each observed call has a child span covering the provider call and, for streams, the stream lifetime. Its attributes do not include prompt text or modify the caller's span. If no OpenTelemetry SDK is configured, envelopes still have generated trace identifiers. Instrumentation failures do not change SDK results or provider exceptions.
