# E3a post-evaluation analysis

Generated from retained evaluation artifacts; no model calls. NA means unavailable, not zero.

## Run provenance, deviations and spend
- Run ID: evaluation. Frozen code is tag `prereg-e3a` at original `be24e7c` (rebased patch-equivalent `3a65403`). `PREREG.md`'s older `b5d3617` reference is imprecise: H3 and lifecycle code changed before the tag.
- Four invocations were needed; the first (seed 11 control and restructure) has no retained manifest or recorded run SHA. The next three recorded dirty worktrees at original SHAs `06694c4`, `278d5b3`, and `a7cfa60`. Exact uncommitted differences are not recoverable from those manifests.
- Original commits are preserved by tags `e3a-run-1` through `e3a-run-4`: `be24e7c`, `06694c4`, `278d5b3`, and `a7cfa60`, respectively. Their patch-equivalent rebased SHAs are `3a65403`, `9e6d3fc`, `ecc2fb4`, and `6d8f562`. The first tag preserves the frozen baseline, not a verified SHA for the manifest-less first invocation.
- Models: `{"embedder": "embeddinggemma", "s1": "jev-1.14.0", "teacher": "gpt-6.1-terra", "writer": "gpt-6.1-terra"}`.
- Frozen configuration deviations: none detected in checked fields.
- Manifest new provider spend (USD): `{"openai": 1.608545700000029, "typesafe": 1.5085857779968936}`. The following cost ratios compare matched stream sets; the secondary arms cover only six streams and their totals must not be divided by the nine-stream always-agent total.
- Cumulative journaled list-price spend at completion: OpenAI $51.813693 of $75 and TypeSafe $6.120658 of the $8 proxy cap. This conservatively includes the $1 reservations for each OpenAI 503 and 429 and the $0.05 TypeSafe 402 reservation; provider billing may differ. No reservations remain unsettled.
- The frozen TypeSafe cap was $5; the cap was raised during evaluation. [INFERENCE] Applying the observed 1.78 billing/list ratio to $6.120658 list spend gives approximately $10.90 billed, exceeding the frozen $5 cap; final provider billing remains unreconciled.
- Manifest notes: `["Deviation: CLINC secondary audit-rate replays skipped by user instruction."]`.
- Recorded budget stop (bench/results/e3a/evaluation/budget_stop.json): `{"caps_usd": {"openai": 75.0, "typesafe": 5.0}, "error": "typesafe: budget reserved for unpriced call: Client error '402 Payment Required' for url 'https://api.typesafe.ai/v1/systemone'\nFor more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/402", "spent_usd": {"openai": 26.55214266999984, "typesafe": 2.8020353839984793}}`.
- Recorded budget stop (bench/results/e3a/evaluation-resumed/budget_stop.json): `{"caps_usd": {"openai": 75.0, "typesafe": 8.0}, "error": "BudgetExceeded: openai: budget reserved for unpriced call: Error code: 503 - Unable to verify model access right now. Please retry.", "spent_usd": {"openai": 35.112541169999865, "typesafe": 3.422965651997018}}`.
- Recorded budget stop (bench/results/e3a/evaluation-resumed-2/budget_stop.json): `{"caps_usd": {"openai": 75.0, "typesafe": 8.0}, "error": "BudgetExceeded: openai: budget reserved for unpriced call: Error code: 429 - You have no credits remaining. Add credits to continue using the API at https://platform.openai.com/settings/organization/billing/.", "spent_usd": {"openai": 50.205147719999346, "typesafe": 4.612072507994607}}`.
- At the TypeSafe 402 stop, the dashboard showed $4.89 billed versus approximately $2.75 settled list-price spend (about 1.78 times). After two authorized top-ups, $9.89 of balance remained on top of $4.89 already billed ($14.78 total available). The cumulative list-price proxy cap was raised to $8.00 (about $14.24 billed at the observed ratio). The previous $0.05 unpriced-call reservation is conservatively retained. This proxy cannot guarantee the actual billed cap; dashboard billing must be monitored separately.
- OpenAI 503 stop deviation: model access verification failed and interrupted evaluation. The $1.00 unpriced-call reservation is retained; it is not evidence of actual provider billing. Actual billing for the failed call is unknown.
- OpenAI 429 deviation: credits were exhausted; after a user-authorized top-up the run resumed from cache. The $1.00 unpriced-call reservation was retained; actual billing is unknown.
- Secondary replay status: `{"caches": {"mining_timings": {"hits": 0, "misses": 0}, "s1": {"hits": 30500, "misses": 7300}, "teacher": {"hits": 0, "misses": 0}, "writer": {"hits": 24, "misses": 9}}, "error": null}`.
- Logical costs can count cached calls across arms and are not provider spend. Provider dashboard reconciliation is unverified for current spend; hardware and energy are unpriced.
- Pacing deviation: the runner reserves at most 400,000 estimated tokens per rolling minute, but does not record individual pacing sleeps; actual waits and any backoff cannot be audited from the retained artifacts.

### Cost per ticket relative to always-agent

| Arm | Overall | Control | Restructure | CLINC |
|---|---:|---:|---:|---:|
| S1 audit, rate 1.0 | 1.023 | 1.022 | 1.026 | 1.022 |
| Oracle audit | 1.022 | — | — | — |
| S1 refit | 0.981 | — | — | — |
| Escalation only | 0.778 | 0.811 | 0.744 | 0.780 |
| Fixed gate | 0.784 | — | — | — |
| Fixed gate with config hash | 0.969 | — | — | — |
| kNN / local surrogates | 1.000 | — | — | — |
| Secondary audit 0.1 / 0.3 / 0.6 | — | 0.833 / 0.874 / 0.937 | 0.937 / 0.976 / 1.004 | not run |

The primary audit arm costs 2.3% more, not less, than always-agent. Local compute is unpriced. Always-agent cost was $62.12 over 21,600 tickets ($0.002876 per ticket); unused teacher-variance draws cost $1.67.

## Offline replay verification

The cache-only replay completed without provider calls. Its strict artifact comparator
matched 121 of 138 deterministic files after excluding timing fields; it did **not**
produce byte-identical artifacts overall. H3, H4, H5, the combined summary, the audit
curve, discovery tables, and all per-ticket arm CSVs matched after timing exclusions.
The 17 mismatches comprised nine S4 trace files, S5 transition records, and seven
per-stream summaries. In the summaries, common-arm values were identical; five
original summaries contained only primary rows while replay summaries also contained
secondary rows, and two differed only in numeric serialization. The combined summary
matched exactly. All nine trace files and all 63 S5 records matched after additionally
excluding generated identifiers and timestamps; this is not a byte-identity claim.

Timing/metadata exclusions were `created_at`, `latency_ms`, `local_cpu_seconds`,
`raw_mining_latency_ms`, `training_filter_latency_ms`, and gzip-header metadata.
For the additional trace/transition semantic comparison, generated `id`, `trace_id`,
`span_id`, `parent_span_id`, and `trace_ref` fields were also excluded. The original
recorded artifacts and observed timing values were not modified.
The comparator JSON is preserved in ordered, privacy-redacted shards with checksums
and reconstruction instructions in `bench/results/e3a/replay-comparison/README.md`.

