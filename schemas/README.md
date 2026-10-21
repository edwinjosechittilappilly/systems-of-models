# Systems of Models: contract schemas (draft v1)

JSON Schema (draft 2020-12) contracts for the taxonomy. Each system schema defines `$defs/request` and `$defs/response`. The response composes `envelope.schema.json` through `allOf` and fixes `system`, the major version (`system_version` matches `^1\.`), and `body`. A top-level document holds a `request`, a `response`, or both. `examples/` has one valid instance per schema, plus a second one for the meta-layer. Example values are illustrative.

| File | Contents |
|---|---|
| `envelope.schema.json` | Common envelope and shared `$defs` (`system_id`, `semver`, `trace_ref`, `cost`, `usage`, `input`) |
| `escalation.schema.json` | Escalation protocol (`escalate_to`, `reason`, `threshold`, `context_handoff`) |
| `s1-decision.schema.json` | System 1: predicate / choice / score questions, answers, refusal |
| `s2-reasoning.schema.json` | System 2: effort/budget, reasoning items with summaries, reasoning tokens |
| `s3-search.schema.json` | Search system: candidates, verifier, selection, search stats |
| `s4-agentic.schema.json` | Agentic system: tools (function / MCP / builtin / system), steps, observations, side effects |
| `s5-self-evolving.schema.json` | Self-evolving system: scoped modifications, before/after, evaluation, rollback |
| `meta-layer.schema.json` | `system_proposal` and `version_bump` records with semver rules |
| `swarm-trace.schema.json` | Width axis: OpenTelemetry-style spans plus swarm-memory references |

Conventions:
- `$id`s resolve to the files in this repository: `https://raw.githubusercontent.com/edwinjosechittilappilly/systems-of-models/main/schemas/<name>.schema.json`.
- Consumers MUST ignore unknown fields, because a minor version may add optional fields.
- Adopted system IDs are `s1.decision` through `s5.self_evolving`. A system proposed by the meta-layer uses an `x.` ID until a `version_bump` with change kind `system_adopted` (minor) admits it.
- The schemas enforce the semver rules: patch allows only improvement kinds, minor needs at least one additive change and no breaking change, and major needs a breaking change plus a `migration`. S5 can cause at most a `patch` bump. JSON Schema cannot check the arithmetic between `from_version` and `to_version`.

## Design rationale

