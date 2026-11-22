# Command-line interface

`som demo` replays recorded Banking77 gate decisions offline. It prints the serving system, estimated gate and S2-only costs, latency, and per-item savings. The paired provider calls were made on public Banking77 test utterances; costs are list-price estimates, not invoices. The recordings are a small demonstration, not an evaluation of gate accuracy.

Estimate break-even and savings with per-request costs in USD:

```sh
som breakeven --c1 0.00004 --c2 0.004 \
  --escalated-c2 0.005 --overhead 0.00001 --escalation-rate 0.2
```

The list-price break-even is `1 - c1/c2`. The usage-weighted break-even is `(c2 - c1 - overhead)/escalated-c2`; it accounts for the mean S2 cost on escalated requests differing from the S2-only mean. If `--escalated-c2` is omitted it defaults to `--c2`, and overhead defaults to zero. Savings are printed when an escalation rate is supplied.

Ask a single choice question (this makes a paid provider request):

```sh
som ask 'I was charged twice' --choice team=billing,cards,fraud --s1 typesafe:jev-1.14.0
```

The command prints the decision envelope as JSON. Set the provider credentials in the environment; `SOM_S1` supplies the default `provider:model` when `--s1` is omitted. Supported S1 providers are `typesafe` and `openai` (or `openai-decisions`).

Use `som mcp-serve` to expose decisions via MCP; see [integrations](integrations.md). Existing schema commands are `som check-schemas` and `som validate FILE --schema NAME`.