## H1 — discovery
Candidate-level precision and recall are per mining report; repeated reports are not independent experiments.
| stream | arm | ticket_index | generation | stage | discovery_precision | discovery_recall | discovery_true_positives | discovery_accepted | discovery_rejected | ambiguous_retrieval_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| seed_11_control | s1_audit | 300 | 0 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | s1_refit | 300 | 0 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | surrogate_audit | 300 | 0 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | surrogate_refit | 300 | 0 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | escalation_only | 300 | 0 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | oracle_audit | 300 | 0 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | s1_audit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | s1_refit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | surrogate_audit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | surrogate_refit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | escalation_only | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | oracle_audit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | s1_audit | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | s1_refit | 500 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | surrogate_audit | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | surrogate_refit | 500 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | escalation_only | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | oracle_audit | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | s1_audit | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | s1_refit | 700 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | surrogate_audit | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | surrogate_refit | 700 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | escalation_only | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | oracle_audit | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | s1_audit | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | s1_refit | 900 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | surrogate_audit | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | surrogate_refit | 900 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | escalation_only | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | oracle_audit | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | s1_audit | 1100 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | s1_refit | 1100 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | surrogate_audit | 1100 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | surrogate_refit | 1100 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | escalation_only | 1100 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | oracle_audit | 1100 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | s1_audit | 1300 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | s1_refit | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | surrogate_audit | 1300 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | surrogate_refit | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | escalation_only | 1300 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | oracle_audit | 1300 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | s1_audit | 1300 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | s1_refit | 1300 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | surrogate_audit | 1300 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | surrogate_refit | 1300 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | escalation_only | 1300 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | oracle_audit | 1300 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | s1_audit | 1500 | 2 | raw | 0.333333 | 1 | 2 | 6 | 11 | 0 |
| seed_11_control | s1_refit | 1500 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | surrogate_audit | 1500 | 2 | raw | 0.333333 | 1 | 2 | 6 | 11 | 0 |
| seed_11_control | surrogate_refit | 1500 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | escalation_only | 1500 | 2 | raw | 0.333333 | 1 | 2 | 6 | 11 | 0 |
| seed_11_control | oracle_audit | 1500 | 2 | raw | 0.333333 | 1 | 2 | 6 | 11 | 0 |
| seed_11_control | s1_audit | 1700 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | s1_refit | 1700 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | surrogate_audit | 1700 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | surrogate_refit | 1700 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | escalation_only | 1700 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | oracle_audit | 1700 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | s1_audit | 1900 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | s1_refit | 1900 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | surrogate_audit | 1900 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | surrogate_refit | 1900 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | escalation_only | 1900 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | oracle_audit | 1900 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | s1_audit | 2100 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | s1_refit | 2100 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | surrogate_audit | 2100 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | surrogate_refit | 2100 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | escalation_only | 2100 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | oracle_audit | 2100 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | s1_audit | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | s1_refit | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | surrogate_audit | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | surrogate_refit | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | escalation_only | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | oracle_audit | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | s1_audit | 2300 | 2 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | s1_refit | 2300 | 2 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | surrogate_audit | 2300 | 2 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | surrogate_refit | 2300 | 2 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | escalation_only | 2300 | 2 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | oracle_audit | 2300 | 2 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | s1_audit | 300 | 0 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | s1_refit | 300 | 0 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | surrogate_audit | 300 | 0 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | surrogate_refit | 300 | 0 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | escalation_only | 300 | 0 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | oracle_audit | 300 | 0 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | s1_audit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | s1_refit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | surrogate_audit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | surrogate_refit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | escalation_only | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | oracle_audit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | s1_audit | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | s1_refit | 500 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | surrogate_audit | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | surrogate_refit | 500 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | escalation_only | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | oracle_audit | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | s1_audit | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | s1_refit | 700 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | surrogate_audit | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | surrogate_refit | 700 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | escalation_only | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | oracle_audit | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | s1_audit | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | s1_refit | 900 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | surrogate_audit | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | surrogate_refit | 900 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | escalation_only | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | oracle_audit | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | s1_audit | 1100 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | s1_refit | 1100 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | surrogate_audit | 1100 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | surrogate_refit | 1100 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | escalation_only | 1100 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | oracle_audit | 1100 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | s1_audit | 1300 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | s1_refit | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | surrogate_audit | 1300 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | surrogate_refit | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | escalation_only | 1300 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | oracle_audit | 1300 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | s1_refit | 1300 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | surrogate_audit | 1300 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | surrogate_refit | 1300 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | s1_audit | 1500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | s1_refit | 1500 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | surrogate_audit | 1500 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | surrogate_refit | 1500 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | escalation_only | 1500 | 1 | raw | 0.333333 | 1 | 2 | 6 | 11 | 0 |
| seed_11_restructure_15 | oracle_audit | 1500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | s1_audit | 1500 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | s1_audit | 1700 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | s1_refit | 1700 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | surrogate_audit | 1700 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | surrogate_refit | 1700 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | escalation_only | 1700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | oracle_audit | 1700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | s1_audit | 1900 | 2 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | s1_refit | 1900 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | surrogate_audit | 1900 | 2 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | surrogate_refit | 1900 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | escalation_only | 1900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | oracle_audit | 1900 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | s1_audit | 2100 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | s1_refit | 2100 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | surrogate_audit | 2100 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | surrogate_refit | 2100 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | escalation_only | 2100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | oracle_audit | 2100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | s1_audit | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | s1_refit | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | surrogate_audit | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | surrogate_refit | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | escalation_only | 2300 | 1 | raw | 0.333333 | 1 | 2 | 6 | 11 | 0 |
| seed_11_restructure_15 | oracle_audit | 2300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | s1_refit | 2300 | 2 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | surrogate_audit | 2300 | 2 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | surrogate_refit | 2300 | 2 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | s1_audit | 300 | 0 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | s1_refit | 300 | 0 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | surrogate_audit | 300 | 0 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | surrogate_refit | 300 | 0 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | escalation_only | 300 | 0 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | oracle_audit | 300 | 0 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | s1_audit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | s1_refit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | surrogate_audit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | surrogate_refit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | escalation_only | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | oracle_audit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | s1_audit | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_clinc | s1_refit | 500 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | surrogate_audit | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_clinc | surrogate_refit | 500 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | escalation_only | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_clinc | oracle_audit | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_clinc | s1_audit | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_clinc | s1_refit | 700 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | surrogate_audit | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_clinc | surrogate_refit | 700 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | escalation_only | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_clinc | oracle_audit | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_clinc | s1_audit | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_clinc | s1_refit | 900 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | surrogate_audit | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_clinc | surrogate_refit | 900 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | escalation_only | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_clinc | oracle_audit | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_clinc | s1_audit | 1100 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | s1_refit | 1100 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | surrogate_audit | 1100 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | surrogate_refit | 1100 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | escalation_only | 1100 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | oracle_audit | 1100 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | s1_audit | 1300 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | s1_refit | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_clinc | surrogate_audit | 1300 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | surrogate_refit | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_clinc | escalation_only | 1300 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | oracle_audit | 1300 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | s1_refit | 1300 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | surrogate_audit | 1300 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | surrogate_refit | 1300 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | s1_audit | 1500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_clinc | s1_refit | 1500 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_clinc | surrogate_audit | 1500 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_clinc | surrogate_refit | 1500 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_clinc | escalation_only | 1500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_clinc | oracle_audit | 1500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_clinc | s1_audit | 1700 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | s1_refit | 1700 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_clinc | surrogate_audit | 1700 | 2 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | surrogate_refit | 1700 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_clinc | escalation_only | 1700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_clinc | oracle_audit | 1700 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | s1_audit | 1900 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | s1_refit | 1900 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_clinc | surrogate_audit | 1900 | 2 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | surrogate_refit | 1900 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_clinc | escalation_only | 1900 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | oracle_audit | 1900 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | s1_audit | 2100 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | s1_refit | 2100 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_clinc | surrogate_audit | 2100 | 2 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | surrogate_refit | 2100 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_clinc | escalation_only | 2100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_clinc | oracle_audit | 2100 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | s1_audit | 2300 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | s1_refit | 2300 | 2 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | surrogate_audit | 2300 | 2 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | surrogate_refit | 2300 | 2 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | escalation_only | 2300 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | oracle_audit | 2300 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | s1_refit | 2300 | 2 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | surrogate_audit | 2300 | 2 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_clinc | surrogate_refit | 2300 | 2 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_control | s1_audit | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | s1_refit | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | surrogate_audit | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | surrogate_refit | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | escalation_only | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | oracle_audit | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | s1_audit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_control | s1_refit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_control | surrogate_audit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_control | surrogate_refit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_control | escalation_only | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_control | oracle_audit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_control | s1_audit | 500 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_control | s1_refit | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | surrogate_audit | 500 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_control | surrogate_refit | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | escalation_only | 500 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_control | oracle_audit | 500 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_control | s1_audit | 700 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_control | s1_refit | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | surrogate_audit | 700 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_control | surrogate_refit | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | escalation_only | 700 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_control | oracle_audit | 700 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_control | s1_audit | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | s1_refit | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | surrogate_audit | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | surrogate_refit | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | escalation_only | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | oracle_audit | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | s1_audit | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | s1_refit | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | surrogate_audit | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | surrogate_refit | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | escalation_only | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | oracle_audit | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | s1_audit | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | s1_refit | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | surrogate_audit | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | surrogate_refit | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | escalation_only | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | oracle_audit | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | s1_refit | 1300 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_control | surrogate_audit | 1300 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_control | surrogate_refit | 1300 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_control | s1_audit | 1500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | s1_refit | 1500 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | surrogate_audit | 1500 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | surrogate_refit | 1500 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | escalation_only | 1500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | oracle_audit | 1500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | s1_audit | 1700 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_control | s1_refit | 1700 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | surrogate_audit | 1700 | 2 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_control | surrogate_refit | 1700 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | escalation_only | 1700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | oracle_audit | 1700 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_control | s1_audit | 1900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | s1_refit | 1900 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | surrogate_audit | 1900 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | surrogate_refit | 1900 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | escalation_only | 1900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | oracle_audit | 1900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | s1_audit | 2100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | s1_refit | 2100 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | surrogate_audit | 2100 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | surrogate_refit | 2100 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | escalation_only | 2100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | oracle_audit | 2100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | s1_audit | 2300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | s1_refit | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | surrogate_audit | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | surrogate_refit | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | escalation_only | 2300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | oracle_audit | 2300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | s1_refit | 2300 | 2 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_control | surrogate_audit | 2300 | 2 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_control | surrogate_refit | 2300 | 2 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_restructure_15 | s1_audit | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | s1_refit | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | surrogate_audit | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | surrogate_refit | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | escalation_only | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | oracle_audit | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | s1_audit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_restructure_15 | s1_refit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_restructure_15 | surrogate_audit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_restructure_15 | surrogate_refit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_restructure_15 | escalation_only | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_restructure_15 | oracle_audit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_restructure_15 | s1_audit | 500 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_restructure_15 | s1_refit | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | surrogate_audit | 500 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_restructure_15 | surrogate_refit | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | escalation_only | 500 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_restructure_15 | oracle_audit | 500 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_restructure_15 | s1_audit | 700 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_restructure_15 | s1_refit | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | surrogate_audit | 700 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_restructure_15 | surrogate_refit | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | escalation_only | 700 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_restructure_15 | oracle_audit | 700 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_restructure_15 | s1_audit | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | s1_refit | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | surrogate_audit | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | surrogate_refit | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | escalation_only | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | oracle_audit | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | s1_audit | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | s1_refit | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | surrogate_audit | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | surrogate_refit | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | escalation_only | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | oracle_audit | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | s1_audit | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | s1_refit | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | surrogate_audit | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | surrogate_refit | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | escalation_only | 1300 | 1 | raw | 0.333333 | 1 | 2 | 6 | 11 | 0 |
| seed_23_restructure_15 | oracle_audit | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | s1_refit | 1300 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_restructure_15 | surrogate_audit | 1300 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_restructure_15 | surrogate_refit | 1300 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_restructure_15 | s1_audit | 1500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | s1_refit | 1500 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | surrogate_audit | 1500 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | surrogate_refit | 1500 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | escalation_only | 1500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | oracle_audit | 1500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | s1_audit | 1500 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_restructure_15 | s1_audit | 1700 | 2 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_restructure_15 | s1_refit | 1700 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | surrogate_audit | 1700 | 2 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_restructure_15 | surrogate_refit | 1700 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | escalation_only | 1700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | oracle_audit | 1700 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_restructure_15 | s1_audit | 1900 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | s1_refit | 1900 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | surrogate_audit | 1900 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | surrogate_refit | 1900 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | escalation_only | 1900 | 1 | raw | 0.333333 | 1 | 2 | 6 | 11 | 0 |
| seed_23_restructure_15 | oracle_audit | 1900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | oracle_audit | 1900 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_restructure_15 | s1_audit | 2100 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | s1_refit | 2100 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | surrogate_audit | 2100 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | surrogate_refit | 2100 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | escalation_only | 2100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | oracle_audit | 2100 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | s1_audit | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | s1_refit | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | surrogate_audit | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | surrogate_refit | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | escalation_only | 2300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | oracle_audit | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | s1_refit | 2300 | 2 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_restructure_15 | surrogate_audit | 2300 | 2 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_restructure_15 | surrogate_refit | 2300 | 2 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_clinc | s1_audit | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | s1_refit | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | surrogate_audit | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | surrogate_refit | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | escalation_only | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | oracle_audit | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | s1_audit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_clinc | s1_refit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_clinc | surrogate_audit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_clinc | surrogate_refit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_clinc | escalation_only | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_clinc | oracle_audit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_clinc | s1_audit | 500 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_clinc | s1_refit | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | surrogate_audit | 500 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_clinc | surrogate_refit | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | escalation_only | 500 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_clinc | oracle_audit | 500 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_clinc | s1_audit | 700 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_clinc | s1_refit | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | surrogate_audit | 700 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_clinc | surrogate_refit | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | escalation_only | 700 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_clinc | oracle_audit | 700 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_clinc | s1_audit | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | s1_refit | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | surrogate_audit | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | surrogate_refit | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | escalation_only | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | oracle_audit | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | s1_audit | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | s1_refit | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | surrogate_audit | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | surrogate_refit | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | escalation_only | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | oracle_audit | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | s1_audit | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | s1_refit | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | surrogate_audit | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | surrogate_refit | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | escalation_only | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | oracle_audit | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | s1_refit | 1300 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_clinc | surrogate_audit | 1300 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_clinc | surrogate_refit | 1300 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_clinc | s1_audit | 1500 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_clinc | s1_refit | 1500 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | surrogate_audit | 1500 | 2 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_clinc | surrogate_refit | 1500 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | escalation_only | 1500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | oracle_audit | 1500 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_clinc | s1_audit | 1700 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_clinc | s1_refit | 1700 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | surrogate_audit | 1700 | 2 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_clinc | surrogate_refit | 1700 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | escalation_only | 1700 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_clinc | oracle_audit | 1700 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_clinc | s1_audit | 1900 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_clinc | s1_refit | 1900 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | surrogate_audit | 1900 | 2 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_clinc | surrogate_refit | 1900 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | escalation_only | 1900 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_clinc | oracle_audit | 1900 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_clinc | s1_audit | 2100 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_clinc | s1_refit | 2100 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | surrogate_audit | 2100 | 2 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_clinc | surrogate_refit | 2100 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | escalation_only | 2100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | oracle_audit | 2100 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_clinc | s1_audit | 2300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | s1_refit | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | surrogate_audit | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | surrogate_refit | 2300 | 2 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_clinc | escalation_only | 2300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | oracle_audit | 2300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_clinc | s1_refit | 2300 | 2 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_clinc | surrogate_audit | 2300 | 2 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_clinc | surrogate_refit | 2300 | 2 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_control | s1_audit | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_refit | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | surrogate_audit | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | surrogate_refit | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | escalation_only | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | oracle_audit | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_audit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_control | s1_refit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_control | surrogate_audit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_control | surrogate_refit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_control | escalation_only | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_control | oracle_audit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_control | s1_audit | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_refit | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | surrogate_audit | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | surrogate_refit | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | escalation_only | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | oracle_audit | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_audit | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_refit | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | surrogate_audit | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | surrogate_refit | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | escalation_only | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | oracle_audit | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_audit | 900 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_control | s1_refit | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | surrogate_audit | 900 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_control | surrogate_refit | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | escalation_only | 900 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_control | oracle_audit | 900 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_control | s1_audit | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_refit | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | surrogate_audit | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | surrogate_refit | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | escalation_only | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | oracle_audit | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_audit | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_refit | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | surrogate_audit | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | surrogate_refit | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | escalation_only | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | oracle_audit | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_refit | 1300 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_control | surrogate_audit | 1300 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_control | surrogate_refit | 1300 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_control | s1_audit | 1500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_refit | 1500 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | surrogate_audit | 1500 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | surrogate_refit | 1500 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | escalation_only | 1500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | oracle_audit | 1500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_audit | 1700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_refit | 1700 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | surrogate_audit | 1700 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | surrogate_refit | 1700 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | escalation_only | 1700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | oracle_audit | 1700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_audit | 1900 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_control | s1_refit | 1900 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | surrogate_audit | 1900 | 2 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_control | surrogate_refit | 1900 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | escalation_only | 1900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | oracle_audit | 1900 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_control | s1_audit | 2100 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_control | s1_refit | 2100 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | surrogate_audit | 2100 | 2 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_control | surrogate_refit | 2100 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | escalation_only | 2100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | oracle_audit | 2100 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_control | s1_audit | 2300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_refit | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | surrogate_audit | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | surrogate_refit | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | escalation_only | 2300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | oracle_audit | 2300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_refit | 2300 | 2 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_control | surrogate_audit | 2300 | 2 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_control | surrogate_refit | 2300 | 2 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_restructure_15 | s1_audit | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | s1_refit | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | surrogate_audit | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | surrogate_refit | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | escalation_only | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | oracle_audit | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | s1_audit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_restructure_15 | s1_refit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_restructure_15 | surrogate_audit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_restructure_15 | surrogate_refit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_restructure_15 | escalation_only | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_restructure_15 | oracle_audit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_restructure_15 | s1_audit | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | s1_refit | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | surrogate_audit | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | surrogate_refit | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | escalation_only | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | oracle_audit | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | s1_audit | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | s1_refit | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | surrogate_audit | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | surrogate_refit | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | escalation_only | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | oracle_audit | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | s1_audit | 900 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_restructure_15 | s1_refit | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | surrogate_audit | 900 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_restructure_15 | surrogate_refit | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | escalation_only | 900 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_restructure_15 | oracle_audit | 900 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_restructure_15 | s1_audit | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | s1_refit | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | surrogate_audit | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | surrogate_refit | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | escalation_only | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | oracle_audit | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | s1_audit | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | s1_refit | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | surrogate_audit | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | surrogate_refit | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | escalation_only | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | oracle_audit | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | s1_refit | 1300 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_restructure_15 | surrogate_audit | 1300 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_restructure_15 | surrogate_refit | 1300 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_restructure_15 | s1_audit | 1500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | s1_refit | 1500 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | surrogate_audit | 1500 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | surrogate_refit | 1500 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | escalation_only | 1500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | oracle_audit | 1500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | s1_audit | 1500 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_restructure_15 | oracle_audit | 1500 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_restructure_15 | s1_audit | 1700 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | s1_refit | 1700 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | surrogate_audit | 1700 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | surrogate_refit | 1700 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | escalation_only | 1700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | oracle_audit | 1700 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | s1_audit | 1900 | 2 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_restructure_15 | s1_refit | 1900 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | surrogate_audit | 1900 | 2 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_restructure_15 | surrogate_refit | 1900 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | escalation_only | 1900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | oracle_audit | 1900 | 2 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_restructure_15 | s1_audit | 2100 | 2 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_restructure_15 | s1_refit | 2100 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | surrogate_audit | 2100 | 2 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_restructure_15 | surrogate_refit | 2100 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | escalation_only | 2100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | oracle_audit | 2100 | 2 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_restructure_15 | s1_audit | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | s1_refit | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | surrogate_audit | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | surrogate_refit | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | escalation_only | 2300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | oracle_audit | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | s1_refit | 2300 | 2 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_restructure_15 | surrogate_audit | 2300 | 2 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_restructure_15 | surrogate_refit | 2300 | 2 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_clinc | s1_audit | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | s1_refit | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | surrogate_audit | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | surrogate_refit | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | escalation_only | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | oracle_audit | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | s1_audit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_clinc | s1_refit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_clinc | surrogate_audit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_clinc | surrogate_refit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_clinc | escalation_only | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_clinc | oracle_audit | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_clinc | s1_audit | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | s1_refit | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | surrogate_audit | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | surrogate_refit | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | escalation_only | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | oracle_audit | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | s1_audit | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | s1_refit | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | surrogate_audit | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | surrogate_refit | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | escalation_only | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | oracle_audit | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | s1_audit | 900 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_clinc | s1_refit | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | surrogate_audit | 900 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_clinc | surrogate_refit | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | escalation_only | 900 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_clinc | oracle_audit | 900 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_clinc | s1_audit | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | s1_refit | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | surrogate_audit | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | surrogate_refit | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | escalation_only | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | oracle_audit | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | s1_audit | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | s1_refit | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | surrogate_audit | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | surrogate_refit | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | escalation_only | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | oracle_audit | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | s1_refit | 1300 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_clinc | surrogate_audit | 1300 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_clinc | surrogate_refit | 1300 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_clinc | s1_audit | 1500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | s1_refit | 1500 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | surrogate_audit | 1500 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | surrogate_refit | 1500 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | escalation_only | 1500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | oracle_audit | 1500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | s1_audit | 1700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | s1_refit | 1700 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | surrogate_audit | 1700 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | surrogate_refit | 1700 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | escalation_only | 1700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | oracle_audit | 1700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | s1_audit | 1900 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_clinc | s1_refit | 1900 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | surrogate_audit | 1900 | 2 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_clinc | surrogate_refit | 1900 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | escalation_only | 1900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | oracle_audit | 1900 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_clinc | s1_audit | 2100 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_clinc | s1_refit | 2100 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | surrogate_audit | 2100 | 2 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_clinc | surrogate_refit | 2100 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | escalation_only | 2100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | oracle_audit | 2100 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_clinc | s1_audit | 2300 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_clinc | s1_refit | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | surrogate_audit | 2300 | 2 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_clinc | surrogate_refit | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | escalation_only | 2300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_clinc | oracle_audit | 2300 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_clinc | s1_refit | 2300 | 2 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_clinc | surrogate_audit | 2300 | 2 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_clinc | surrogate_refit | 2300 | 2 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | s1_audit_0.1 | 300 | 0 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | s1_audit_0.3 | 300 | 0 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | s1_audit_0.6 | 300 | 0 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | s1_audit_0.1 | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | s1_audit_0.3 | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | s1_audit_0.6 | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | s1_audit_0.1 | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | s1_audit_0.3 | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | s1_audit_0.6 | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | s1_audit_0.1 | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | s1_audit_0.3 | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | s1_audit_0.6 | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | s1_audit_0.1 | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | s1_audit_0.3 | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | s1_audit_0.6 | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | s1_audit_0.1 | 1100 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | s1_audit_0.3 | 1100 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | s1_audit_0.6 | 1100 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | s1_audit_0.1 | 1300 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | s1_audit_0.3 | 1300 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | s1_audit_0.6 | 1300 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | s1_audit_0.1 | 1300 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | s1_audit_0.3 | 1300 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | s1_audit_0.6 | 1300 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | s1_audit_0.1 | 1500 | 2 | raw | 0.333333 | 1 | 2 | 6 | 11 | 0 |
| seed_11_control | s1_audit_0.3 | 1500 | 2 | raw | 0.333333 | 1 | 2 | 6 | 11 | 0 |
| seed_11_control | s1_audit_0.6 | 1500 | 2 | raw | 0.333333 | 1 | 2 | 6 | 11 | 0 |
| seed_11_control | s1_audit_0.1 | 1700 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | s1_audit_0.3 | 1700 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | s1_audit_0.6 | 1700 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | s1_audit_0.1 | 1900 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | s1_audit_0.3 | 1900 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | s1_audit_0.6 | 1900 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | s1_audit_0.1 | 2100 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | s1_audit_0.3 | 2100 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | s1_audit_0.6 | 2100 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | s1_audit_0.1 | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | s1_audit_0.3 | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | s1_audit_0.6 | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_control | s1_audit_0.1 | 2300 | 2 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | s1_audit_0.3 | 2300 | 2 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_control | s1_audit_0.6 | 2300 | 2 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | s1_audit_0.1 | 300 | 0 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | s1_audit_0.3 | 300 | 0 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | s1_audit_0.6 | 300 | 0 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | s1_audit_0.1 | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | s1_audit_0.3 | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | s1_audit_0.6 | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | s1_audit_0.1 | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | s1_audit_0.3 | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | s1_audit_0.6 | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | s1_audit_0.1 | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | s1_audit_0.3 | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | s1_audit_0.6 | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | s1_audit_0.1 | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | s1_audit_0.3 | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | s1_audit_0.6 | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | s1_audit_0.1 | 1100 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | s1_audit_0.3 | 1100 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | s1_audit_0.6 | 1100 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | s1_audit_0.1 | 1300 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | s1_audit_0.3 | 1300 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | s1_audit_0.6 | 1300 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | s1_audit_0.1 | 1500 | 1 | raw | 0.333333 | 1 | 2 | 6 | 11 | 0 |
| seed_11_restructure_15 | s1_audit_0.3 | 1500 | 1 | raw | 0.333333 | 1 | 2 | 6 | 11 | 0 |
| seed_11_restructure_15 | s1_audit_0.6 | 1500 | 1 | raw | 0.333333 | 1 | 2 | 6 | 11 | 0 |
| seed_11_restructure_15 | s1_audit_0.3 | 1500 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | s1_audit_0.6 | 1500 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | s1_audit_0.1 | 1700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | s1_audit_0.3 | 1700 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | s1_audit_0.6 | 1700 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | s1_audit_0.1 | 1900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | s1_audit_0.3 | 1900 | 2 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | s1_audit_0.6 | 1900 | 2 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_11_restructure_15 | s1_audit_0.1 | 2100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | s1_audit_0.3 | 2100 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | s1_audit_0.6 | 2100 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | s1_audit_0.1 | 2300 | 1 | raw | 0.333333 | 1 | 2 | 6 | 11 | 0 |
| seed_11_restructure_15 | s1_audit_0.3 | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | s1_audit_0.6 | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_11_restructure_15 | s1_audit_0.1 | 2300 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_control | s1_audit_0.1 | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | s1_audit_0.3 | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | s1_audit_0.6 | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | s1_audit_0.1 | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_control | s1_audit_0.3 | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_control | s1_audit_0.6 | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_control | s1_audit_0.1 | 500 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_control | s1_audit_0.3 | 500 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_control | s1_audit_0.6 | 500 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_control | s1_audit_0.1 | 700 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_control | s1_audit_0.3 | 700 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_control | s1_audit_0.6 | 700 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_control | s1_audit_0.1 | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | s1_audit_0.3 | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | s1_audit_0.6 | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | s1_audit_0.1 | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | s1_audit_0.3 | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | s1_audit_0.6 | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | s1_audit_0.1 | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | s1_audit_0.3 | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | s1_audit_0.6 | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | s1_audit_0.1 | 1500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | s1_audit_0.3 | 1500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | s1_audit_0.6 | 1500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | s1_audit_0.1 | 1700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | s1_audit_0.3 | 1700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | s1_audit_0.6 | 1700 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_control | s1_audit_0.1 | 1900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | s1_audit_0.3 | 1900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | s1_audit_0.6 | 1900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | s1_audit_0.1 | 2100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | s1_audit_0.3 | 2100 | 1 | raw | 0.333333 | 1 | 2 | 6 | 11 | 0 |
| seed_23_control | s1_audit_0.6 | 2100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | s1_audit_0.1 | 2300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | s1_audit_0.3 | 2300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_control | s1_audit_0.6 | 2300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | s1_audit_0.1 | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | s1_audit_0.3 | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | s1_audit_0.6 | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | s1_audit_0.1 | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_restructure_15 | s1_audit_0.3 | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_restructure_15 | s1_audit_0.6 | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_restructure_15 | s1_audit_0.1 | 500 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_restructure_15 | s1_audit_0.3 | 500 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_restructure_15 | s1_audit_0.6 | 500 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_restructure_15 | s1_audit_0.1 | 700 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_restructure_15 | s1_audit_0.3 | 700 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_restructure_15 | s1_audit_0.6 | 700 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_restructure_15 | s1_audit_0.1 | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | s1_audit_0.3 | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | s1_audit_0.6 | 900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | s1_audit_0.1 | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | s1_audit_0.3 | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | s1_audit_0.6 | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | s1_audit_0.1 | 1300 | 1 | raw | 0.333333 | 1 | 2 | 6 | 11 | 0 |
| seed_23_restructure_15 | s1_audit_0.3 | 1300 | 1 | raw | 0.333333 | 1 | 2 | 6 | 11 | 0 |
| seed_23_restructure_15 | s1_audit_0.6 | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | s1_audit_0.1 | 1500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | s1_audit_0.3 | 1500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | s1_audit_0.6 | 1500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | s1_audit_0.1 | 1500 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_restructure_15 | s1_audit_0.3 | 1500 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_restructure_15 | s1_audit_0.6 | 1500 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_restructure_15 | s1_audit_0.1 | 1700 | 2 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_restructure_15 | s1_audit_0.3 | 1700 | 2 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_restructure_15 | s1_audit_0.6 | 1700 | 2 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_23_restructure_15 | s1_audit_0.1 | 1900 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | s1_audit_0.3 | 1900 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | s1_audit_0.6 | 1900 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | s1_audit_0.1 | 2100 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | s1_audit_0.3 | 2100 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | s1_audit_0.6 | 2100 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | s1_audit_0.1 | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | s1_audit_0.3 | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_23_restructure_15 | s1_audit_0.6 | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_audit_0.1 | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_audit_0.3 | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_audit_0.6 | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_audit_0.1 | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_control | s1_audit_0.3 | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_control | s1_audit_0.6 | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_control | s1_audit_0.1 | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_audit_0.3 | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_audit_0.6 | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_audit_0.1 | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_audit_0.3 | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_audit_0.6 | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_audit_0.1 | 900 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_control | s1_audit_0.3 | 900 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_control | s1_audit_0.6 | 900 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_control | s1_audit_0.1 | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_audit_0.3 | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_audit_0.6 | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_audit_0.1 | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_audit_0.3 | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_audit_0.6 | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_audit_0.1 | 1500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_audit_0.3 | 1500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_audit_0.6 | 1500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_audit_0.1 | 1700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_audit_0.3 | 1700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_audit_0.6 | 1700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_audit_0.1 | 1900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_audit_0.3 | 1900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_audit_0.6 | 1900 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_audit_0.1 | 2100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_audit_0.3 | 2100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_audit_0.6 | 2100 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_control | s1_audit_0.1 | 2300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_audit_0.3 | 2300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_control | s1_audit_0.6 | 2300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | s1_audit_0.1 | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | s1_audit_0.3 | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | s1_audit_0.6 | 300 | 0 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | s1_audit_0.1 | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_restructure_15 | s1_audit_0.3 | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_restructure_15 | s1_audit_0.6 | 300 | 0 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_restructure_15 | s1_audit_0.1 | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | s1_audit_0.3 | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | s1_audit_0.6 | 500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | s1_audit_0.1 | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | s1_audit_0.3 | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | s1_audit_0.6 | 700 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | s1_audit_0.1 | 900 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_restructure_15 | s1_audit_0.3 | 900 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_restructure_15 | s1_audit_0.6 | 900 | 1 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_restructure_15 | s1_audit_0.1 | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | s1_audit_0.3 | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | s1_audit_0.6 | 1100 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | s1_audit_0.1 | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | s1_audit_0.3 | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | s1_audit_0.6 | 1300 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | s1_audit_0.1 | 1500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | s1_audit_0.3 | 1500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | s1_audit_0.6 | 1500 | 1 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | s1_audit_0.1 | 1500 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_restructure_15 | s1_audit_0.3 | 1500 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_restructure_15 | s1_audit_0.6 | 1500 | 1 | filtered | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_restructure_15 | s1_audit_0.1 | 1700 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | s1_audit_0.3 | 1700 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | s1_audit_0.6 | 1700 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | s1_audit_0.1 | 1900 | 2 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_restructure_15 | s1_audit_0.3 | 1900 | 2 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_restructure_15 | s1_audit_0.6 | 1900 | 2 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_restructure_15 | s1_audit_0.1 | 2100 | 2 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_restructure_15 | s1_audit_0.3 | 2100 | 2 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_restructure_15 | s1_audit_0.6 | 2100 | 2 | raw | 0.5 | 1 | 2 | 4 | 13 | 0 |
| seed_37_restructure_15 | s1_audit_0.1 | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | s1_audit_0.3 | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
| seed_37_restructure_15 | s1_audit_0.6 | 2300 | 2 | raw | 0.4 | 1 | 2 | 5 | 12 | 0 |
Verdict: H1 is not supported as stated: none of the 944 repeated reports attained both precision and recall 1. These reports are pseudoreplicates, not independent experiments.
At the 300-ticket warm-up raw precision was 0.5 for seed 11 and 0.4 for seeds 23 and 37; filtered precision was 0.5 and recall was 1.0 for all three. The miner always accepted distractors `get_policy.entry_id` and `route_ticket.queue`, both consequences of D1; raw `route_ticket.branch` was also accepted at support 8–9. Ambiguous retrievals were zero in all reports.
All 16048 accepted and rejected candidate records, with reasons, are retained in `bench/results/e3a/evaluation-resumed-3/discovery.csv`; deterministic compressed shards and reconstruction details are in `bench/results/e3a/eval-compressed/manifest.json` and `bench/results/e3a/ARTIFACTS.md`.
The preregistration reports a development identity functional-dependency false negative; it was not corrected. Candidate-level results above are evaluation observations, not proof of independence.

