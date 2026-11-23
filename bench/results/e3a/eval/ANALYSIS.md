# E3a post-evaluation analysis

Generated from retained evaluation artifacts; no model calls. NA means unavailable, not zero.

## Run provenance, deviations and spend
- Manifest unavailable; frozen configuration, run completion and spend cannot be verified.
- Recorded budget stop: `{"caps_usd": {"openai": 75.0, "typesafe": 5.0}, "error": "typesafe: budget reserved for unpriced call: Client error '402 Payment Required' for url 'https://api.typesafe.ai/v1/systemone'\nFor more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/402", "spent_usd": {"openai": 26.55214266999984, "typesafe": 2.8020353839984793}}`.
- Logical costs can count cached calls across arms and are not provider spend. Provider dashboard reconciliation is unverified; hardware and energy are unpriced.
- Pacing deviation: the runner reserves at most 400,000 estimated tokens per rolling minute, but does not record individual pacing sleeps; actual waits and any backoff cannot be audited from the retained artifacts.

## H1 — discovery
Candidate-level precision and recall are per mining report; repeated reports are not independent experiments.
Verdict: not evaluable; discovery summaries unavailable or empty.
The preregistration reports a development identity functional-dependency false negative; it was not corrected. Candidate-level results above are evaluation observations, not proof of independence.

## H2 — promoted-generation risk control
- Verdict: not evaluable; promotion records unavailable or invalid.
- No promotion is not zero-error success. Validation controls teacher disagreement under its assumptions, not gold error or post-shift risk.

## H3 — control noninferiority
- Verdict: not evaluable; valid h3.csv unavailable.

## H4 — 15% restructure
- Verdict: not evaluable; both valid Holm-family comparisons are required.

## H5 — exploratory equal-training-label comparison
- Verdict: not evaluable; exploratory comparison unavailable.

## Per-stream outcomes and audit-rate replay

## Ticket-level agreement and completeness
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
- Served joint error uses only served tickets with observed teacher labels; selective missing labels can bias it. Overall agreement columns use available labels.

