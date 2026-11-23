# E3a development tuning

Mode: record; parameters: `{"allow_eval": false, "alpha": 0.05, "audit_rate": 0.2, "cost_bound_percent": null, "dev_condition": ["dev_control", "dev_restructure_15"], "dev_run_id": "dev-tuning-joint", "epsilon": 0.1, "metric": "probability", "mode": "record", "n_cal": 250, "n_val": 250, "phase_limit": 1000, "refit_interval": 200, "seed": 20261122, "streams": "dev", "tau_rule": "margin", "warmup": 300, "workers": 2}`.
Costs are token-usage list-price estimates; local hardware and energy are not priced.

- dev_control, always_agent: joint accuracy 0.749 (95% Wilson 0.729-0.767), coverage 0.000, cost/ticket $0.002883, agent calls 2000.
- dev_control, escalation_only: joint accuracy 0.759 (95% Wilson 0.740-0.778), coverage 0.270, cost/ticket $0.002230, agent calls 1461.
- dev_control, fixed_gate: joint accuracy 0.758 (95% Wilson 0.739-0.776), coverage 0.262, cost/ticket $0.002254, agent calls 1477.
- dev_control, fixed_gate_config_hash: joint accuracy 0.758 (95% Wilson 0.739-0.776), coverage 0.262, cost/ticket $0.002254, agent calls 1477.
- dev_control, knn_cache: joint accuracy 0.749 (95% Wilson 0.729-0.767), coverage 0.000, cost/ticket $0.002883, agent calls 2000.
- dev_control, oracle_audit: joint accuracy 0.759 (95% Wilson 0.740-0.778), coverage 0.270, cost/ticket $0.002373, agent calls 1570.
- dev_control, s1_audit: joint accuracy 0.759 (95% Wilson 0.740-0.778), coverage 0.270, cost/ticket $0.002373, agent calls 1570.
- dev_control, s1_refit: joint accuracy 0.749 (95% Wilson 0.730-0.768), coverage 0.019, cost/ticket $0.002901, agent calls 1961.
- dev_control, surrogate_audit: joint accuracy 0.749 (95% Wilson 0.729-0.767), coverage 0.000, cost/ticket $0.002883, agent calls 2000.
- dev_control, surrogate_refit: joint accuracy 0.749 (95% Wilson 0.729-0.767), coverage 0.000, cost/ticket $0.002883, agent calls 2000.
- dev_restructure_15, always_agent: joint accuracy 0.673 (95% Wilson 0.652-0.693), coverage 0.000, cost/ticket $0.002941, agent calls 2000.
- dev_restructure_15, escalation_only: joint accuracy 0.706 (95% Wilson 0.685-0.725), coverage 0.267, cost/ticket $0.002271, agent calls 1466.
- dev_restructure_15, fixed_gate: joint accuracy 0.702 (95% Wilson 0.681-0.721), coverage 0.260, cost/ticket $0.002295, agent calls 1480.
- dev_restructure_15, fixed_gate_config_hash: joint accuracy 0.675 (95% Wilson 0.654-0.695), coverage 0.047, cost/ticket $0.002914, agent calls 1906.
- dev_restructure_15, knn_cache: joint accuracy 0.673 (95% Wilson 0.652-0.693), coverage 0.000, cost/ticket $0.002941, agent calls 2000.
- dev_restructure_15, oracle_audit: joint accuracy 0.706 (95% Wilson 0.685-0.725), coverage 0.267, cost/ticket $0.002416, agent calls 1574.
- dev_restructure_15, s1_audit: joint accuracy 0.693 (95% Wilson 0.672-0.712), coverage 0.154, cost/ticket $0.002672, agent calls 1748.
- dev_restructure_15, s1_refit: joint accuracy 0.673 (95% Wilson 0.653-0.694), coverage 0.019, cost/ticket $0.002962, agent calls 1961.
- dev_restructure_15, surrogate_audit: joint accuracy 0.673 (95% Wilson 0.652-0.693), coverage 0.000, cost/ticket $0.002941, agent calls 2000.
- dev_restructure_15, surrogate_refit: joint accuracy 0.673 (95% Wilson 0.652-0.693), coverage 0.000, cost/ticket $0.002941, agent calls 2000.

Intervals are descriptive per-arm proportions, not paired hypothesis tests.
Public-data contamination, synthetic policies and cohort marker, selective labels, teacher noise and unreconciled provider billing threaten validity.
E3a exposed the lack of a truthful meta-layer patch kind for an audit-triggered rollback; contract 2.1.0 added `rollback` as a non-breaking patch kind.
No E3 hypotheses are tested on development data.

## Joint-risk dev tuning and proposed evaluation

The prior two-question run is retained in `../dev-tuning/`; this run instead predicts
entry and learns the identity value from the arm's training traces, with unseen or tied
entries escalated. Shadow validation and audits compare entry plus identity jointly.
In the 2,000-ticket control, S1-plus-audit compiled 27.0% and achieved 75.9% joint gold
accuracy, versus 74.9% for always-agent. In the 15% shift it compiled 15.4%, with 69.3%
joint accuracy versus 67.3% for always-agent. These are descriptive, not hypothesis tests.

`promotion_grid.csv` records 500 bootstrap resamples per setting of the original 569
matched shadow observations. Among configurations whose nominal warmup and shadow
windows finish by the evaluation shift, epsilon 0.20, margin calibration and 400+400
windows had the highest observed bootstrap promotion fraction: 437/500 (87.4%; Wilson
84.2%-90.0%). Bootstrap duplicates tickets, and the chosen configuration has not been
run as a complete dev lifecycle. Missing mappings can defer promotion past the shift.

For the selected epsilon, `power.json` records a separate Bernoulli e-process simulation
using the observed conditional error and 8.6% pre-shift coverage from the epsilon 0.10
run. Even at 100% auditing, estimated detection power was 16.8% (Wilson 13.8%-20.3%),
with 416/500 misses and median 985 tickets among detections. This is extrapolation, not
measured power of the selected configuration.

At this stop OpenAI spend including pilots was $15.1003/$55, and TypeSafe was $1.8431/$5.
The reduced six-condition, three-seed evaluation is estimated at $39.8357 additional
OpenAI for 11,400 teacher samples, including a 20% margin but excluding writer calls.
The estimate assumes paired pre-shift cache hits and may exceed the remaining usable
budget after the $1 request reserve. No evaluation was run.
