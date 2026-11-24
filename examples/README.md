# Examples

From the repository root, install the project and development dependencies with `uv sync`, then run:

```bash
uv run python examples/support_ticket.py
uv run python examples/compile_from_traces.py
```

Both examples run offline by default. The support-ticket example demonstrates a gate, its envelopes, trace store,
escalation and cost; the trace-compilation example mines synthetic agent traces and follows a compiled decision through
shadowing, promotion, serving, auditing and demotion.

To run the support-ticket example against real providers instead, set `TYPESAFE_API_KEY` and `OPENAI_API_KEY` in your
environment, then run `uv run python examples/support_ticket.py --live`. This makes paid API calls. Never commit keys.