## H2 — promoted-generation risk control
- Seven of seven distinct validation windows had bounds below 0.15, ranging from 0.118 to 0.145. There were 10 stream-level promotions (eight first-generation and two second-generation refits), not 49 independent promotions. The 49 transition rows repeat gates across arms and secondary replays; transition records omit stream identity. Restructure and CLINC share pre-shift windows within a seed.
| generation | validation_served | validation_errors | validation_upper_bound |
| --- | --- | --- | --- |
| 1 | 125 | 7 | 0.120731 |
| 1 | 231 | 19 | 0.13201 |
| 2 | 256 | 21 | 0.137741 |
| 1 | 241 | 20 | 0.131652 |
| 1 | 270 | 22 | 0.126702 |
| 1 | 277 | 27 | 0.144816 |
| 2 | 130 | 6 | 0.117995 |
- Seed 11 control never promoted (two attempts rejected). In control, served teacher disagreement after promotion was 62/778 = 0.080 for seed 23 and 85/832 = 0.102 for seed 37. Post-shift CLINC seed 37 was 117/713 = 0.164 and never demoted; post-shift restructure disagreement was 0.35–0.45. These served observations are descriptive, not validation guarantees.
- No promotion is not zero-error success. Validation controls teacher disagreement under its assumptions, not gold error or post-shift risk.