## Missing outputs and limitations
- Missing files: `manifest.json`, `secondary_replay_cache.json`, `discovery_summary.csv`, `discovery.csv`, `s5-records.jsonl`, `h3.csv`, `h4.csv`, `h5_exploratory.csv`, `summary.csv`, `audit_rate_curve.csv`, `seed_11_control_s1_audit_0.1.csv`, `seed_11_control_s1_audit_0.3.csv`, `seed_11_control_s1_audit_0.6.csv`, `seed_11_restructure_15_s1_audit_0.1.csv`, `seed_11_restructure_15_s1_audit_0.3.csv`, `seed_11_restructure_15_s1_audit_0.6.csv`, `seed_11_clinc_always_agent.csv`, `seed_11_clinc_s1_audit.csv`, `seed_11_clinc_s1_refit.csv`, `seed_11_clinc_escalation_only.csv`, `seed_11_clinc_fixed_gate.csv`, `seed_11_clinc_fixed_gate_config_hash.csv`, `seed_11_clinc_oracle_audit.csv`, `seed_11_clinc_knn_cache.csv`, `seed_11_clinc_surrogate_audit.csv`, `seed_11_clinc_surrogate_refit.csv`, `seed_11_clinc_s1_audit_0.1.csv`, `seed_11_clinc_s1_audit_0.3.csv`, `seed_11_clinc_s1_audit_0.6.csv`, `seed_23_control_always_agent.csv`, `seed_23_control_s1_audit.csv`, `seed_23_control_s1_refit.csv`, `seed_23_control_escalation_only.csv`, `seed_23_control_fixed_gate.csv`, `seed_23_control_fixed_gate_config_hash.csv`, `seed_23_control_oracle_audit.csv`, `seed_23_control_knn_cache.csv`, `seed_23_control_surrogate_audit.csv`, `seed_23_control_surrogate_refit.csv`, `seed_23_control_s1_audit_0.1.csv`, `seed_23_control_s1_audit_0.3.csv`, `seed_23_control_s1_audit_0.6.csv`, `seed_23_restructure_15_always_agent.csv`, `seed_23_restructure_15_s1_audit.csv`, `seed_23_restructure_15_s1_refit.csv`, `seed_23_restructure_15_escalation_only.csv`, `seed_23_restructure_15_fixed_gate.csv`, `seed_23_restructure_15_fixed_gate_config_hash.csv`, `seed_23_restructure_15_oracle_audit.csv`, `seed_23_restructure_15_knn_cache.csv`, `seed_23_restructure_15_surrogate_audit.csv`, `seed_23_restructure_15_surrogate_refit.csv`, `seed_23_restructure_15_s1_audit_0.1.csv`, `seed_23_restructure_15_s1_audit_0.3.csv`, `seed_23_restructure_15_s1_audit_0.6.csv`, `seed_23_clinc_always_agent.csv`, `seed_23_clinc_s1_audit.csv`, `seed_23_clinc_s1_refit.csv`, `seed_23_clinc_escalation_only.csv`, `seed_23_clinc_fixed_gate.csv`, `seed_23_clinc_fixed_gate_config_hash.csv`, `seed_23_clinc_oracle_audit.csv`, `seed_23_clinc_knn_cache.csv`, `seed_23_clinc_surrogate_audit.csv`, `seed_23_clinc_surrogate_refit.csv`, `seed_23_clinc_s1_audit_0.1.csv`, `seed_23_clinc_s1_audit_0.3.csv`, `seed_23_clinc_s1_audit_0.6.csv`, `seed_37_control_always_agent.csv`, `seed_37_control_s1_audit.csv`, `seed_37_control_s1_refit.csv`, `seed_37_control_escalation_only.csv`, `seed_37_control_fixed_gate.csv`, `seed_37_control_fixed_gate_config_hash.csv`, `seed_37_control_oracle_audit.csv`, `seed_37_control_knn_cache.csv`, `seed_37_control_surrogate_audit.csv`, `seed_37_control_surrogate_refit.csv`, `seed_37_control_s1_audit_0.1.csv`, `seed_37_control_s1_audit_0.3.csv`, `seed_37_control_s1_audit_0.6.csv`, `seed_37_restructure_15_always_agent.csv`, `seed_37_restructure_15_s1_audit.csv`, `seed_37_restructure_15_s1_refit.csv`, `seed_37_restructure_15_escalation_only.csv`, `seed_37_restructure_15_fixed_gate.csv`, `seed_37_restructure_15_fixed_gate_config_hash.csv`, `seed_37_restructure_15_oracle_audit.csv`, `seed_37_restructure_15_knn_cache.csv`, `seed_37_restructure_15_surrogate_audit.csv`, `seed_37_restructure_15_surrogate_refit.csv`, `seed_37_restructure_15_s1_audit_0.1.csv`, `seed_37_restructure_15_s1_audit_0.3.csv`, `seed_37_restructure_15_s1_audit_0.6.csv`, `seed_37_clinc_always_agent.csv`, `seed_37_clinc_s1_audit.csv`, `seed_37_clinc_s1_refit.csv`, `seed_37_clinc_escalation_only.csv`, `seed_37_clinc_fixed_gate.csv`, `seed_37_clinc_fixed_gate_config_hash.csv`, `seed_37_clinc_oracle_audit.csv`, `seed_37_clinc_knn_cache.csv`, `seed_37_clinc_surrogate_audit.csv`, `seed_37_clinc_surrogate_refit.csv`, `seed_37_clinc_s1_audit_0.1.csv`, `seed_37_clinc_s1_audit_0.3.csv`, `seed_37_clinc_s1_audit_0.6.csv`.
- Data/completeness issues: none detected by these checks.
- Public benchmark contamination, synthetic policy/cohort markers, teacher error, adaptive temporal dependence and selectively observed labels limit interpretation. Missing or interrupted outputs cannot establish a hypothesis.
