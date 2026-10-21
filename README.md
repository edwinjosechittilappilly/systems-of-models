# Systems of Models: API contracts

JSON Schemas (draft 2020-12) that accompany the paper

> **Beyond System 2: A Taxonomy and API Contracts for Systems of Models**
> Edwin Jose, Western Michigan University (2026). arXiv link to be added on publication.

The paper classifies LLM systems by compute topology into five systems: System 1 (Decision), System 2 (Reasoning), Search (S3), Agentic (S4) and Self-evolving (S5). It adds a width axis (single → swarm) and a meta-layer that versions systems. This repository gives each system a request/response contract, plus the shared pieces:

| File | Contents |
|---|---|
| `schemas/envelope.schema.json` | Common response envelope: `id`, `system`, `system_version`, `confidence` + `confidence_basis`, `cost`, `latency_ms`, `trace_ref`, `escalation`, `body` |
| `schemas/escalation.schema.json` | Escalation protocol (`escalate_to`, `reason`, `threshold`, `context_handoff`, `mode`) |
| `schemas/s1-decision.schema.json` … `s5-self-evolving.schema.json` | One contract per system |
| `schemas/meta-layer.schema.json` | System proposals and semantic-version bumps |
| `schemas/swarm-trace.schema.json` | OpenTelemetry-compatible swarm traces and swarm memory |
| `schemas/examples/` | One valid example per schema; together they trace one support ticket from S1 to S5 |

See `schemas/README.md` for the design rationale and the vendor precedent behind each field.

## Validate

```bash
uv run --with jsonschema python scripts/validate_schemas.py
```

Each schema's `$id` resolves to its raw file in this repository, so `$ref`s work over the network as well as locally.

## Citation

See `CITATION.cff`. The arXiv identifier will be added once the paper is published.

## License

MIT, see `LICENSE`.