## H3 — control noninferiority
- Paired reference-minus-S1 accuracy loss: -0.0116667; one-sided 95% upper bound: -0.00693056; margin: 0.02.
- Verdict: noninferiority demonstrated using the preregistered 0.02 margin; stored flag: True.
| served_count | served_arm_accuracy | served_reference_accuracy | served_paired_accuracy_loss | resamples |
| --- | --- | --- | --- | --- |
| 1511 | 0.900728 | 0.872932 | -0.0277962 | 2000 |
- Served subset is selected and descriptive; the primary estimand includes all post-1200 tickets and has no cost condition.
- Composition: S1 served 1511/3600 control tickets (42.0%); seed 11 served 0/1200, seed 23 served 731/1200, and seed 37 served 780/1200. Per-seed reference-minus-S1 losses were 0, −0.0267, and −0.0083. The 2089 agent-served tickets contributed zero loss.
- On the selected served subset, S1 accuracy was 0.9007 versus agent 0.8729, a descriptive paired gain of 2.78 percentage points (seed-stratified bootstrap 95% CI [1.39, 4.17] points); 80 tickets favored S1 and 38 favored the agent. This is not the preregistered noninferiority estimand.
- Audits never replace the compiled answer: the compiled route remains served even when audited. Control accuracy is identical across audit rates 0.1–1.0.

## H4 — 15% restructure
| comparison | mean_audit_advantage | ci_low | ci_high | ticket_permutation_one_sided_p | holm_p_within_severity | per_seed_advantages | all_seed_effects_positive |
| --- | --- | --- | --- | --- | --- | --- | --- |
| s1_refit | -2.33333 | -5.66667 | 1 | 0.938031 | 1 | [-3.0, -1.0, -3.0] | False |
| escalation_only | -38.3333 | -54.0083 | -22.3333 | 1 | 1 | [-15.0, -65.0, -35.0] | False |
- Against s1_refit: lower error not demonstrated at Holm-adjusted 0.05.
- Against escalation_only: lower error not demonstrated at Holm-adjusted 0.05.
- The observed effect went the opposite way: versus escalation-only, audit yielded −38.3 correct tickets per seed, 95% CI [−54.0, −22.3], with seed effects −15, −65, and −35.
- On post-shift tickets served by escalation-only, compiled versus teacher gold accuracy was 0.829 versus 0.805, 0.786 versus 0.707, and 0.742 versus 0.699 for seeds 11, 23, and 37 respectively. Demotion on teacher disagreement handed tickets to a less accurate teacher; the selected comparison is descriptive.
- At audit rate 1.0 restructure detection took 270, 102, and 142 tickets (92, 62, and 92 audits), respectively; there were no false control demotions.
- Positive advantage favors audit. Ticket sign flips assume exchangeability; adaptation and temporal dependence may make uncertainty anti-conservative. Three seed effects are an essential secondary check; traffic shift is exploratory.

## H5 — exploratory equal-training-label comparison
| stream | arm | tickets | joint_accuracy | teacher_agreement | coverage | cost_per_ticket_usd | agent_calls | promotions | audits | detection_delay_tickets | detection_miss | false_demotions | recovery_ticket | amortization_ticket |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| seed_11_clinc | s1_audit | 2400 | 0.759167 | 0.994503 | 0.148333 | 0.00287439 | 2400 | 1 | 356 | NA | True | 0 | NA | NA |
| seed_11_clinc | s1_refit | 2400 | 0.757083 | 0.999154 | 0.0208333 | 0.00282401 | 2350 | 1 | 0 | NA | True | 0 | NA | 1190 |
| seed_11_clinc | surrogate_audit | 2400 | 0.757083 | 1 | 0 | 0.00281195 | 2400 | 0 | 0 | NA | True | 0 | NA | NA |
| seed_11_clinc | surrogate_refit | 2400 | 0.757083 | 1 | 0 | 0.00281195 | 2400 | 0 | 0 | NA | True | 0 | NA | NA |
| seed_11_control | s1_audit | 2400 | 0.745833 | 1 | 0 | 0.00288758 | 2400 | 0 | 0 | NA | NA | 0 | NA | NA |
| seed_11_control | s1_refit | 2400 | 0.745833 | 1 | 0 | 0.00288741 | 2400 | 0 | 0 | NA | NA | 0 | NA | NA |
| seed_11_control | surrogate_audit | 2400 | 0.745833 | 1 | 0 | 0.00282183 | 2400 | 0 | 0 | NA | NA | 0 | NA | NA |
| seed_11_control | surrogate_refit | 2400 | 0.745833 | 1 | 0 | 0.00282183 | 2400 | 0 | 0 | NA | NA | 0 | NA | NA |
| seed_11_restructure_15 | s1_audit | 2400 | 0.67625 | 0.987229 | 0.0491667 | 0.00295524 | 2400 | 1 | 118 | 270 | False | 0 | NA | NA |
| seed_11_restructure_15 | s1_refit | 2400 | 0.6775 | 0.994891 | 0.0270833 | 0.00288162 | 2335 | 1 | 0 | NA | True | 0 | NA | 1190 |
| seed_11_restructure_15 | surrogate_audit | 2400 | 0.678333 | 1 | 0 | 0.00287843 | 2400 | 0 | 0 | NA | True | 0 | NA | NA |
| seed_11_restructure_15 | surrogate_refit | 2400 | 0.678333 | 1 | 0 | 0.00287843 | 2400 | 0 | 0 | NA | True | 0 | NA | NA |
| seed_23_clinc | s1_audit | 2400 | 0.74625 | 0.97326 | 0.299167 | 0.00291968 | 2400 | 1 | 718 | NA | True | 0 | 1286 | NA |
| seed_23_clinc | s1_refit | 2400 | 0.738333 | 0.995756 | 0.0433333 | 0.00280815 | 2296 | 1 | 0 | NA | True | 0 | NA | 1161 |
| seed_23_clinc | surrogate_audit | 2400 | 0.73875 | 1 | 0 | 0.00285734 | 2400 | 0 | 0 | NA | True | 0 | NA | NA |
| seed_23_clinc | surrogate_refit | 2400 | 0.73875 | 1 | 0 | 0.00285734 | 2400 | 0 | 0 | NA | True | 0 | NA | NA |
| seed_23_control | s1_audit | 2400 | 0.7525 | 0.978669 | 0.325 | 0.00293371 | 2400 | 1 | 780 | NA | NA | 0 | NA | NA |
| seed_23_control | s1_refit | 2400 | 0.74125 | 0.994881 | 0.0925 | 0.00268585 | 2178 | 2 | 0 | NA | NA | 0 | NA | 1162 |
| seed_23_control | surrogate_audit | 2400 | 0.738333 | 1 | 0 | 0.00287255 | 2400 | 0 | 0 | NA | NA | 0 | NA | NA |
| seed_23_control | surrogate_refit | 2400 | 0.738333 | 1 | 0 | 0.00287255 | 2400 | 0 | 0 | NA | NA | 0 | NA | NA |
| seed_23_restructure_15 | s1_audit | 2400 | 0.669167 | 0.988889 | 0.0475 | 0.00299652 | 2400 | 1 | 114 | 102 | False | 0 | NA | NA |
| seed_23_restructure_15 | s1_refit | 2400 | 0.669583 | 0.989744 | 0.04625 | 0.00286201 | 2289 | 1 | 0 | NA | True | 0 | NA | 1161 |
| seed_23_restructure_15 | surrogate_audit | 2400 | 0.670833 | 1 | 0 | 0.00292004 | 2400 | 0 | 0 | NA | True | 0 | NA | NA |
| seed_23_restructure_15 | surrogate_refit | 2400 | 0.670833 | 1 | 0 | 0.00292004 | 2400 | 0 | 0 | NA | True | 0 | NA | NA |
| seed_37_clinc | s1_audit | 2400 | 0.76625 | 0.955932 | 0.320417 | 0.002918 | 2400 | 1 | 769 | NA | True | 0 | 1200 | NA |
| seed_37_clinc | s1_refit | 2400 | 0.76625 | 0.994915 | 0.0766667 | 0.00271986 | 2216 | 2 | 0 | NA | True | 0 | NA | 1146 |
| seed_37_clinc | surrogate_audit | 2400 | 0.76375 | 1 | 0 | 0.00285824 | 2400 | 0 | 0 | NA | True | 0 | NA | NA |
| seed_37_clinc | surrogate_refit | 2400 | 0.76375 | 1 | 0 | 0.00285824 | 2400 | 0 | 0 | NA | True | 0 | NA | NA |
| seed_37_control | s1_audit | 2400 | 0.765833 | 0.965576 | 0.3475 | 0.00294427 | 2400 | 1 | 834 | NA | NA | 0 | NA | NA |
| seed_37_control | s1_refit | 2400 | 0.761667 | 0.995325 | 0.0466667 | 0.00282312 | 2288 | 1 | 0 | NA | NA | 0 | NA | 1146 |
| seed_37_control | surrogate_audit | 2400 | 0.76125 | 1 | 0 | 0.00288496 | 2400 | 0 | 0 | NA | NA | 0 | NA | NA |
| seed_37_control | surrogate_refit | 2400 | 0.76125 | 1 | 0 | 0.00288496 | 2400 | 0 | 0 | NA | NA | 0 | NA | NA |
| seed_37_restructure_15 | s1_audit | 2400 | 0.694167 | 0.983844 | 0.0616667 | 0.00305308 | 2400 | 1 | 148 | 142 | False | 0 | NA | NA |
| seed_37_restructure_15 | s1_refit | 2400 | 0.695417 | 0.988095 | 0.0504167 | 0.00290318 | 2279 | 1 | 0 | NA | True | 0 | NA | 1146 |
| seed_37_restructure_15 | surrogate_audit | 2400 | 0.693333 | 1 | 0 | 0.00297782 | 2400 | 0 | 0 | NA | True | 0 | NA | NA |
| seed_37_restructure_15 | surrogate_refit | 2400 | 0.693333 | 1 | 0 | 0.00297782 | 2400 | 0 | 0 | NA | True | 0 | NA | NA |
- Descriptive comparison only; no preregistered significance criterion. Equal training-label availability is not equal total agent calls.
Across the nine equally sized streams, S1 audit had mean joint accuracy 0.7306 and coverage 0.1776; surrogate audit had 0.7275 and 0.0000. This exploratory difference is descriptive, not a significance verdict.

