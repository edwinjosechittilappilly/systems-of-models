# Integrations

## LangChain

Install `systems-of-models[langchain]`, then wrap an existing `som.Gate`:

```python
from som.integrations.langchain import GateRunnable

runnable = GateRunnable(gate, max_concurrency=10)
result = runnable.invoke("I was charged twice")
results = runnable.batch(["I was charged twice", "My card is missing"])
# In an async function: result = await runnable.ainvoke("I was charged twice")
```

The result is a `GateResult`, including the served answer, decisions and cost. `som.AsyncGate(gate, max_concurrency=10)` also exposes asynchronous calls and an ordered `batch` without requiring LangChain. Synchronous provider calls run in worker threads; cancellation does not stop a provider request already in progress.

## MCP

Install the official MCP SDK using the optional extra and start the server:

```sh
pip install 'systems-of-models[mcp]'
```

```sh
som mcp-serve --s1 typesafe:jev-1.14.0
```

Set the provider credentials in the environment. The `decide` tool accepts `input` and a list of typed `questions` in the S1 contract representation, and returns typed `answers` plus an `envelope`. For example, the tool arguments can be:

```json
{
  "input": "I was charged twice",
  "questions": [{"type": "choice", "name": "team", "instructions": "Which team handles the ticket?", "choices": [{"value": "billing"}, {"value": "cards"}, {"value": "fraud"}]}]
}
```

A tool call makes a provider request and may incur a charge. `SOM_S1` sets the default S1 model; `--s1` overrides it.

## Native reasoning adapters

Install `systems-of-models[anthropic]` or `systems-of-models[gemini]` to use
`som.Anthropic(model)` or `som.Gemini(model)` as an S2 decider. Provider credentials
must be configured for the respective SDK, or an initialized client can be passed
as `client=`. Provider pricing is not built in: pass a verified `rate_card` to
estimate cost, otherwise the envelope reports an unknown cost.

See [wrap](wrap.md) for OpenAI client observability and its supported surfaces.
