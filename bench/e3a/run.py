"""Run the E3a lifecycle simulator; cache-only replay is the default.

Development tuning never consumes the evaluation streams. Evaluation requires
an explicit opt-in after the preregistration has been reviewed and tagged.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
from bench.common.cache import JsonCache
from bench.common.manifest import Manifest
from bench.common.stats import wilson
from bench.e3a.collect import DEV_STREAMS, collect, items_for_stream, previous_openai_spend
from bench.e3a.local_models import EMBEDDING_NAMESPACE, CachedEmbedder
from bench.e3a.metrics import summarize_streams
from bench.e3a.providers import E3aProviders
from bench.e3a.spend import JournaledBudget
from bench.e3a.variance import teacher_variance

ROOT = Path(__file__).resolve().parents[1]
EVAL_STREAMS = tuple(
    f"seed_{seed}_{kind}" for seed in (11, 23, 37) for kind in ("control", "restructure_15", "restructure_30", "clinc")
)


def always_agent(items: list[dict[str, Any]], stream: str, shift_at: int | None) -> list[dict[str, Any]]:
    """Book the paired teacher run as an actual call on every reference ticket."""
    rows = []
    for item in items:
        teacher, gold = item["teacher"], item["gold"]
        route = teacher.route or {}
        department = route.get("department") == gold["department"]
        priority = route.get("priority") == gold["priority"]
        identity = teacher.verified == gold["identity_check"]
        cost = teacher.envelope.cost.amount
        if cost is None:
            raise RuntimeError("unpriced teacher call")
        rows.append(
            {
                "stream": stream,
                "ticket_index": item["index"],
                "shift_at": shift_at,
                "arm": "always_agent",
                "served_by": "agent",
                "gold_department_correct": department,
                "gold_priority_correct": priority,
                "gold_identity_correct": identity,
                "gold_joint_correct": department and priority and identity,
                "teacher_agreement": bool(teacher.route),
                "cost_usd": cost,
                "agent_cost_usd": cost,
                "s1_cost_usd": 0.0,
                "shadow_cost_usd": 0.0,
                "audit_cost_usd": 0.0,
                "writer_cost_usd": 0.0,
                "mining_cost_usd": 0.0,
                "embedding_cost_usd": 0.0,
                "route": route,
                "verified": teacher.verified,
                "agent_calls": 1,
                "latency_ms": teacher.envelope.latency_ms,
                "promoted": False,
                "demoted": False,
                "audited": False,
            }
        )
    return rows


def plot_results(rows: pd.DataFrame, summary: pd.DataFrame, directory: Path) -> None:
    """Plot only observed data, keeping every arm visible."""
    plt.style.use(ROOT / "ieee.mplstyle")
    fig, axes = plt.subplots(1, 2, figsize=(7, 2.8))
    for arm, part in rows.groupby("arm", sort=True):
        part = part.sort_values("ticket_index")
        axes[0].plot(
            part["ticket_index"],
            part["gold_joint_correct"].astype(float).rolling(100, min_periods=100).mean(),
            label=arm,
        )
        axes[1].plot(
            part["ticket_index"],
            part["served_by"].ne("agent").astype(float).rolling(100, min_periods=100).mean(),
            label=arm,
        )
    shifts = rows["shift_at"].dropna().unique()
    if len(shifts) == 1:
        for ax in axes:
            ax.axvline(shifts[0], color="black", linestyle="--", linewidth=0.8)
    axes[0].set_ylabel("Rolling 100 joint accuracy")
    axes[1].set_ylabel("Rolling 100 compiled coverage")
    for ax in axes:
        ax.set_xlabel("Ticket index")
        ax.set_ylim(0, 1)
    axes[1].legend(fontsize=4, loc="best")
    for ext in ("pdf", "png"):
        fig.savefig(directory / f"trajectories.{ext}")
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 3))
    ordered = summary.sort_values("arm")
    ax.bar(ordered["arm"], ordered["cost_per_ticket_usd"])
    ax.tick_params(axis="x", labelrotation=65, labelsize=5)
    ax.set_ylabel("Usage-weighted USD / ticket")
    for ext in ("pdf", "png"):
        fig.savefig(directory / f"cost.{ext}")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--streams", choices=("dev", "eval"), default="dev")
    parser.add_argument("--mode", choices=("record", "replay"), default="replay")
    parser.add_argument("--allow-eval", action="store_true", help="requires prior preregistration approval")
    parser.add_argument(
        "--phase-limit",
        type=int,
        default=None,
        help="dev tuning: first N tickets from each phase; omitted means the complete stream",
    )
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--warmup", type=int, default=300)
    parser.add_argument("--n-cal", type=int, default=250)
    parser.add_argument("--n-val", type=int, default=250)
    parser.add_argument("--epsilon", type=float, default=0.10)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--audit-rate", type=float, default=0.2)
    parser.add_argument("--refit-interval", type=int, default=200)
    parser.add_argument(
        "--metric",
        choices=("probability", "confidence"),
        default=None,
        help="dev defaults to probability; evaluation requires the E2-selected signal",
    )
    parser.add_argument("--tau-rule", choices=("upper_bound", "margin"), default="margin")
    parser.add_argument("--seed", type=int, default=20261122)
    parser.add_argument(
        "--cost-bound-percent", type=float, default=None, help="evaluation requires the preregistered H3 cost bound"
    )
    args = parser.parse_args()
    if args.streams == "eval" and not args.allow_eval:
        parser.error("evaluation requires preregistration approval and --allow-eval")
    if args.streams == "eval" and args.phase_limit is not None:
        parser.error("evaluation streams must not be truncated")
    if args.streams == "eval" and (args.cost_bound_percent is None or args.cost_bound_percent <= 0):
        parser.error("evaluation requires the preregistered --cost-bound-percent")
    if args.streams == "eval" and args.metric is None:
        parser.error("evaluation requires the E2-selected --metric")
    if args.metric is None:
        args.metric = "probability"
    from bench.e3a.baselines import run_baseline
    from bench.e3a.lifecycle_runner import run_lifecycle

    names = DEV_STREAMS if args.streams == "dev" else EVAL_STREAMS
    run_id = "dev-tuning" if args.streams == "dev" else "evaluation"
    directory = ROOT / "results" / "e3a" / run_id
    directory.mkdir(parents=True, exist_ok=True)
    config = vars(args).copy()
    manifest = Manifest("e3a", run_id, config)
    budget = JournaledBudget({"openai": 55.0, "typesafe": 5.0}, initial={"openai": previous_openai_spend()})
    providers = E3aProviders(args.mode, budget)
    embedder = CachedEmbedder(JsonCache(EMBEDDING_NAMESPACE, mode=args.mode))
    mining_timing = JsonCache("e3a_mining_timing_v1", mode=args.mode)
    all_rows: list[dict[str, Any]] = []
    s5_records: list[dict[str, Any]] = []
    meta_records: list[dict[str, Any]] = []
    discovery: list[dict[str, Any]] = []
    variance_overhead = 0.0
    for name in names:
        path = ROOT / "tasks" / "streams" / f"{name}.csv"
        manifest.data[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        frame = pd.read_csv(path)
        items, shift = items_for_stream(frame, phase_limit=args.phase_limit)
        completed = collect(items, providers, workers=args.workers)
        errors = [row for row in completed if row["status"] == "error"]
        if errors:
            pd.DataFrame(completed).to_csv(directory / f"{name}_collection.csv", index=False)
            manifest.notes.append(f"{name}: {len(errors)} failed teacher calls; see collection CSV")
            manifest.new_spend_usd = budget.new_spend()
            manifest.write()
            raise RuntimeError(manifest.notes[-1])
        if args.streams == "eval" and name.endswith("_control"):
            variance_rows, overhead = teacher_variance(items, providers, seed=args.seed, size=100, workers=args.workers)
            pd.DataFrame(variance_rows).to_csv(directory / f"{name}_teacher_variance.csv", index=False)
            variance_overhead += overhead
        shift_at = None if name.endswith("_control") else shift
        rows = always_agent(items, name, shift_at)
        settings = {
            "warmup": args.warmup,
            "n_cal": args.n_cal,
            "n_val": args.n_val,
            "epsilon": args.epsilon,
            "alpha": args.alpha,
            "audit_rate": args.audit_rate,
            "refit_interval": args.refit_interval,
            "metric": args.metric,
            "tau_rule": args.tau_rule,
            "seed": args.seed,
            "embedder": embedder,
            "min_support": 5,
            "diagnostics": discovery,
            "stream": name,
            "s5_records": s5_records,
            "meta_records": meta_records,
            "timing_cache": mining_timing,
        }
        for arm, arm_rows in run_lifecycle(items, providers, settings).items():
            for row in arm_rows:
                row.update(stream=name, shift_at=shift_at, arm=arm)
            rows.extend(arm_rows)
        for arm in ("fixed_gate", "fixed_gate_config_hash", "knn_cache"):
            rows.extend(
                run_baseline(
                    items,
                    providers,
                    arm=arm,
                    stream=name,
                    shift_at=shift_at,
                    warmup=args.warmup,
                    n_cal=args.n_cal,
                    n_val=args.n_val,
                    epsilon=args.epsilon,
                    alpha=args.alpha,
                    audit_rate=args.audit_rate,
                    seed=args.seed,
                    embedder=embedder,
                    tau_rule=args.tau_rule,
                )
            )
        # Paired teacher outcomes are used only after routing for analysis, not
        # for training, promotion, auditing, or refitting.
        by_index = {item["index"]: item for item in items}
        for row in rows:
            item = by_index[row["ticket_index"]]
            teacher, route = item["teacher"], row.get("route") or {}
            row["teacher_agreement"] = (
                (
                    route.get("department") == teacher.route.get("department")
                    and route.get("priority") == teacher.route.get("priority")
                    and row.get("verified") == teacher.verified
                )
                if teacher.route
                else None
            )
            predicted = row.get("predicted_entry", row.get("prediction"))
            teacher_entry = None
            for event in teacher.events:
                if event["tool"] == "route_ticket":
                    break
                if event["tool"] == "get_policy":
                    teacher_entry = event["entry_id"]
            row["d1_teacher_agreement"] = (
                predicted == teacher_entry if predicted is not None and teacher_entry is not None else None
            )
            for part in ("s1", "agent", "shadow", "audit", "writer", "mining", "embedding"):
                old_name, new_name = f"cost_{part}", f"{part}_cost_usd"
                if old_name in row:
                    row[new_name] = row.pop(old_name)
        table = pd.DataFrame(rows)
        for arm, arm_rows in table.groupby("arm", sort=True):
            arm_rows.to_csv(directory / f"{name}_{arm}.csv", index=False)
        summary = summarize_streams(table)
        summary.to_csv(directory / f"{name}_summary.csv", index=False)
        per_stream = directory / name
        per_stream.mkdir(exist_ok=True)
        plot_results(table, summary, per_stream)
        with gzip.open(per_stream / "s4-traces.jsonl.gz", "wt", encoding="utf-8") as handle:
            for item in items:
                teacher = item["teacher"]
                handle.write(json.dumps({"kind": "envelope", "value": teacher.envelope.to_dict()}) + "\n")
                for step in teacher.trace.steps:
                    handle.write(
                        json.dumps(
                            {
                                "kind": "agent_step",
                                "trace_id": teacher.trace.trace_id,
                                "input": teacher.trace.input,
                                "tool": step.tool,
                                "arguments": step.arguments,
                                "result": step.result,
                            }
                        )
                        + "\n"
                    )
        all_rows.extend(rows)
        manifest.counts[name] = len(items)
    if discovery:
        pd.DataFrame(discovery).to_csv(directory / "discovery.csv", index=False)
    for filename, records in (("s5-records.jsonl", s5_records), ("meta-records.jsonl", meta_records)):
        with (directory / filename).open("w") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    manifest.counts["s5_records"] = len(s5_records)
    manifest.counts["meta_records"] = len(meta_records)
    result = pd.DataFrame(all_rows)
    summary = summarize_streams(result)
    summary.to_csv(directory / "summary.csv", index=False)
    if args.streams == "eval":
        from bench.e3a.hypotheses import evaluate

        h3, h4 = evaluate(result, cost_bound_percent=args.cost_bound_percent, seed=args.seed)
        pd.DataFrame(h3).to_csv(directory / "h3.csv", index=False)
        pd.DataFrame(h4).to_csv(directory / "h4.csv", index=False)
        summary[summary["arm"].isin(["s1_audit", "surrogate_audit", "s1_refit", "surrogate_refit"])].to_csv(
            directory / "h5_exploratory.csv", index=False
        )
    manifest.new_spend_usd = budget.new_spend()
    manifest.cost_usd = {str(arm): float(part["cost_usd"].sum()) for arm, part in result.groupby("arm")}
    if args.streams == "eval":
        manifest.cost_usd["teacher_variance_unused_draws"] = variance_overhead
    manifest.cache = {"teacher": {"hits": providers.agent_cache.hits, "misses": providers.agent_cache.misses}}
    manifest.models = {"teacher": "gpt-6.1-terra", "s1": "jev-1.14.0", "embedder": "embeddinggemma"}
    manifest.write()
    analysis = [
        "# E3a development tuning" if args.streams == "dev" else "# E3a evaluation",
        "",
        f"Mode: {args.mode}; parameters: `{json.dumps(config, sort_keys=True)}`.",
        "Costs are token-usage list-price estimates; local hardware and energy are not priced.",
        "",
    ]
    for _, row in summary.iterrows():
        group = result[(result["stream"] == row["stream"]) & (result["arm"] == row["arm"])]
        low, high = wilson(int(group["gold_joint_correct"].sum()), len(group))
        analysis.append(
            f"- {row['stream']}, {row['arm']}: joint accuracy {row['joint_accuracy']:.3f} "
            f"(95% Wilson {low:.3f}-{high:.3f}), coverage {row['coverage']:.3f}, "
            f"cost/ticket ${row['cost_per_ticket_usd']:.6f}, agent calls {row['agent_calls']}."
        )
    analysis.extend(
        [
            "",
            "Intervals are descriptive per-arm proportions, not paired hypothesis tests.",
            "Public-data contamination, synthetic policies and cohort marker, selective labels, "
            "teacher noise and unreconciled provider billing threaten validity.",
            "E3a exposed the lack of a truthful meta-layer patch kind for an audit-triggered rollback; "
            "contract 2.1.0 added `rollback` as a non-breaking patch kind.",
            "No E3 hypotheses are tested on development data." if args.streams == "dev" else "",
        ]
    )
    (directory / "ANALYSIS.md").write_text("\n".join(analysis) + "\n")


if __name__ == "__main__":
    main()