## Per-stream outcomes and audit-rate replay
| stream | arm | tickets | joint_accuracy | teacher_agreement | coverage | total_cost_usd | cost_per_ticket_usd | agent_calls | promotions | demotions | audits | detection_delay_tickets | detection_delay_audits | detection_miss | false_demotions | recovery_ticket | amortization_ticket |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| seed_11_clinc | always_agent | 2400 | 0.757083 | 1 | 0 | 6.74868 | 0.00281195 | 2400 | 0 | 0 | 0 | NA | NA | True | 0 | NA | NA |
| seed_11_clinc | escalation_only | 2400 | 0.759167 | 0.994503 | 0.148333 | 5.95425 | 0.00248094 | 2044 | 1 | 0 | 0 | NA | NA | True | 0 | NA | 1190 |
| seed_11_clinc | fixed_gate | 2400 | 0.757083 | 1 | 0 | 6.90391 | 0.00287663 | 2400 | 0 | 0 | 0 | NA | NA | True | 0 | NA | NA |
| seed_11_clinc | fixed_gate_config_hash | 2400 | 0.764583 | 0.988584 | 0.1025 | 6.27326 | 0.00261386 | 2154 | 1 | 0 | 0 | NA | NA | True | 0 | 2084 | 2094 |
| seed_11_clinc | knn_cache | 2400 | 0.756667 | 0.999577 | 0.00125 | 6.74868 | 0.00281195 | 2400 | 1 | 1 | 3 | NA | NA | True | 1 | NA | NA |
| seed_11_clinc | oracle_audit | 2400 | 0.759167 | 0.994503 | 0.148333 | 6.89854 | 0.00287439 | 2400 | 1 | 0 | 356 | NA | NA | True | 0 | NA | NA |
| seed_11_clinc | s1_audit | 2400 | 0.759167 | 0.994503 | 0.148333 | 6.89854 | 0.00287439 | 2400 | 1 | 0 | 356 | NA | NA | True | 0 | NA | NA |
| seed_11_clinc | s1_refit | 2400 | 0.757083 | 0.999154 | 0.0208333 | 6.77763 | 0.00282401 | 2350 | 1 | 0 | 0 | NA | NA | True | 0 | NA | 1190 |
| seed_11_clinc | surrogate_audit | 2400 | 0.757083 | 1 | 0 | 6.74868 | 0.00281195 | 2400 | 0 | 0 | 0 | NA | NA | True | 0 | NA | NA |
| seed_11_clinc | surrogate_refit | 2400 | 0.757083 | 1 | 0 | 6.74868 | 0.00281195 | 2400 | 0 | 0 | 0 | NA | NA | True | 0 | NA | NA |
| seed_11_control | always_agent | 2400 | 0.745833 | 1 | 0 | 6.77238 | 0.00282183 | 2400 | 0 | 0 | 0 | NA | NA | NA | 0 | NA | NA |
| seed_11_control | escalation_only | 2400 | 0.745833 | 1 | 0 | 6.93018 | 0.00288758 | 2400 | 0 | 0 | 0 | NA | NA | NA | 0 | NA | NA |
| seed_11_control | fixed_gate | 2400 | 0.745833 | 1 | 0 | 6.92767 | 0.00288653 | 2400 | 0 | 0 | 0 | NA | NA | NA | 0 | NA | NA |
| seed_11_control | fixed_gate_config_hash | 2400 | 0.745833 | 1 | 0 | 6.92767 | 0.00288653 | 2400 | 0 | 0 | 0 | NA | NA | NA | 0 | NA | NA |
| seed_11_control | knn_cache | 2400 | 0.745417 | 0.999574 | 0.00125 | 6.77238 | 0.00282183 | 2400 | 1 | 1 | 3 | NA | NA | NA | 1 | NA | NA |
| seed_11_control | oracle_audit | 2400 | 0.745833 | 1 | 0 | 6.93018 | 0.00288758 | 2400 | 0 | 0 | 0 | NA | NA | NA | 0 | NA | NA |
| seed_11_control | s1_audit | 2400 | 0.745833 | 1 | 0 | 6.93018 | 0.00288758 | 2400 | 0 | 0 | 0 | NA | NA | NA | 0 | NA | NA |
| seed_11_control | s1_audit_0.1 | 2400 | 0.745833 | 1 | 0 | 6.93018 | 0.00288758 | 2400 | 0 | 0 | 0 | NA | NA | NA | 0 | NA | NA |
| seed_11_control | s1_audit_0.3 | 2400 | 0.745833 | 1 | 0 | 6.93018 | 0.00288758 | 2400 | 0 | 0 | 0 | NA | NA | NA | 0 | NA | NA |
| seed_11_control | s1_audit_0.6 | 2400 | 0.745833 | 1 | 0 | 6.93018 | 0.00288758 | 2400 | 0 | 0 | 0 | NA | NA | NA | 0 | NA | NA |
| seed_11_control | s1_refit | 2400 | 0.745833 | 1 | 0 | 6.9298 | 0.00288741 | 2400 | 0 | 0 | 0 | NA | NA | NA | 0 | NA | NA |
| seed_11_control | surrogate_audit | 2400 | 0.745833 | 1 | 0 | 6.77238 | 0.00282183 | 2400 | 0 | 0 | 0 | NA | NA | NA | 0 | NA | NA |
| seed_11_control | surrogate_refit | 2400 | 0.745833 | 1 | 0 | 6.77238 | 0.00282183 | 2400 | 0 | 0 | 0 | NA | NA | NA | 0 | NA | NA |
| seed_11_restructure_15 | always_agent | 2400 | 0.678333 | 1 | 0 | 6.90823 | 0.00287843 | 2400 | 0 | 0 | 0 | NA | NA | True | 0 | NA | NA |
| seed_11_restructure_15 | escalation_only | 2400 | 0.6825 | 0.948914 | 0.169167 | 5.94972 | 0.00247905 | 1994 | 1 | 0 | 0 | NA | NA | True | 0 | NA | 1190 |
| seed_11_restructure_15 | fixed_gate | 2400 | 0.678333 | 1 | 0 | 7.06355 | 0.00294315 | 2400 | 0 | 0 | 0 | NA | NA | True | 0 | NA | NA |
| seed_11_restructure_15 | fixed_gate_config_hash | 2400 | 0.678333 | 1 | 0 | 7.14586 | 0.00297744 | 2400 | 0 | 0 | 0 | NA | NA | True | 0 | NA | NA |
| seed_11_restructure_15 | knn_cache | 2400 | 0.677917 | 0.999574 | 0.00125 | 6.90823 | 0.00287843 | 2400 | 1 | 1 | 3 | NA | NA | True | 1 | NA | NA |
| seed_11_restructure_15 | oracle_audit | 2400 | 0.6825 | 0.948914 | 0.169167 | 7.05818 | 0.00294091 | 2400 | 1 | 0 | 406 | NA | NA | True | 0 | NA | NA |
| seed_11_restructure_15 | s1_audit | 2400 | 0.67625 | 0.987229 | 0.0491667 | 7.09258 | 0.00295524 | 2400 | 1 | 1 | 118 | 270 | 92 | False | 0 | NA | NA |
| seed_11_restructure_15 | s1_audit_0.1 | 2400 | 0.680417 | 0.957003 | 0.145417 | 6.20326 | 0.00258469 | 2086 | 1 | 1 | 35 | 1014 | 30 | False | 0 | NA | 1208 |
| seed_11_restructure_15 | s1_audit_0.3 | 2400 | 0.675833 | 0.987654 | 0.04875 | 6.89857 | 0.0028744 | 2326 | 1 | 1 | 43 | 267 | 32 | False | 0 | NA | 1239 |
| seed_11_restructure_15 | s1_audit_0.6 | 2400 | 0.67625 | 0.988931 | 0.04625 | 6.98798 | 0.00291166 | 2360 | 1 | 1 | 71 | 249 | 55 | False | 0 | NA | 1312 |
| seed_11_restructure_15 | s1_refit | 2400 | 0.6775 | 0.994891 | 0.0270833 | 6.91588 | 0.00288162 | 2335 | 1 | 0 | 0 | NA | NA | True | 0 | NA | 1190 |
| seed_11_restructure_15 | surrogate_audit | 2400 | 0.678333 | 1 | 0 | 6.90823 | 0.00287843 | 2400 | 0 | 0 | 0 | NA | NA | True | 0 | NA | NA |
| seed_11_restructure_15 | surrogate_refit | 2400 | 0.678333 | 1 | 0 | 6.90823 | 0.00287843 | 2400 | 0 | 0 | 0 | NA | NA | True | 0 | NA | NA |
| seed_23_clinc | always_agent | 2400 | 0.73875 | 1 | 0 | 6.85762 | 0.00285734 | 2400 | 0 | 0 | 0 | NA | NA | True | 0 | NA | NA |
| seed_23_clinc | escalation_only | 2400 | 0.74625 | 0.97326 | 0.299167 | 5.08745 | 0.00211977 | 1682 | 1 | 0 | 0 | NA | NA | True | 0 | 1286 | 1161 |
| seed_23_clinc | fixed_gate | 2400 | 0.7575 | 0.960951 | 0.330833 | 4.85162 | 0.00202151 | 1606 | 1 | 0 | 0 | NA | NA | True | 0 | 1200 | 1147 |
| seed_23_clinc | fixed_gate_config_hash | 2400 | 0.73875 | 1 | 0 | 7.03398 | 0.00293083 | 2400 | 0 | 0 | 0 | NA | NA | True | 0 | NA | NA |
| seed_23_clinc | knn_cache | 2400 | 0.738333 | 0.999576 | 0.000416667 | 6.85762 | 0.00285734 | 2400 | 1 | 1 | 1 | NA | NA | True | 1 | NA | NA |
| seed_23_clinc | oracle_audit | 2400 | 0.74625 | 0.97326 | 0.299167 | 7.00724 | 0.00291968 | 2400 | 1 | 0 | 718 | NA | NA | True | 0 | 1286 | NA |
| seed_23_clinc | s1_audit | 2400 | 0.74625 | 0.97326 | 0.299167 | 7.00724 | 0.00291968 | 2400 | 1 | 0 | 718 | NA | NA | True | 0 | 1286 | NA |
| seed_23_clinc | s1_refit | 2400 | 0.738333 | 0.995756 | 0.0433333 | 6.73957 | 0.00280815 | 2296 | 1 | 0 | 0 | NA | NA | True | 0 | NA | 1161 |
| seed_23_clinc | surrogate_audit | 2400 | 0.73875 | 1 | 0 | 6.85762 | 0.00285734 | 2400 | 0 | 0 | 0 | NA | NA | True | 0 | NA | NA |
| seed_23_clinc | surrogate_refit | 2400 | 0.73875 | 1 | 0 | 6.85762 | 0.00285734 | 2400 | 0 | 0 | 0 | NA | NA | True | 0 | NA | NA |
| seed_23_control | always_agent | 2400 | 0.738333 | 1 | 0 | 6.89413 | 0.00287255 | 2400 | 0 | 0 | 0 | NA | NA | NA | 0 | NA | NA |
| seed_23_control | escalation_only | 2400 | 0.7525 | 0.978669 | 0.325 | 4.95638 | 0.00206516 | 1620 | 1 | 0 | 0 | NA | NA | NA | 0 | NA | 1162 |
| seed_23_control | fixed_gate | 2400 | 0.7625 | 0.97227 | 0.3725 | 4.62629 | 0.00192762 | 1506 | 1 | 0 | 0 | NA | NA | NA | 0 | NA | 1147 |
| seed_23_control | fixed_gate_config_hash | 2400 | 0.738333 | 1 | 0 | 7.04942 | 0.00293726 | 2400 | 0 | 0 | 0 | NA | NA | NA | 0 | NA | NA |
| seed_23_control | knn_cache | 2400 | 0.737917 | 0.999573 | 0.000416667 | 6.89413 | 0.00287255 | 2400 | 1 | 1 | 1 | NA | NA | NA | 1 | NA | NA |
| seed_23_control | oracle_audit | 2400 | 0.7525 | 0.978669 | 0.325 | 7.0409 | 0.00293371 | 2400 | 1 | 0 | 780 | NA | NA | NA | 0 | NA | NA |
| seed_23_control | s1_audit | 2400 | 0.7525 | 0.978669 | 0.325 | 7.0409 | 0.00293371 | 2400 | 1 | 0 | 780 | NA | NA | NA | 0 | NA | NA |
| seed_23_control | s1_audit_0.1 | 2400 | 0.7525 | 0.978669 | 0.325 | 5.19336 | 0.0021639 | 1705 | 1 | 0 | 85 | NA | NA | NA | 0 | NA | 1163 |
| seed_23_control | s1_audit_0.3 | 2400 | 0.7525 | 0.978669 | 0.325 | 5.60858 | 0.00233691 | 1864 | 1 | 0 | 244 | NA | NA | NA | 0 | NA | 1168 |
| seed_23_control | s1_audit_0.6 | 2400 | 0.7525 | 0.978669 | 0.325 | 6.19727 | 0.0025822 | 2083 | 1 | 0 | 463 | NA | NA | NA | 0 | NA | 1243 |
| seed_23_control | s1_refit | 2400 | 0.74125 | 0.994881 | 0.0925 | 6.44605 | 0.00268585 | 2178 | 2 | 0 | 0 | NA | NA | NA | 0 | NA | 1162 |
| seed_23_control | surrogate_audit | 2400 | 0.738333 | 1 | 0 | 6.89413 | 0.00287255 | 2400 | 0 | 0 | 0 | NA | NA | NA | 0 | NA | NA |
| seed_23_control | surrogate_refit | 2400 | 0.738333 | 1 | 0 | 6.89413 | 0.00287255 | 2400 | 0 | 0 | 0 | NA | NA | NA | 0 | NA | NA |
| seed_23_restructure_15 | always_agent | 2400 | 0.670833 | 1 | 0 | 7.0081 | 0.00292004 | 2400 | 0 | 0 | 0 | NA | NA | True | 0 | NA | NA |
| seed_23_restructure_15 | escalation_only | 2400 | 0.69625 | 0.888034 | 0.337083 | 4.95733 | 0.00206555 | 1591 | 1 | 0 | 0 | NA | NA | True | 0 | 1335 | 1161 |
| seed_23_restructure_15 | fixed_gate | 2400 | 0.705417 | 0.869231 | 0.372917 | 4.66421 | 0.00194342 | 1505 | 1 | 0 | 0 | NA | NA | True | 0 | 1315 | 1147 |
| seed_23_restructure_15 | fixed_gate_config_hash | 2400 | 0.670833 | 1 | 0 | 7.2468 | 0.0030195 | 2400 | 0 | 0 | 0 | NA | NA | True | 0 | NA | NA |
| seed_23_restructure_15 | knn_cache | 2400 | 0.670417 | 0.999573 | 0.000416667 | 7.0081 | 0.00292004 | 2400 | 1 | 1 | 1 | NA | NA | True | 1 | NA | NA |
| seed_23_restructure_15 | oracle_audit | 2400 | 0.684583 | 0.93547 | 0.19625 | 7.17639 | 0.00299016 | 2400 | 1 | 1 | 471 | 660 | 419 | False | 0 | 1335 | NA |
| seed_23_restructure_15 | s1_audit | 2400 | 0.669167 | 0.988889 | 0.0475 | 7.19165 | 0.00299652 | 2400 | 1 | 1 | 114 | 102 | 62 | False | 0 | NA | NA |
| seed_23_restructure_15 | s1_audit_0.1 | 2400 | 0.676667 | 0.97265 | 0.0933333 | 6.6195 | 0.00275813 | 2199 | 1 | 1 | 23 | 266 | 20 | False | 0 | NA | 1162 |
| seed_23_restructure_15 | s1_audit_0.3 | 2400 | 0.676667 | 0.97265 | 0.0933333 | 6.72826 | 0.00280344 | 2236 | 1 | 1 | 60 | 266 | 47 | False | 0 | NA | 1168 |
| seed_23_restructure_15 | s1_audit_0.6 | 2400 | 0.675833 | 0.979487 | 0.0754167 | 6.98487 | 0.00291036 | 2329 | 1 | 1 | 110 | 202 | 76 | False | 0 | NA | 1225 |
| seed_23_restructure_15 | s1_refit | 2400 | 0.669583 | 0.989744 | 0.04625 | 6.86882 | 0.00286201 | 2289 | 1 | 0 | 0 | NA | NA | True | 0 | NA | 1161 |
| seed_23_restructure_15 | surrogate_audit | 2400 | 0.670833 | 1 | 0 | 7.0081 | 0.00292004 | 2400 | 0 | 0 | 0 | NA | NA | True | 0 | NA | NA |
| seed_23_restructure_15 | surrogate_refit | 2400 | 0.670833 | 1 | 0 | 7.0081 | 0.00292004 | 2400 | 0 | 0 | 0 | NA | NA | True | 0 | NA | NA |
| seed_37_clinc | always_agent | 2400 | 0.76375 | 1 | 0 | 6.85977 | 0.00285824 | 2400 | 0 | 0 | 0 | NA | NA | True | 0 | NA | NA |
| seed_37_clinc | escalation_only | 2400 | 0.76625 | 0.955932 | 0.320417 | 4.91931 | 0.00204971 | 1631 | 1 | 0 | 0 | NA | NA | True | 0 | 1200 | 1146 |
| seed_37_clinc | fixed_gate | 2400 | 0.776667 | 0.952542 | 0.354167 | 4.70874 | 0.00196198 | 1550 | 1 | 0 | 0 | NA | NA | True | 0 | 1200 | 1138 |
| seed_37_clinc | fixed_gate_config_hash | 2400 | 0.764167 | 0.999153 | 0.0279167 | 6.8529 | 0.00285538 | 2333 | 1 | 0 | 0 | NA | NA | True | 0 | NA | 1138 |
| seed_37_clinc | knn_cache | 2400 | 0.763333 | 0.999576 | 0.000416667 | 6.85977 | 0.00285824 | 2400 | 1 | 1 | 1 | NA | NA | True | 1 | NA | NA |
| seed_37_clinc | oracle_audit | 2400 | 0.76625 | 0.955932 | 0.320417 | 7.0032 | 0.002918 | 2400 | 1 | 0 | 769 | NA | NA | True | 0 | 1200 | NA |
| seed_37_clinc | s1_audit | 2400 | 0.76625 | 0.955932 | 0.320417 | 7.0032 | 0.002918 | 2400 | 1 | 0 | 769 | NA | NA | True | 0 | 1200 | NA |
| seed_37_clinc | s1_refit | 2400 | 0.76625 | 0.994915 | 0.0766667 | 6.52767 | 0.00271986 | 2216 | 2 | 0 | 0 | NA | NA | True | 0 | NA | 1146 |
| seed_37_clinc | surrogate_audit | 2400 | 0.76375 | 1 | 0 | 6.85977 | 0.00285824 | 2400 | 0 | 0 | 0 | NA | NA | True | 0 | NA | NA |
| seed_37_clinc | surrogate_refit | 2400 | 0.76375 | 1 | 0 | 6.85977 | 0.00285824 | 2400 | 0 | 0 | 0 | NA | NA | True | 0 | NA | NA |
| seed_37_control | always_agent | 2400 | 0.76125 | 1 | 0 | 6.92391 | 0.00288496 | 2400 | 0 | 0 | 0 | NA | NA | NA | 0 | NA | NA |
| seed_37_control | escalation_only | 2400 | 0.765833 | 0.965576 | 0.3475 | 4.81513 | 0.0020063 | 1566 | 1 | 0 | 0 | NA | NA | NA | 0 | NA | 1146 |
| seed_37_control | fixed_gate | 2400 | 0.78375 | 0.964301 | 0.399167 | 4.4493 | 0.00185388 | 1442 | 1 | 0 | 0 | NA | NA | NA | 0 | NA | 1138 |
| seed_37_control | fixed_gate_config_hash | 2400 | 0.78375 | 0.964301 | 0.399167 | 4.4493 | 0.00185388 | 1442 | 1 | 0 | 0 | NA | NA | NA | 0 | NA | 1138 |
| seed_37_control | knn_cache | 2400 | 0.760833 | 0.999575 | 0.000416667 | 6.92391 | 0.00288496 | 2400 | 1 | 1 | 1 | NA | NA | NA | 1 | NA | NA |
| seed_37_control | oracle_audit | 2400 | 0.765833 | 0.965576 | 0.3475 | 7.06624 | 0.00294427 | 2400 | 1 | 0 | 834 | NA | NA | NA | 0 | NA | NA |
| seed_37_control | s1_audit | 2400 | 0.765833 | 0.965576 | 0.3475 | 7.06624 | 0.00294427 | 2400 | 1 | 0 | 834 | NA | NA | NA | 0 | NA | NA |
| seed_37_control | s1_audit_0.1 | 2400 | 0.765833 | 0.965576 | 0.3475 | 5.03767 | 0.00209903 | 1644 | 1 | 0 | 78 | NA | NA | NA | 0 | NA | 1147 |
| seed_37_control | s1_audit_0.3 | 2400 | 0.765833 | 0.965576 | 0.3475 | 5.45546 | 0.00227311 | 1802 | 1 | 0 | 236 | NA | NA | NA | 0 | NA | 1157 |
| seed_37_control | s1_audit_0.6 | 2400 | 0.765833 | 0.965576 | 0.3475 | 6.17546 | 0.00257311 | 2074 | 1 | 0 | 508 | NA | NA | NA | 0 | NA | 1215 |
| seed_37_control | s1_refit | 2400 | 0.761667 | 0.995325 | 0.0466667 | 6.77549 | 0.00282312 | 2288 | 1 | 0 | 0 | NA | NA | NA | 0 | NA | 1146 |
| seed_37_control | surrogate_audit | 2400 | 0.76125 | 1 | 0 | 6.92391 | 0.00288496 | 2400 | 0 | 0 | 0 | NA | NA | NA | 0 | NA | NA |
| seed_37_control | surrogate_refit | 2400 | 0.76125 | 1 | 0 | 6.92391 | 0.00288496 | 2400 | 0 | 0 | 0 | NA | NA | NA | 0 | NA | NA |
| seed_37_restructure_15 | always_agent | 2400 | 0.693333 | 1 | 0 | 7.14676 | 0.00297782 | 2400 | 0 | 0 | 0 | NA | NA | True | 0 | NA | NA |
| seed_37_restructure_15 | escalation_only | 2400 | 0.70875 | 0.869048 | 0.362917 | 4.76428 | 0.00198512 | 1529 | 1 | 0 | 0 | NA | NA | True | 0 | 1488 | 1146 |
| seed_37_restructure_15 | fixed_gate | 2400 | 0.726667 | 0.851616 | 0.400417 | 4.51433 | 0.00188097 | 1439 | 1 | 0 | 0 | NA | NA | True | 0 | 1226 | 1138 |
| seed_37_restructure_15 | fixed_gate_config_hash | 2400 | 0.69375 | 0.99915 | 0.0279167 | 7.20787 | 0.00300328 | 2333 | 1 | 0 | 0 | NA | NA | True | 0 | NA | 1138 |
| seed_37_restructure_15 | knn_cache | 2400 | 0.692917 | 0.999575 | 0.000416667 | 7.14676 | 0.00297782 | 2400 | 1 | 1 | 1 | NA | NA | True | 1 | NA | NA |
| seed_37_restructure_15 | oracle_audit | 2400 | 0.6925 | 0.97619 | 0.0754167 | 7.32739 | 0.00305308 | 2400 | 1 | 1 | 181 | 189 | 125 | False | 0 | NA | NA |
| seed_37_restructure_15 | s1_audit | 2400 | 0.694167 | 0.983844 | 0.0616667 | 7.32739 | 0.00305308 | 2400 | 1 | 1 | 148 | 142 | 92 | False | 0 | NA | NA |
| seed_37_restructure_15 | s1_audit_0.1 | 2400 | 0.695 | 0.981718 | 0.0658333 | 6.91886 | 0.00288286 | 2257 | 1 | 1 | 15 | 158 | 11 | False | 0 | NA | 1146 |
| seed_37_restructure_15 | s1_audit_0.3 | 2400 | 0.692083 | 0.971088 | 0.0883333 | 6.92397 | 0.00288499 | 2257 | 1 | 1 | 69 | 239 | 52 | False | 0 | NA | 1157 |
| seed_37_restructure_15 | s1_audit_0.6 | 2400 | 0.695 | 0.982143 | 0.0645833 | 7.16751 | 0.00298646 | 2342 | 1 | 1 | 97 | 154 | 62 | False | 0 | NA | 1223 |
| seed_37_restructure_15 | s1_refit | 2400 | 0.695417 | 0.988095 | 0.0504167 | 6.96762 | 0.00290318 | 2279 | 1 | 0 | 0 | NA | NA | True | 0 | NA | 1146 |
| seed_37_restructure_15 | surrogate_audit | 2400 | 0.693333 | 1 | 0 | 7.14676 | 0.00297782 | 2400 | 0 | 0 | 0 | NA | NA | True | 0 | NA | NA |
| seed_37_restructure_15 | surrogate_refit | 2400 | 0.693333 | 1 | 0 | 7.14676 | 0.00297782 | 2400 | 0 | 0 | 0 | NA | NA | True | 0 | NA | NA |

