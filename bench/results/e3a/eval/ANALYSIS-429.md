# E3a post-evaluation analysis

Generated from retained evaluation artifacts; no model calls. NA means unavailable, not zero.

## Run provenance, deviations and spend
- Run ID: evaluation; git SHA: 278d5b35e79f81860b485b10eaef1c9ff51da657; dirty: True.
- Models: `{}`.
- Frozen configuration deviations: none detected in checked fields.
- Manifest new provider spend (USD): `{"openai": 15.09260654999948, "typesafe": 1.1891068559975886}`; logical arm costs (USD): `{}`.
- Manifest notes: `["seed_37_restructure_15: 44 failed teacher calls; see collection CSV"]`.
- Recorded budget stop (bench/results/e3a/evaluation/budget_stop.json): `{"caps_usd": {"openai": 75.0, "typesafe": 5.0}, "error": "typesafe: budget reserved for unpriced call: Client error '402 Payment Required' for url 'https://api.typesafe.ai/v1/systemone'\nFor more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/402", "spent_usd": {"openai": 26.55214266999984, "typesafe": 2.8020353839984793}}`.
- Recorded budget stop (bench/results/e3a/evaluation-resumed/budget_stop.json): `{"caps_usd": {"openai": 75.0, "typesafe": 8.0}, "error": "BudgetExceeded: openai: budget reserved for unpriced call: Error code: 503 - Unable to verify model access right now. Please retry.", "spent_usd": {"openai": 35.112541169999865, "typesafe": 3.422965651997018}}`.
- Recorded budget stop (bench/results/e3a/evaluation-resumed-2/budget_stop.json): `{"caps_usd": {"openai": 75.0, "typesafe": 8.0}, "error": "BudgetExceeded: openai: budget reserved for unpriced call: Error code: 429 - You have no credits remaining. Add credits to continue using the API at https://platform.openai.com/settings/organization/billing/.", "spent_usd": {"openai": 50.205147719999346, "typesafe": 4.612072507994607}}`.
- At the TypeSafe 402 stop, the dashboard showed $4.89 billed versus approximately $2.75 settled list-price spend (about 1.78 times). After two authorized top-ups, $9.89 of balance remained on top of $4.89 already billed ($14.78 total available). The cumulative list-price proxy cap was raised to $8.00 (about $14.24 billed at the observed ratio). The previous $0.05 unpriced-call reservation is conservatively retained. This proxy cannot guarantee the actual billed cap; dashboard billing must be monitored separately.
- OpenAI 503 stop deviation: model access verification failed and interrupted evaluation. The $1.00 unpriced-call reservation is retained; it is not evidence of actual provider billing. Actual billing for the failed call is unknown.
- Logical costs can count cached calls across arms and are not provider spend. Provider dashboard reconciliation is unverified for current spend; hardware and energy are unpriced.
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
- Served joint error uses only served tickets with observed teacher labels; selective missing labels can bias it. Overall agreement columns use available labels.

## Missing outputs and limitations
- Missing files: `secondary_replay_cache.json`, `discovery_summary.csv`, `discovery.csv`, `s5-records.jsonl`, `h3.csv`, `h4.csv`, `h5_exploratory.csv`, `summary.csv`, `audit_rate_curve.csv`, `seed_11_control_s1_audit_0.1.csv`, `seed_11_control_s1_audit_0.3.csv`, `seed_11_control_s1_audit_0.6.csv`, `seed_11_restructure_15_s1_audit_0.1.csv`, `seed_11_restructure_15_s1_audit_0.3.csv`, `seed_11_restructure_15_s1_audit_0.6.csv`, `seed_11_clinc_s1_audit_0.1.csv`, `seed_11_clinc_s1_audit_0.3.csv`, `seed_11_clinc_s1_audit_0.6.csv`, `seed_23_control_s1_audit_0.1.csv`, `seed_23_control_s1_audit_0.3.csv`, `seed_23_control_s1_audit_0.6.csv`, `seed_23_restructure_15_s1_audit_0.1.csv`, `seed_23_restructure_15_s1_audit_0.3.csv`, `seed_23_restructure_15_s1_audit_0.6.csv`, `seed_23_clinc_s1_audit_0.1.csv`, `seed_23_clinc_s1_audit_0.3.csv`, `seed_23_clinc_s1_audit_0.6.csv`, `seed_37_control_s1_audit_0.1.csv`, `seed_37_control_s1_audit_0.3.csv`, `seed_37_control_s1_audit_0.6.csv`, `seed_37_restructure_15_always_agent.csv`, `seed_37_restructure_15_s1_audit.csv`, `seed_37_restructure_15_s1_refit.csv`, `seed_37_restructure_15_escalation_only.csv`, `seed_37_restructure_15_fixed_gate.csv`, `seed_37_restructure_15_fixed_gate_config_hash.csv`, `seed_37_restructure_15_oracle_audit.csv`, `seed_37_restructure_15_knn_cache.csv`, `seed_37_restructure_15_surrogate_audit.csv`, `seed_37_restructure_15_surrogate_refit.csv`, `seed_37_restructure_15_s1_audit_0.1.csv`, `seed_37_restructure_15_s1_audit_0.3.csv`, `seed_37_restructure_15_s1_audit_0.6.csv`, `seed_37_clinc_always_agent.csv`, `seed_37_clinc_s1_audit.csv`, `seed_37_clinc_s1_refit.csv`, `seed_37_clinc_escalation_only.csv`, `seed_37_clinc_fixed_gate.csv`, `seed_37_clinc_fixed_gate_config_hash.csv`, `seed_37_clinc_oracle_audit.csv`, `seed_37_clinc_knn_cache.csv`, `seed_37_clinc_surrogate_audit.csv`, `seed_37_clinc_surrogate_refit.csv`, `seed_37_clinc_s1_audit_0.1.csv`, `seed_37_clinc_s1_audit_0.3.csv`, `seed_37_clinc_s1_audit_0.6.csv`.
- Data/completeness issues: seed_37_restructure_15: manifest count missing, expected 2400; seed_37_clinc: manifest count missing, expected 2400.
- Public benchmark contamination, synthetic policy/cohort markers, teacher error, adaptive temporal dependence and selectively observed labels limit interpretation. Missing or interrupted outputs cannot establish a hypothesis.
