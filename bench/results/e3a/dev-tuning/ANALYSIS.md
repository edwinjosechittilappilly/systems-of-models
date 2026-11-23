# E3a development tuning

Mode: record; parameters: `{"allow_eval": false, "alpha": 0.05, "audit_rate": 0.2, "cost_bound_percent": null, "epsilon": 0.1, "metric": "probability", "mode": "record", "n_cal": 250, "n_val": 250, "phase_limit": 1000, "refit_interval": 200, "seed": 20261122, "streams": "dev", "tau_rule": "margin", "warmup": 300, "workers": 2}`.
Costs are token-usage list-price estimates; local hardware and energy are not priced.

- dev_clinc, always_agent: joint accuracy 0.748 (95% Wilson 0.728-0.766), coverage 0.000, cost/ticket $0.002858, agent calls 2000.
- dev_clinc, escalation_only: joint accuracy 0.748 (95% Wilson 0.728-0.766), coverage 0.000, cost/ticket $0.002943, agent calls 2000.
- dev_clinc, fixed_gate: joint accuracy 0.758 (95% Wilson 0.739-0.777), coverage 0.230, cost/ticket $0.002325, agent calls 1540.
- dev_clinc, fixed_gate_config_hash: joint accuracy 0.750 (95% Wilson 0.730-0.768), coverage 0.047, cost/ticket $0.002803, agent calls 1906.
- dev_clinc, knn_cache: joint accuracy 0.748 (95% Wilson 0.728-0.766), coverage 0.000, cost/ticket $0.002858, agent calls 2000.
- dev_clinc, oracle_audit: joint accuracy 0.748 (95% Wilson 0.728-0.766), coverage 0.000, cost/ticket $0.002943, agent calls 2000.
- dev_clinc, s1_audit: joint accuracy 0.748 (95% Wilson 0.728-0.766), coverage 0.000, cost/ticket $0.002943, agent calls 2000.
- dev_clinc, s1_refit: joint accuracy 0.748 (95% Wilson 0.728-0.766), coverage 0.000, cost/ticket $0.002943, agent calls 2000.
- dev_clinc, surrogate_audit: joint accuracy 0.748 (95% Wilson 0.728-0.766), coverage 0.000, cost/ticket $0.002858, agent calls 2000.
- dev_clinc, surrogate_refit: joint accuracy 0.748 (95% Wilson 0.728-0.766), coverage 0.000, cost/ticket $0.002858, agent calls 2000.
- dev_control, always_agent: joint accuracy 0.749 (95% Wilson 0.729-0.767), coverage 0.000, cost/ticket $0.002883, agent calls 2000.
- dev_control, escalation_only: joint accuracy 0.749 (95% Wilson 0.729-0.767), coverage 0.000, cost/ticket $0.002965, agent calls 2000.
- dev_control, fixed_gate: joint accuracy 0.758 (95% Wilson 0.739-0.776), coverage 0.262, cost/ticket $0.002254, agent calls 1477.
- dev_control, fixed_gate_config_hash: joint accuracy 0.758 (95% Wilson 0.739-0.776), coverage 0.262, cost/ticket $0.002254, agent calls 1477.
- dev_control, knn_cache: joint accuracy 0.749 (95% Wilson 0.729-0.767), coverage 0.000, cost/ticket $0.002883, agent calls 2000.
- dev_control, oracle_audit: joint accuracy 0.749 (95% Wilson 0.729-0.767), coverage 0.000, cost/ticket $0.002965, agent calls 2000.
- dev_control, s1_audit: joint accuracy 0.749 (95% Wilson 0.729-0.767), coverage 0.000, cost/ticket $0.002965, agent calls 2000.
- dev_control, s1_refit: joint accuracy 0.749 (95% Wilson 0.729-0.767), coverage 0.000, cost/ticket $0.002967, agent calls 2000.
- dev_control, surrogate_audit: joint accuracy 0.749 (95% Wilson 0.729-0.767), coverage 0.000, cost/ticket $0.002883, agent calls 2000.
- dev_control, surrogate_refit: joint accuracy 0.749 (95% Wilson 0.729-0.767), coverage 0.000, cost/ticket $0.002883, agent calls 2000.
- dev_restructure_05, always_agent: joint accuracy 0.691 (95% Wilson 0.670-0.710), coverage 0.000, cost/ticket $0.002914, agent calls 2000.
- dev_restructure_05, escalation_only: joint accuracy 0.691 (95% Wilson 0.670-0.710), coverage 0.000, cost/ticket $0.003002, agent calls 2000.
- dev_restructure_05, fixed_gate: joint accuracy 0.717 (95% Wilson 0.697-0.736), coverage 0.261, cost/ticket $0.002269, agent calls 1478.
- dev_restructure_05, fixed_gate_config_hash: joint accuracy 0.693 (95% Wilson 0.672-0.712), coverage 0.047, cost/ticket $0.002873, agent calls 1906.
- dev_restructure_05, knn_cache: joint accuracy 0.691 (95% Wilson 0.670-0.710), coverage 0.000, cost/ticket $0.002914, agent calls 2000.
- dev_restructure_05, oracle_audit: joint accuracy 0.691 (95% Wilson 0.670-0.710), coverage 0.000, cost/ticket $0.003002, agent calls 2000.
- dev_restructure_05, s1_audit: joint accuracy 0.691 (95% Wilson 0.670-0.710), coverage 0.000, cost/ticket $0.003002, agent calls 2000.
- dev_restructure_05, s1_refit: joint accuracy 0.691 (95% Wilson 0.670-0.710), coverage 0.000, cost/ticket $0.003000, agent calls 2000.
- dev_restructure_05, surrogate_audit: joint accuracy 0.691 (95% Wilson 0.670-0.710), coverage 0.000, cost/ticket $0.002914, agent calls 2000.
- dev_restructure_05, surrogate_refit: joint accuracy 0.691 (95% Wilson 0.670-0.710), coverage 0.000, cost/ticket $0.002914, agent calls 2000.
- dev_restructure_15, always_agent: joint accuracy 0.673 (95% Wilson 0.652-0.693), coverage 0.000, cost/ticket $0.002941, agent calls 2000.
- dev_restructure_15, escalation_only: joint accuracy 0.673 (95% Wilson 0.652-0.693), coverage 0.000, cost/ticket $0.003032, agent calls 2000.
- dev_restructure_15, fixed_gate: joint accuracy 0.702 (95% Wilson 0.681-0.721), coverage 0.260, cost/ticket $0.002295, agent calls 1480.
- dev_restructure_15, fixed_gate_config_hash: joint accuracy 0.675 (95% Wilson 0.654-0.695), coverage 0.047, cost/ticket $0.002914, agent calls 1906.
- dev_restructure_15, knn_cache: joint accuracy 0.673 (95% Wilson 0.652-0.693), coverage 0.000, cost/ticket $0.002941, agent calls 2000.
- dev_restructure_15, oracle_audit: joint accuracy 0.673 (95% Wilson 0.652-0.693), coverage 0.000, cost/ticket $0.003032, agent calls 2000.
- dev_restructure_15, s1_audit: joint accuracy 0.673 (95% Wilson 0.652-0.693), coverage 0.000, cost/ticket $0.003032, agent calls 2000.
- dev_restructure_15, s1_refit: joint accuracy 0.673 (95% Wilson 0.652-0.693), coverage 0.000, cost/ticket $0.003030, agent calls 2000.
- dev_restructure_15, surrogate_audit: joint accuracy 0.673 (95% Wilson 0.652-0.693), coverage 0.000, cost/ticket $0.002941, agent calls 2000.
- dev_restructure_15, surrogate_refit: joint accuracy 0.673 (95% Wilson 0.652-0.693), coverage 0.000, cost/ticket $0.002941, agent calls 2000.
- dev_restructure_30, always_agent: joint accuracy 0.677 (95% Wilson 0.657-0.698), coverage 0.000, cost/ticket $0.002945, agent calls 2000.
- dev_restructure_30, escalation_only: joint accuracy 0.677 (95% Wilson 0.657-0.698), coverage 0.000, cost/ticket $0.003039, agent calls 2000.
- dev_restructure_30, fixed_gate: joint accuracy 0.662 (95% Wilson 0.641-0.683), coverage 0.259, cost/ticket $0.002302, agent calls 1482.
- dev_restructure_30, fixed_gate_config_hash: joint accuracy 0.679 (95% Wilson 0.659-0.700), coverage 0.047, cost/ticket $0.002922, agent calls 1906.
- dev_restructure_30, knn_cache: joint accuracy 0.677 (95% Wilson 0.657-0.698), coverage 0.000, cost/ticket $0.002945, agent calls 2000.
- dev_restructure_30, oracle_audit: joint accuracy 0.677 (95% Wilson 0.657-0.698), coverage 0.000, cost/ticket $0.003039, agent calls 2000.
- dev_restructure_30, s1_audit: joint accuracy 0.677 (95% Wilson 0.657-0.698), coverage 0.000, cost/ticket $0.003039, agent calls 2000.
- dev_restructure_30, s1_refit: joint accuracy 0.677 (95% Wilson 0.657-0.698), coverage 0.000, cost/ticket $0.003037, agent calls 2000.
- dev_restructure_30, surrogate_audit: joint accuracy 0.677 (95% Wilson 0.657-0.698), coverage 0.000, cost/ticket $0.002945, agent calls 2000.
- dev_restructure_30, surrogate_refit: joint accuracy 0.677 (95% Wilson 0.657-0.698), coverage 0.000, cost/ticket $0.002945, agent calls 2000.
- dev_visible, always_agent: joint accuracy 0.488 (95% Wilson 0.467-0.510), coverage 0.000, cost/ticket $0.003057, agent calls 2000.
- dev_visible, fixed_gate_config_hash: joint accuracy 0.490 (95% Wilson 0.469-0.512), coverage 0.047, cost/ticket $0.003030, agent calls 1906.