### Secondary audit rates
| stream | arm | audit_rate | cost_ratio_vs_always_agent | detection_delay_tickets | detection_delay_audits | detection_miss | false_demotions |
| --- | --- | --- | --- | --- | --- | --- | --- |
| seed_11_clinc | s1_audit | 1 | 1.02221 | NA | NA | True | 0 |
| seed_11_control | s1_audit | 1 | 1.0233 | NA | NA | NA | 0 |
| seed_11_control | s1_audit_0.1 | 0.1 | 1.0233 | NA | NA | NA | 0 |
| seed_11_control | s1_audit_0.3 | 0.3 | 1.0233 | NA | NA | NA | 0 |
| seed_11_control | s1_audit_0.6 | 0.6 | 1.0233 | NA | NA | NA | 0 |
| seed_11_restructure_15 | s1_audit | 1 | 1.02669 | 270 | 92 | False | 0 |
| seed_11_restructure_15 | s1_audit_0.1 | 0.1 | 0.897953 | 1014 | 30 | False | 0 |
| seed_11_restructure_15 | s1_audit_0.3 | 0.3 | 0.998602 | 267 | 32 | False | 0 |
| seed_11_restructure_15 | s1_audit_0.6 | 0.6 | 1.01154 | 249 | 55 | False | 0 |
| seed_23_clinc | s1_audit | 1 | 1.02182 | NA | NA | True | 0 |
| seed_23_control | s1_audit | 1 | 1.02129 | NA | NA | NA | 0 |
| seed_23_control | s1_audit_0.1 | 0.1 | 0.753302 | NA | NA | NA | 0 |
| seed_23_control | s1_audit_0.3 | 0.3 | 0.81353 | NA | NA | NA | 0 |
| seed_23_control | s1_audit_0.6 | 0.6 | 0.898921 | NA | NA | NA | 0 |
| seed_23_restructure_15 | s1_audit | 1 | 1.02619 | 102 | 62 | False | 0 |
| seed_23_restructure_15 | s1_audit_0.1 | 0.1 | 0.94455 | 266 | 20 | False | 0 |
| seed_23_restructure_15 | s1_audit_0.3 | 0.3 | 0.960069 | 266 | 47 | False | 0 |
| seed_23_restructure_15 | s1_audit_0.6 | 0.6 | 0.996685 | 202 | 76 | False | 0 |
| seed_37_clinc | s1_audit | 1 | 1.02091 | NA | NA | True | 0 |
| seed_37_control | s1_audit | 1 | 1.02056 | NA | NA | NA | 0 |
| seed_37_control | s1_audit_0.1 | 0.1 | 0.727575 | NA | NA | NA | 0 |
| seed_37_control | s1_audit_0.3 | 0.3 | 0.787916 | NA | NA | NA | 0 |
| seed_37_control | s1_audit_0.6 | 0.6 | 0.891902 | NA | NA | NA | 0 |
| seed_37_restructure_15 | s1_audit | 1 | 1.02527 | 142 | 92 | False | 0 |
| seed_37_restructure_15 | s1_audit_0.1 | 0.1 | 0.968111 | 158 | 11 | False | 0 |
| seed_37_restructure_15 | s1_audit_0.3 | 0.3 | 0.968826 | 239 | 52 | False | 0 |
| seed_37_restructure_15 | s1_audit_0.6 | 0.6 | 1.0029 | 154 | 62 | False | 0 |