| Field | Purpose | Precedent |
|---|---|---|
| `id`, `object`, `created_at`, `metadata` | Identify and tag a response | OpenAI Responses/Decisions response objects |
| `system`, `system_version` | State which contract and which semver release answered | [SemVer 2.0.0](https://semver.org); API versioning practice |
| `confidence`, `confidence_basis` | Give one gate signal across tiers (estimated probability that the response is correct), and record where it comes from so uncalibrated signals can be discounted. `confidence_basis` is required whenever `confidence` is a number | Decisions `confidence`; [TypeSafe confidence](https://docs.typesafe.ai/confidence.md); calibration disputes in the lit review |
| `cost.amount`, `cost.usage`, `cost.breakdown` | Price composed calls; `usage` keeps vendor token names | OpenAI `usage` (`input_tokens`, `output_tokens_details.reasoning_tokens`) |
| `latency_ms` | Latency is part of the S1 definition, and it is what tiers trade against | Decisions "about 10x faster than the Responses API" claim |
| `trace_ref.trace_id/span_id` | Join a response to the shared trace | [W3C Trace Context](https://www.w3.org/TR/trace-context/); OpenTelemetry |
| `implementation.provider/model/endpoint` | Record which vendor API served the contract | OTel `gen_ai.provider.name`, `gen_ai.response.model` |
| `status: escalated` + `escalation` | Make a handoff explicit and auditable | TypeSafe docs ("escalate to a person or a reasoning model"); cascade/router literature |
| `escalation.threshold` (`metric`, `operator`, `value`, `observed`, `source`) | Make the gating rule reproducible | [Decisions guide](https://developers.openai.com/api/docs/guides/decisions): set thresholds from labelled data and error costs |
| `escalation.context_handoff` (`full` / `summary` / `reference`) | Bound what the receiver sees and spends | Responses `previous_response_id`; agent handoff patterns |
| S1 `questions[].type` ∈ `predicate`, `choice`, `score` | Bounded, typed answer space | [Decisions API reference](https://developers.openai.com/api/reference/python/resources/decisions.md); Jev `noul`/`choice`/`score` ([primitives](https://docs.typesafe.ai/primitives.md)) |
| S1 `choices` (2–255, typed `str`/`bool`), `levels` (ordered, index from 0) | Fix the answer space | Decisions API limits; Jev cardinality 255 |
| S1 `answers[]`: `probability`; `choice` + `probabilities` + `confidence`; `score` + `probabilities` + `confidence` | Probabilistic, typed answers | Decisions API answer objects |
| S1 `answers[].type: refusal` (+ optional `reason`) | Abstain on a single question while the others still answer | Decisions refusal; `reason` is our extension |
| S1 `name` required | Stable keys for escalation and traces | Optional in Decisions; required as a dict key in Jev |
| S1 `input` as string, messages, or object | Cover both vendor input shapes | Decisions `input`; Jev `state` |
| S2 `reasoning.effort`, `reasoning.mode`, `reasoning.summary`, `max_output_tokens` | Control linear test-time compute | [OpenAI reasoning guide](https://developers.openai.com/api/docs/guides/reasoning.md) |
| S2 `reasoning.budget_tokens` | Set a hard cap on thinking tokens | Anthropic `thinking.budget_tokens`; Gemini `thinkingBudget` |
| S2 `output[]` reasoning items (`summary_text`, `encrypted_content`) | Expose a summary but not raw reasoning | Responses API reasoning output items |
| S2 `incomplete_details.reason` | Report budget exhaustion | Responses API `incomplete_details` |
| S3 `strategy`, `generator`, `verifier.kind`, `granularity` | Separate generating candidates from checking them | Best-of-N with reward models, process reward models, self-consistency, Tree of Thoughts, MCTS (see lit review) |
| S3 `candidates[]` (`parent_id`, `depth`, `visits`, `status`) | Represent best-of-N, beams and trees in one shape | ToT / MCTS search trees |
| S3 `selection` (`rule`, `selected_ids`, `margin`) | Make the choice auditable; a small margin can trigger escalation | Majority vote / argmax over verifier scores |
| S4 `tools[]` (`function`, `mcp`, `builtin`, `system`) | Declare actions; other systems can act as tools | Responses API `function` and `mcp` tools (`server_label`, `allowed_tools`, `require_approval`) |
| S4 `tool_ref` (`server_label`, `name`) | Point to a tool unambiguously across servers | [MCP `tools/call`](https://modelcontextprotocol.io/specification/2025-06-18/server/tools) |
| S4 `observation` (`content`, `structured_content`, `is_error`) | Record environment feedback | MCP `CallToolResult` (`content`, `structuredContent`, `isError`) |
| S4 `approval`, `side_effects[].reversible`, `environment.snapshot_ref` | Support human-in-the-loop control, audit and replay | Responses MCP `require_approval`; agent-safety practice |
| S5 `modifications[].scope` (incl. `compiled_decision`) | Keep self-modification within an allowed scope; compiling repeated reasoning into S1 is a first-class scope | Self-improvement work (STaR, DGM, AlphaEvolve) in the lit review; the paper's key prediction |
| S5 `before` / `after` (`content_hash`) | Make every change diffable and pinned | Content-addressed artefacts |
| S5 `evaluation` (`baseline`, `candidate`, `n`, `confidence_interval`, `passed`) | Require evidence before `applied` | Held-out regression gating |
| S5 `rollback` (`strategy`, `snapshot_ref`, `trigger`) | Allow automatic reversal on live regressions | Feature flags and canary rollback |
| Meta `system_proposal` (`x.` ID, `position`, `contract`, `initial_version` 0.y.z) | Let a machine author an RFC for a new tier | PEP/RFC processes; SemVer 0.y.z = unstable |
| Meta `version_bump.changes[].kind`, `breaking`, `migration` | Encode the semver rules in the schema | SemVer 2.0.0 |
| Meta `provenance.distilled_from` | Record downward distillation as the source of a patch | Distillation thesis (lit review) |
| Swarm `spans[]` (`trace_id`, `span_id`, `parent_span_id`, `*_unix_nano`, `status.code`, `events`, `links`) | Give every member one trace model; links carry cross-member causality | OpenTelemetry span model and OTLP/JSON |
| Swarm `attributes` `gen_ai.*` | Stay compatible with existing GenAI observability tools | [OTel GenAI semantic conventions](https://github.com/open-telemetry/semantic-conventions-genai) (`gen_ai.operation.name`, `gen_ai.agent.id`, `gen_ai.usage.reasoning.output_tokens`, …) |
| Swarm `attributes` `som.*` | Carry taxonomy-specific data (system, confidence, cost, escalation, memory I/O) | OTel guidance to namespace custom attributes |
| Swarm `memory.entries[]` (`kind`, `content_hash`, `written_by`, `read_by`, `visibility`, `version`) | Shared memory that spans reference rather than inline; provenance for later training | Episodic/semantic/procedural memory taxonomies in agent work |