Intervals are descriptive per-arm proportions, not paired hypothesis tests.
Public-data contamination, synthetic policies and cohort marker, selective labels, teacher noise and unreconciled provider billing threaten validity.
E3a exposed the lack of a truthful meta-layer patch kind for an audit-triggered rollback; contract 2.1.0 added `rollback` as a non-breaking patch kind.
No E3 hypotheses are tested on development data.

## Diagnostic: initial independent-question design

This run uses the original two-S1-question lifecycle; it is diagnostic, not the revised
joint-monitored lifecycle. The miner accepted the identity branch on the development
sample despite the policy's identity field being a deterministic function of the entry.
Across 972 routed pre-control teacher traces, the teacher followed that field in 946
(97.3%); 26 minority deviations appeared in 21 of 77 entry groups.

The cache-based first-generation shadow reconstruction joins 569 D1 and 250 D2
observations; 373 decision observations were ambiguous or missing and excluded, so these
results may be selected. D1 at top-probability 0.95 selected 291/569 observations and
disagreed with the teacher on 12 (4.12%; one-sided 98.75% Clopper-Pearson upper bound
7.55%). For D2, 145/250 agreed with the teacher, whereas flipping the answer would agree
on 105/250; inversion is not an improvement. At threshold 0.85, D2 disagreement was
20/54 (37.0%; upper bound 53.2%).

`shadow_risk_coverage.csv` reports every threshold and the actual selected-sample bound.
The 300/500/1,000-window bounds and pass fractions are bootstrap projections from these
same observations (500 resamples), not independent validation windows or full
calibration-plus-validation promotion probabilities. In particular, the 1,000-window
results reuse tickets and may be optimistic. The matching PDF/PNG plots show selective
error and projected bounds. Both the original two-question experiment and the separate
joint-monitored rerun are retained for provenance.