## Ticket-level agreement and completeness
- seed_11_clinc: secondary audit-rate replays skipped by user instruction (deviation).
- seed_23_clinc: secondary audit-rate replays skipped by user instruction (deviation).
- seed_37_clinc: secondary audit-rate replays skipped by user instruction (deviation).
| stream | arm | served | audits | served_joint_labeled | served_joint_error | gold_department_correct | gold_priority_correct | gold_identity_correct | d1_teacher_agreement | d2_teacher_agreement | joint_decision_agreement | latency_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| seed_11_control | always_agent | 0 | 0 | 0 | NA | 0.78375 | 0.9225 | 0.8575 | NA | NA | NA | 7673.99 |
| seed_11_control | s1_audit | 0 | 0 | 0 | NA | 0.78375 | 0.9225 | 0.8575 | 0.782525 | 0.874401 | 0.781054 | 7765.04 |
| seed_11_control | s1_refit | 0 | 0 | 0 | NA | 0.78375 | 0.9225 | 0.8575 | 0.783005 | 0.881429 | 0.777244 | 7764.33 |
| seed_11_control | escalation_only | 0 | 0 | 0 | NA | 0.78375 | 0.9225 | 0.8575 | 0.782525 | 0.874401 | 0.781054 | 7765.04 |
| seed_11_control | fixed_gate | 0 | 0 | 0 | NA | 0.78375 | 0.9225 | 0.8575 | NA | NA | NA | 7754.27 |
| seed_11_control | fixed_gate_config_hash | 0 | 0 | 0 | NA | 0.78375 | 0.9225 | 0.8575 | NA | NA | NA | 7754.27 |
| seed_11_control | oracle_audit | 0 | 0 | 0 | NA | 0.78375 | 0.9225 | 0.8575 | 0.782525 | 0.874401 | 0.781054 | 7765.04 |
| seed_11_control | knn_cache | 3 | 3 | 0 | NA | 0.783333 | 0.9225 | 0.8575 | 0.666667 | NA | NA | 7795.36 |
| seed_11_control | surrogate_audit | 0 | 0 | 0 | NA | 0.78375 | 0.9225 | 0.8575 | 0.345175 | 0.668095 | 0.340855 | 7721.61 |
| seed_11_control | surrogate_refit | 0 | 0 | 0 | NA | 0.78375 | 0.9225 | 0.8575 | 0.344215 | 0.674286 | 0.341335 | 7720.83 |
| seed_11_control | s1_audit_0.1 | 0 | 0 | 0 | NA | 0.78375 | 0.9225 | 0.8575 | 0.782525 | 0.874401 | 0.781054 | 7765 |
| seed_11_control | s1_audit_0.3 | 0 | 0 | 0 | NA | 0.78375 | 0.9225 | 0.8575 | 0.782525 | 0.874401 | 0.781054 | 7765 |
| seed_11_control | s1_audit_0.6 | 0 | 0 | 0 | NA | 0.78375 | 0.9225 | 0.8575 | 0.782525 | 0.874401 | 0.781054 | 7765 |
| seed_11_restructure_15 | always_agent | 0 | 0 | 0 | NA | 0.715 | 0.922083 | 0.858333 | NA | NA | NA | 7851.54 |
| seed_11_restructure_15 | s1_audit | 118 | 118 | 118 | 0.279661 | 0.712917 | 0.922083 | 0.859583 | 0.683654 | 0.871429 | 0.680288 | 7936.14 |
| seed_11_restructure_15 | s1_refit | 65 | 0 | 65 | 0.184615 | 0.714167 | 0.922083 | 0.85875 | 0.647115 | 0.880952 | 0.64375 | 7724.73 |
| seed_11_restructure_15 | escalation_only | 406 | 0 | 406 | 0.307882 | 0.717917 | 0.9225 | 0.860833 | 0.615865 | 0.877619 | 0.612981 | 6570.87 |
| seed_11_restructure_15 | fixed_gate | 0 | 0 | 0 | NA | 0.715 | 0.922083 | 0.858333 | NA | NA | NA | 7931.66 |
| seed_11_restructure_15 | fixed_gate_config_hash | 0 | 0 | 0 | NA | 0.715 | 0.922083 | 0.858333 | NA | NA | NA | 7934.94 |
| seed_11_restructure_15 | oracle_audit | 406 | 406 | 406 | 0.307882 | 0.717917 | 0.9225 | 0.860833 | 0.615865 | 0.877619 | 0.612981 | 7933.57 |
| seed_11_restructure_15 | knn_cache | 3 | 3 | 0 | NA | 0.714583 | 0.922083 | 0.858333 | 0.666667 | NA | NA | 7961.59 |
| seed_11_restructure_15 | surrogate_audit | 0 | 0 | 0 | NA | 0.715 | 0.922083 | 0.858333 | 0.279327 | 0.645238 | 0.275481 | 7900.81 |
| seed_11_restructure_15 | surrogate_refit | 0 | 0 | 0 | NA | 0.715 | 0.922083 | 0.858333 | 0.286538 | 0.650952 | 0.283173 | 7900.28 |
| seed_11_restructure_15 | s1_audit_0.1 | 349 | 35 | 349 | 0.303725 | 0.715833 | 0.9225 | 0.860833 | 0.624038 | 0.878571 | 0.621154 | 6876.51 |
| seed_11_restructure_15 | s1_audit_0.3 | 117 | 43 | 117 | 0.273504 | 0.7125 | 0.922083 | 0.859583 | 0.658173 | 0.874521 | 0.658607 | 7700.45 |
| seed_11_restructure_15 | s1_audit_0.6 | 111 | 71 | 111 | 0.261261 | 0.712917 | 0.922083 | 0.859167 | 0.6625 | 0.873921 | 0.664085 | 7813.34 |
| seed_11_clinc | always_agent | 0 | 0 | 0 | NA | 0.792917 | 0.926667 | 0.867917 | NA | NA | NA | 7721.72 |
| seed_11_clinc | s1_audit | 356 | 356 | 356 | 0.0477528 | 0.795 | 0.926667 | 0.869167 | 0.694883 | 0.839524 | 0.689622 | 7806.27 |
| seed_11_clinc | s1_refit | 50 | 0 | 50 | 0.04 | 0.792917 | 0.926667 | 0.867917 | 0.745098 | 0.867143 | 0.740316 | 7653.19 |
| seed_11_clinc | escalation_only | 356 | 0 | 356 | 0.0477528 | 0.795 | 0.926667 | 0.869167 | 0.694883 | 0.839524 | 0.689622 | 6645.33 |
| seed_11_clinc | fixed_gate | 0 | 0 | 0 | NA | 0.792917 | 0.926667 | 0.867917 | NA | NA | NA | 7803.26 |
| seed_11_clinc | fixed_gate_config_hash | 246 | 0 | 0 | NA | 0.797083 | 0.930833 | 0.872083 | 0.882114 | NA | NA | 6969.88 |
| seed_11_clinc | oracle_audit | 356 | 356 | 356 | 0.0477528 | 0.795 | 0.926667 | 0.869167 | 0.694883 | 0.839524 | 0.689622 | 7806.27 |
| seed_11_clinc | knn_cache | 3 | 3 | 0 | NA | 0.7925 | 0.926667 | 0.867917 | 0.666667 | NA | NA | 7832.32 |
| seed_11_clinc | surrogate_audit | 0 | 0 | 0 | NA | 0.792917 | 0.926667 | 0.867917 | 0.289335 | 0.634286 | 0.286944 | 7772.47 |
| seed_11_clinc | surrogate_refit | 0 | 0 | 0 | NA | 0.792917 | 0.926667 | 0.867917 | 0.29077 | 0.629048 | 0.288379 | 7770.41 |
| seed_23_control | always_agent | 0 | 0 | 0 | NA | 0.765417 | 0.917083 | 0.85625 | NA | NA | NA | 8464.33 |
| seed_23_control | s1_audit | 780 | 780 | 778 | 0.0796915 | 0.777083 | 0.9225 | 0.865833 | 0.758389 | 0.876667 | 0.753116 | 8560.84 |
| seed_23_control | s1_refit | 222 | 0 | 222 | 0.0765766 | 0.767917 | 0.919167 | 0.8575 | 0.765101 | 0.880476 | 0.760786 | 7837.97 |
| seed_23_control | escalation_only | 780 | 0 | 778 | 0.0796915 | 0.777083 | 0.9225 | 0.865833 | 0.758389 | 0.876667 | 0.753116 | 5990.81 |
| seed_23_control | fixed_gate | 894 | 0 | 0 | NA | 0.785417 | 0.924167 | 0.870833 | 0.906951 | NA | NA | 5591.83 |
| seed_23_control | fixed_gate_config_hash | 0 | 0 | 0 | NA | 0.765417 | 0.917083 | 0.85625 | NA | NA | NA | 8562.29 |
| seed_23_control | oracle_audit | 780 | 780 | 778 | 0.0796915 | 0.777083 | 0.9225 | 0.865833 | 0.758389 | 0.876667 | 0.753116 | 8560.84 |
| seed_23_control | knn_cache | 1 | 1 | 0 | NA | 0.765417 | 0.917083 | 0.855833 | 0 | NA | NA | 8572.82 |
| seed_23_control | surrogate_audit | 0 | 0 | 0 | NA | 0.765417 | 0.917083 | 0.85625 | 0.283317 | 0.631905 | 0.278523 | 8511.65 |
| seed_23_control | surrogate_refit | 0 | 0 | 0 | NA | 0.765417 | 0.917083 | 0.85625 | 0.315436 | 0.606667 | 0.310642 | 8511.5 |
| seed_23_control | s1_audit_0.1 | 780 | 85 | 778 | 0.0796915 | 0.777083 | 0.9225 | 0.865833 | 0.758389 | 0.876667 | 0.753116 | 6283.59 |
| seed_23_control | s1_audit_0.3 | 780 | 244 | 778 | 0.0796915 | 0.777083 | 0.9225 | 0.865833 | 0.758389 | 0.876667 | 0.753116 | 6798.33 |
| seed_23_control | s1_audit_0.6 | 780 | 463 | 778 | 0.0796915 | 0.777083 | 0.9225 | 0.865833 | 0.758389 | 0.876667 | 0.753116 | 7519.67 |
| seed_23_restructure_15 | always_agent | 0 | 0 | 0 | NA | 0.700417 | 0.9125 | 0.855417 | NA | NA | NA | 8295.74 |
| seed_23_restructure_15 | s1_audit | 114 | 114 | 114 | 0.289474 | 0.697917 | 0.915 | 0.85375 | 0.669223 | 0.872857 | 0.663471 | 8393.57 |
| seed_23_restructure_15 | s1_refit | 111 | 0 | 111 | 0.279279 | 0.698333 | 0.915 | 0.85375 | 0.633749 | 0.87619 | 0.627037 | 8017.81 |
| seed_23_restructure_15 | escalation_only | 809 | 0 | 807 | 0.342007 | 0.720833 | 0.920833 | 0.860833 | 0.626558 | 0.872857 | 0.619367 | 5858.19 |
| seed_23_restructure_15 | fixed_gate | 895 | 0 | 0 | NA | 0.729167 | 0.922083 | 0.87 | 0.634938 | NA | NA | 5541.19 |
| seed_23_restructure_15 | fixed_gate_config_hash | 0 | 0 | 0 | NA | 0.700417 | 0.9125 | 0.855417 | NA | NA | NA | 8394.72 |
| seed_23_restructure_15 | oracle_audit | 471 | 471 | 471 | 0.339703 | 0.710417 | 0.918333 | 0.858333 | 0.652445 | 0.86619 | 0.645733 | 8393.5 |
| seed_23_restructure_15 | knn_cache | 1 | 1 | 0 | NA | 0.700417 | 0.9125 | 0.855 | 0 | NA | NA | 8406.81 |
| seed_23_restructure_15 | surrogate_audit | 0 | 0 | 0 | NA | 0.700417 | 0.9125 | 0.855417 | 0.250719 | 0.599524 | 0.246405 | 8345.09 |
| seed_23_restructure_15 | surrogate_refit | 0 | 0 | 0 | NA | 0.700417 | 0.9125 | 0.855417 | 0.245925 | 0.604286 | 0.24209 | 8345.23 |
| seed_23_restructure_15 | s1_audit_0.1 | 224 | 23 | 224 | 0.325893 | 0.704167 | 0.915417 | 0.855417 | 0.625599 | 0.860965 | 0.620491 | 7716.5 |
| seed_23_restructure_15 | s1_audit_0.3 | 224 | 60 | 224 | 0.325893 | 0.704167 | 0.915417 | 0.855417 | 0.628955 | 0.867654 | 0.623377 | 7846.61 |
| seed_23_restructure_15 | s1_audit_0.6 | 181 | 110 | 181 | 0.298343 | 0.70375 | 0.915417 | 0.855 | 0.627517 | 0.86619 | 0.621764 | 8152.4 |
| seed_23_clinc | always_agent | 0 | 0 | 0 | NA | 0.772083 | 0.920417 | 0.860417 | NA | NA | NA | 8297.29 |
| seed_23_clinc | s1_audit | 718 | 718 | 717 | 0.100418 | 0.777917 | 0.925833 | 0.858333 | 0.690761 | 0.837619 | 0.685495 | 8392.78 |
| seed_23_clinc | s1_refit | 104 | 0 | 104 | 0.105769 | 0.77125 | 0.921667 | 0.857917 | 0.741024 | 0.877143 | 0.735759 | 8049.66 |
| seed_23_clinc | escalation_only | 718 | 0 | 717 | 0.100418 | 0.777917 | 0.925833 | 0.858333 | 0.690761 | 0.837619 | 0.685495 | 6088.74 |
| seed_23_clinc | fixed_gate | 794 | 0 | 0 | NA | 0.787083 | 0.925833 | 0.864167 | 0.858764 | NA | NA | 5819.57 |
| seed_23_clinc | fixed_gate_config_hash | 0 | 0 | 0 | NA | 0.772083 | 0.920417 | 0.860417 | NA | NA | NA | 8392.33 |
| seed_23_clinc | oracle_audit | 718 | 718 | 717 | 0.100418 | 0.777917 | 0.925833 | 0.858333 | 0.690761 | 0.837619 | 0.685495 | 8392.78 |
| seed_23_clinc | knn_cache | 1 | 1 | 0 | NA | 0.772083 | 0.920417 | 0.86 | 0 | NA | NA | 8408.55 |
| seed_23_clinc | surrogate_audit | 0 | 0 | 0 | NA | 0.772083 | 0.920417 | 0.860417 | 0.250359 | 0.608571 | 0.246529 | 8346.7 |
| seed_23_clinc | surrogate_refit | 0 | 0 | 0 | NA | 0.772083 | 0.920417 | 0.860417 | 0.276687 | 0.588095 | 0.273337 | 8346.79 |
| seed_37_control | always_agent | 0 | 0 | 0 | NA | 0.795 | 0.91875 | 0.867083 | NA | NA | NA | 7514.48 |
| seed_37_control | s1_audit | 834 | 834 | 832 | 0.102163 | 0.802917 | 0.916667 | 0.865417 | 0.76831 | 0.861429 | 0.762566 | 7602.13 |
| seed_37_control | s1_refit | 112 | 0 | 111 | 0.0990991 | 0.795417 | 0.91875 | 0.867083 | 0.774055 | 0.868571 | 0.76831 | 7296.42 |
| seed_37_control | escalation_only | 834 | 0 | 832 | 0.102163 | 0.802917 | 0.916667 | 0.865417 | 0.76831 | 0.861429 | 0.762566 | 5082.95 |
| seed_37_control | fixed_gate | 958 | 0 | 0 | NA | 0.812917 | 0.927917 | 0.880417 | 0.899371 | NA | NA | 4663.35 |
| seed_37_control | fixed_gate_config_hash | 958 | 0 | 0 | NA | 0.812917 | 0.927917 | 0.880417 | 0.899371 | NA | NA | 4663.35 |
| seed_37_control | oracle_audit | 834 | 834 | 832 | 0.102163 | 0.802917 | 0.916667 | 0.865417 | 0.76831 | 0.861429 | 0.762566 | 7602.13 |
| seed_37_control | knn_cache | 1 | 1 | 0 | NA | 0.795 | 0.918333 | 0.867083 | 0 | NA | NA | 7621.67 |
| seed_37_control | surrogate_audit | 0 | 0 | 0 | NA | 0.795 | 0.91875 | 0.867083 | 0.34179 | 0.655714 | 0.338918 | 7560.84 |
| seed_37_control | surrogate_refit | 0 | 0 | 0 | NA | 0.795 | 0.91875 | 0.867083 | 0.331259 | 0.63381 | 0.328865 | 7560.31 |
| seed_37_control | s1_audit_0.1 | 834 | 78 | 832 | 0.102163 | 0.802917 | 0.916667 | 0.865417 | 0.76831 | 0.861429 | 0.762566 | 5326.88 |
| seed_37_control | s1_audit_0.3 | 834 | 236 | 832 | 0.102163 | 0.802917 | 0.916667 | 0.865417 | 0.76831 | 0.861429 | 0.762566 | 5798.18 |
| seed_37_control | s1_audit_0.6 | 834 | 508 | 832 | 0.102163 | 0.802917 | 0.916667 | 0.865417 | 0.76831 | 0.861429 | 0.762566 | 6610.89 |
| seed_37_restructure_15 | always_agent | 0 | 0 | 0 | NA | 0.72375 | 0.91375 | 0.872083 | NA | NA | NA | 8119.07 |
| seed_37_restructure_15 | s1_audit | 148 | 148 | 148 | 0.277027 | 0.724583 | 0.913333 | 0.872083 | 0.644359 | 0.856732 | 0.643579 | 8213.45 |
| seed_37_restructure_15 | s1_refit | 121 | 0 | 121 | 0.256198 | 0.725833 | 0.914167 | 0.8725 | 0.620937 | 0.871306 | 0.617703 | 7831 |
| seed_37_restructure_15 | escalation_only | 871 | 0 | 870 | 0.386207 | 0.7425 | 0.915 | 0.866667 | 0.617591 | 0.86381 | 0.614245 | 5174.55 |
| seed_37_restructure_15 | fixed_gate | 961 | 0 | 0 | NA | 0.752083 | 0.92625 | 0.882083 | 0.601042 | NA | NA | 4849.83 |
| seed_37_restructure_15 | fixed_gate_config_hash | 67 | 0 | 0 | NA | 0.72375 | 0.91375 | 0.8725 | 0.955224 | NA | NA | 8015.63 |
| seed_37_restructure_15 | oracle_audit | 181 | 181 | 181 | 0.331492 | 0.723333 | 0.913333 | 0.87125 | 0.644359 | 0.856732 | 0.643579 | 8213.45 |
| seed_37_restructure_15 | knn_cache | 1 | 1 | 0 | NA | 0.72375 | 0.913333 | 0.872083 | 0 | NA | NA | 8229.52 |
| seed_37_restructure_15 | surrogate_audit | 0 | 0 | 0 | NA | 0.72375 | 0.91375 | 0.872083 | 0.289675 | 0.648571 | 0.287763 | 8167.78 |
| seed_37_restructure_15 | surrogate_refit | 0 | 0 | 0 | NA | 0.72375 | 0.91375 | 0.872083 | 0.271033 | 0.640952 | 0.269598 | 8167.68 |
| seed_37_restructure_15 | s1_audit_0.1 | 158 | 15 | 158 | 0.291139 | 0.725417 | 0.91375 | 0.872083 | 0.640057 | 0.858649 | 0.635402 | 7757.19 |
| seed_37_restructure_15 | s1_audit_0.3 | 212 | 69 | 212 | 0.349057 | 0.7225 | 0.913333 | 0.871667 | 0.638145 | 0.864286 | 0.633843 | 7758.92 |
| seed_37_restructure_15 | s1_audit_0.6 | 155 | 97 | 155 | 0.283871 | 0.725417 | 0.913333 | 0.872083 | 0.645793 | 0.86021 | 0.643199 | 8027.77 |
| seed_37_clinc | always_agent | 0 | 0 | 0 | NA | 0.802083 | 0.921667 | 0.867917 | NA | NA | NA | 7675.67 |
| seed_37_clinc | s1_audit | 769 | 769 | 769 | 0.157347 | 0.80875 | 0.918333 | 0.859583 | 0.683883 | 0.827619 | 0.678623 | 7767.77 |
| seed_37_clinc | s1_refit | 184 | 0 | 184 | 0.0815217 | 0.803333 | 0.921667 | 0.870833 | 0.732186 | 0.861905 | 0.727403 | 7216.62 |
| seed_37_clinc | escalation_only | 769 | 0 | 769 | 0.157347 | 0.80875 | 0.918333 | 0.859583 | 0.683883 | 0.827619 | 0.678623 | 5338.84 |
| seed_37_clinc | fixed_gate | 850 | 0 | 0 | NA | 0.8125 | 0.926667 | 0.86875 | 0.846698 | NA | NA | 5066.67 |
| seed_37_clinc | fixed_gate_config_hash | 67 | 0 | 0 | NA | 0.802083 | 0.921667 | 0.868333 | 0.955224 | NA | NA | 7567.55 |
| seed_37_clinc | oracle_audit | 769 | 769 | 769 | 0.157347 | 0.80875 | 0.918333 | 0.859583 | 0.683883 | 0.827619 | 0.678623 | 7767.77 |
| seed_37_clinc | knn_cache | 1 | 1 | 0 | NA | 0.802083 | 0.92125 | 0.867917 | 0 | NA | NA | 7785.65 |
| seed_37_clinc | surrogate_audit | 0 | 0 | 0 | NA | 0.802083 | 0.921667 | 0.867917 | 0.304161 | 0.629048 | 0.302726 | 7724.16 |
| seed_37_clinc | surrogate_refit | 0 | 0 | 0 | NA | 0.802083 | 0.921667 | 0.867917 | 0.27451 | 0.621905 | 0.272597 | 7723.88 |
- Served joint error uses only served tickets with observed teacher labels; selective missing labels can bias it. Overall agreement columns use available labels.

## Missing outputs and limitations
- Missing files: none among expected files.
- Data/completeness issues: none detected by these checks.
- Public benchmark contamination, synthetic policy/cohort markers, teacher error, adaptive temporal dependence and selectively observed labels limit interpretation. Missing or interrupted outputs cannot establish a hypothesis.
