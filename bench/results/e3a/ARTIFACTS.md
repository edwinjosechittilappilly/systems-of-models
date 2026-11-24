# E3a full evaluation artifacts

`eval-full.tar.gz` is a local generated archive of the complete `evaluation-resumed-3` directory. It is ignored by Git and must be transferred separately.

- SHA-256: `0a469a864c2f6760e540338c066c2a3f3eb837ffc15f62bfbf5448d5f54e1e2d`
- Size: 49,646,634 bytes
- Regular files: 177

The archive uses sorted paths, normalized ownership and timestamps, and a gzip timestamp of zero.

## Safe restore

From the repository root, extract into a newly created temporary directory rather than over existing raw data:

```sh
archive="$PWD/bench/results/e3a/eval-full.tar.gz"
restore_dir="$(mktemp -d)"
tar -xzf "$archive" -C "$restore_dir"
printf 'Restored to %s/evaluation-resumed-3\n' "$restore_dir"
```

## Development artifact restoration

The development files too large for the repository are stored as deterministic
gzip byte shards under `bench/results/e3a/dev-compressed/`. From the repository
root, restore their original paths with `uv run python -m bench.e3a.dev_artifacts restore`.
The restoration refuses to overwrite existing files and verifies the recorded SHA-256
for each reconstructed file. The evaluation archive above is unchanged.

## Complete file list

Paths are relative to the archive root:

```text
evaluation-resumed-3/ANALYSIS.md
evaluation-resumed-3/audit_rate_curve.csv
evaluation-resumed-3/discovery.csv
evaluation-resumed-3/discovery_summary.csv
evaluation-resumed-3/h3.csv
evaluation-resumed-3/h4.csv
evaluation-resumed-3/h5_exploratory.csv
evaluation-resumed-3/manifest.json
evaluation-resumed-3/meta-records.jsonl
evaluation-resumed-3/s5-records.jsonl
evaluation-resumed-3/secondary_replay_cache.json
evaluation-resumed-3/seed_11_clinc/cost.pdf
evaluation-resumed-3/seed_11_clinc/cost.png
evaluation-resumed-3/seed_11_clinc/s4-traces.jsonl.gz
evaluation-resumed-3/seed_11_clinc/trajectories.pdf
evaluation-resumed-3/seed_11_clinc/trajectories.png
evaluation-resumed-3/seed_11_clinc_always_agent.csv
evaluation-resumed-3/seed_11_clinc_escalation_only.csv
evaluation-resumed-3/seed_11_clinc_fixed_gate.csv
evaluation-resumed-3/seed_11_clinc_fixed_gate_config_hash.csv
evaluation-resumed-3/seed_11_clinc_knn_cache.csv
evaluation-resumed-3/seed_11_clinc_oracle_audit.csv
evaluation-resumed-3/seed_11_clinc_s1_audit.csv
evaluation-resumed-3/seed_11_clinc_s1_refit.csv
evaluation-resumed-3/seed_11_clinc_summary.csv
evaluation-resumed-3/seed_11_clinc_surrogate_audit.csv
evaluation-resumed-3/seed_11_clinc_surrogate_refit.csv
evaluation-resumed-3/seed_11_control/cost.pdf
evaluation-resumed-3/seed_11_control/cost.png
evaluation-resumed-3/seed_11_control/s4-traces.jsonl.gz
evaluation-resumed-3/seed_11_control/trajectories.pdf
evaluation-resumed-3/seed_11_control/trajectories.png
evaluation-resumed-3/seed_11_control_always_agent.csv
evaluation-resumed-3/seed_11_control_escalation_only.csv
evaluation-resumed-3/seed_11_control_fixed_gate.csv
evaluation-resumed-3/seed_11_control_fixed_gate_config_hash.csv
evaluation-resumed-3/seed_11_control_knn_cache.csv
evaluation-resumed-3/seed_11_control_oracle_audit.csv
evaluation-resumed-3/seed_11_control_s1_audit.csv
evaluation-resumed-3/seed_11_control_s1_audit_0.1.csv
evaluation-resumed-3/seed_11_control_s1_audit_0.3.csv
evaluation-resumed-3/seed_11_control_s1_audit_0.6.csv
evaluation-resumed-3/seed_11_control_s1_refit.csv
evaluation-resumed-3/seed_11_control_summary.csv
evaluation-resumed-3/seed_11_control_surrogate_audit.csv
evaluation-resumed-3/seed_11_control_surrogate_refit.csv
evaluation-resumed-3/seed_11_control_teacher_variance.csv
evaluation-resumed-3/seed_11_restructure_15/cost.pdf
evaluation-resumed-3/seed_11_restructure_15/cost.png
evaluation-resumed-3/seed_11_restructure_15/s4-traces.jsonl.gz
evaluation-resumed-3/seed_11_restructure_15/trajectories.pdf
evaluation-resumed-3/seed_11_restructure_15/trajectories.png
evaluation-resumed-3/seed_11_restructure_15_always_agent.csv
evaluation-resumed-3/seed_11_restructure_15_escalation_only.csv
evaluation-resumed-3/seed_11_restructure_15_fixed_gate.csv
evaluation-resumed-3/seed_11_restructure_15_fixed_gate_config_hash.csv
evaluation-resumed-3/seed_11_restructure_15_knn_cache.csv
evaluation-resumed-3/seed_11_restructure_15_oracle_audit.csv
evaluation-resumed-3/seed_11_restructure_15_s1_audit.csv
evaluation-resumed-3/seed_11_restructure_15_s1_audit_0.1.csv
evaluation-resumed-3/seed_11_restructure_15_s1_audit_0.3.csv
evaluation-resumed-3/seed_11_restructure_15_s1_audit_0.6.csv
evaluation-resumed-3/seed_11_restructure_15_s1_refit.csv
evaluation-resumed-3/seed_11_restructure_15_summary.csv
evaluation-resumed-3/seed_11_restructure_15_surrogate_audit.csv
evaluation-resumed-3/seed_11_restructure_15_surrogate_refit.csv
evaluation-resumed-3/seed_23_clinc/cost.pdf
evaluation-resumed-3/seed_23_clinc/cost.png
evaluation-resumed-3/seed_23_clinc/s4-traces.jsonl.gz
evaluation-resumed-3/seed_23_clinc/trajectories.pdf
evaluation-resumed-3/seed_23_clinc/trajectories.png
evaluation-resumed-3/seed_23_clinc_always_agent.csv
evaluation-resumed-3/seed_23_clinc_escalation_only.csv
evaluation-resumed-3/seed_23_clinc_fixed_gate.csv
evaluation-resumed-3/seed_23_clinc_fixed_gate_config_hash.csv
evaluation-resumed-3/seed_23_clinc_knn_cache.csv
evaluation-resumed-3/seed_23_clinc_oracle_audit.csv
evaluation-resumed-3/seed_23_clinc_s1_audit.csv
evaluation-resumed-3/seed_23_clinc_s1_refit.csv
evaluation-resumed-3/seed_23_clinc_summary.csv
evaluation-resumed-3/seed_23_clinc_surrogate_audit.csv
evaluation-resumed-3/seed_23_clinc_surrogate_refit.csv
evaluation-resumed-3/seed_23_control/cost.pdf
evaluation-resumed-3/seed_23_control/cost.png
evaluation-resumed-3/seed_23_control/s4-traces.jsonl.gz
evaluation-resumed-3/seed_23_control/trajectories.pdf
evaluation-resumed-3/seed_23_control/trajectories.png
evaluation-resumed-3/seed_23_control_always_agent.csv
evaluation-resumed-3/seed_23_control_escalation_only.csv
evaluation-resumed-3/seed_23_control_fixed_gate.csv
evaluation-resumed-3/seed_23_control_fixed_gate_config_hash.csv
evaluation-resumed-3/seed_23_control_knn_cache.csv
evaluation-resumed-3/seed_23_control_oracle_audit.csv
evaluation-resumed-3/seed_23_control_s1_audit.csv
evaluation-resumed-3/seed_23_control_s1_audit_0.1.csv
evaluation-resumed-3/seed_23_control_s1_audit_0.3.csv
evaluation-resumed-3/seed_23_control_s1_audit_0.6.csv
evaluation-resumed-3/seed_23_control_s1_refit.csv
evaluation-resumed-3/seed_23_control_summary.csv
evaluation-resumed-3/seed_23_control_surrogate_audit.csv
evaluation-resumed-3/seed_23_control_surrogate_refit.csv
evaluation-resumed-3/seed_23_control_teacher_variance.csv
evaluation-resumed-3/seed_23_restructure_15/cost.pdf
evaluation-resumed-3/seed_23_restructure_15/cost.png
evaluation-resumed-3/seed_23_restructure_15/s4-traces.jsonl.gz
evaluation-resumed-3/seed_23_restructure_15/trajectories.pdf
evaluation-resumed-3/seed_23_restructure_15/trajectories.png
evaluation-resumed-3/seed_23_restructure_15_always_agent.csv
evaluation-resumed-3/seed_23_restructure_15_escalation_only.csv
evaluation-resumed-3/seed_23_restructure_15_fixed_gate.csv
evaluation-resumed-3/seed_23_restructure_15_fixed_gate_config_hash.csv
evaluation-resumed-3/seed_23_restructure_15_knn_cache.csv
evaluation-resumed-3/seed_23_restructure_15_oracle_audit.csv
evaluation-resumed-3/seed_23_restructure_15_s1_audit.csv
evaluation-resumed-3/seed_23_restructure_15_s1_audit_0.1.csv
evaluation-resumed-3/seed_23_restructure_15_s1_audit_0.3.csv
evaluation-resumed-3/seed_23_restructure_15_s1_audit_0.6.csv
evaluation-resumed-3/seed_23_restructure_15_s1_refit.csv
evaluation-resumed-3/seed_23_restructure_15_summary.csv
evaluation-resumed-3/seed_23_restructure_15_surrogate_audit.csv
evaluation-resumed-3/seed_23_restructure_15_surrogate_refit.csv
evaluation-resumed-3/seed_37_clinc/cost.pdf
evaluation-resumed-3/seed_37_clinc/cost.png
evaluation-resumed-3/seed_37_clinc/s4-traces.jsonl.gz
evaluation-resumed-3/seed_37_clinc/trajectories.pdf
evaluation-resumed-3/seed_37_clinc/trajectories.png
evaluation-resumed-3/seed_37_clinc_always_agent.csv
evaluation-resumed-3/seed_37_clinc_escalation_only.csv
evaluation-resumed-3/seed_37_clinc_fixed_gate.csv
evaluation-resumed-3/seed_37_clinc_fixed_gate_config_hash.csv
evaluation-resumed-3/seed_37_clinc_knn_cache.csv
evaluation-resumed-3/seed_37_clinc_oracle_audit.csv
evaluation-resumed-3/seed_37_clinc_s1_audit.csv
evaluation-resumed-3/seed_37_clinc_s1_refit.csv
evaluation-resumed-3/seed_37_clinc_summary.csv
evaluation-resumed-3/seed_37_clinc_surrogate_audit.csv
evaluation-resumed-3/seed_37_clinc_surrogate_refit.csv
evaluation-resumed-3/seed_37_control/cost.pdf
evaluation-resumed-3/seed_37_control/cost.png
evaluation-resumed-3/seed_37_control/s4-traces.jsonl.gz
evaluation-resumed-3/seed_37_control/trajectories.pdf
evaluation-resumed-3/seed_37_control/trajectories.png
evaluation-resumed-3/seed_37_control_always_agent.csv
evaluation-resumed-3/seed_37_control_escalation_only.csv
evaluation-resumed-3/seed_37_control_fixed_gate.csv
evaluation-resumed-3/seed_37_control_fixed_gate_config_hash.csv
evaluation-resumed-3/seed_37_control_knn_cache.csv
evaluation-resumed-3/seed_37_control_oracle_audit.csv
evaluation-resumed-3/seed_37_control_s1_audit.csv
evaluation-resumed-3/seed_37_control_s1_audit_0.1.csv
evaluation-resumed-3/seed_37_control_s1_audit_0.3.csv
evaluation-resumed-3/seed_37_control_s1_audit_0.6.csv
evaluation-resumed-3/seed_37_control_s1_refit.csv
evaluation-resumed-3/seed_37_control_summary.csv
evaluation-resumed-3/seed_37_control_surrogate_audit.csv
evaluation-resumed-3/seed_37_control_surrogate_refit.csv
evaluation-resumed-3/seed_37_control_teacher_variance.csv
evaluation-resumed-3/seed_37_restructure_15/cost.pdf
evaluation-resumed-3/seed_37_restructure_15/cost.png
evaluation-resumed-3/seed_37_restructure_15/s4-traces.jsonl.gz
evaluation-resumed-3/seed_37_restructure_15/trajectories.pdf
evaluation-resumed-3/seed_37_restructure_15/trajectories.png
evaluation-resumed-3/seed_37_restructure_15_always_agent.csv
evaluation-resumed-3/seed_37_restructure_15_escalation_only.csv
evaluation-resumed-3/seed_37_restructure_15_fixed_gate.csv
evaluation-resumed-3/seed_37_restructure_15_fixed_gate_config_hash.csv
evaluation-resumed-3/seed_37_restructure_15_knn_cache.csv
evaluation-resumed-3/seed_37_restructure_15_oracle_audit.csv
evaluation-resumed-3/seed_37_restructure_15_s1_audit.csv
evaluation-resumed-3/seed_37_restructure_15_s1_audit_0.1.csv
evaluation-resumed-3/seed_37_restructure_15_s1_audit_0.3.csv
evaluation-resumed-3/seed_37_restructure_15_s1_audit_0.6.csv
evaluation-resumed-3/seed_37_restructure_15_s1_refit.csv
evaluation-resumed-3/seed_37_restructure_15_summary.csv
evaluation-resumed-3/seed_37_restructure_15_surrogate_audit.csv
evaluation-resumed-3/seed_37_restructure_15_surrogate_refit.csv
evaluation-resumed-3/summary.csv
```
