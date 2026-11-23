"""Run the E3a lifecycle simulator; cache-only replay is the default.

Development tuning never consumes the evaluation streams. Evaluation requires
an explicit opt-in after the preregistration has been reviewed and approved.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import gzip
import hashlib
import io
import json
import re
import shutil
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
EVAL_STREAMS = tuple(f"seed_{seed}_{kind}" for seed in (11, 23, 37) for kind in ("control", "restructure_15", "clinc"))
RESUMED_STREAMS = EVAL_STREAMS[:2]
TYPESAFE_CAP = 8.00


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


def _comparison_csv(handle: Any) -> tuple[str, list[str]]:
    rows = list(csv.reader(handle))
    if not rows:
        return "", []
    excluded = [name for name in rows[0] if "latency" in name or "cpu_seconds" in name]
    keep = [index for index, name in enumerate(rows[0]) if name not in excluded]
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerows([[row[index] for index in keep] for row in rows])
    return output.getvalue(), excluded


def _verify_reconstructed_primary(table: pd.DataFrame, original: Path, name: str, arms: set[str]) -> None:
    """Fail closed before live work if any completed primary arm changed."""
    observed = set(table["arm"].unique())
    if observed != arms:
        raise RuntimeError(
            f"{name}: reconstructed primary arms differ: expected {sorted(arms)}, got {sorted(observed)}"
        )
    for arm, rows in table.groupby("arm", sort=True):
        path = original / f"{name}_{arm}.csv"
        if not path.is_file():
            raise RuntimeError(f"{name}: missing original primary artifact {path.name}")
        with path.open(newline="", encoding="utf-8") as handle:
            recorded, _ = _comparison_csv(handle)
        reconstructed, _ = _comparison_csv(io.StringIO(rows.to_csv(index=False, lineterminator="\n")))
        if recorded != reconstructed:
            raise RuntimeError(f"{name}: reconstructed primary arm {arm} differs from {path.name}")


def _comparison_text(path: Path) -> tuple[str | None, list[str]]:
    """Return comparable content without changing the recorded artifact."""
    if path.suffix == ".csv":
        with path.open(newline="", encoding="utf-8") as handle:
            return _comparison_csv(handle)
    if path.name in ("s5-records.jsonl", "meta-records.jsonl"):
        excluded = {"latency_ms", "created_at"}

        def strip_timing(value: Any) -> Any:
            if isinstance(value, dict):
                return {key: strip_timing(item) for key, item in value.items() if key not in excluded}
            if isinstance(value, list):
                return [strip_timing(item) for item in value]
            return value

        records = [strip_timing(json.loads(line)) for line in path.read_text(encoding="utf-8").splitlines()]
        return (
            "".join(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n" for record in records),
            sorted(excluded),
        )
    if path.name == "s4-traces.jsonl.gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return handle.read(), ["gzip header metadata"]
    return None, []


def compare_replay(original: Path, replay: Path) -> dict[str, Any]:
    """Compare deterministic artifacts and report observed metadata separately."""
    if not original.is_dir() or not replay.is_dir():
        raise ValueError("both artifact directories must exist")
    if original.resolve() == replay.resolve():
        raise ValueError("original and replay must be separate directories")
    original_files = {p.relative_to(original) for p in original.rglob("*") if p.is_file()}
    replay_files = {p.relative_to(replay) for p in replay.rglob("*") if p.is_file()}
    report: dict[str, Any] = {"deterministic": {}, "observed_metadata": {}, "presentation": {}}
    for relative in sorted(original_files | replay_files):
        name = str(relative)
        if relative.name in ("manifest.json", "secondary_replay_cache.json", "budget_stop.json", "ANALYSIS.md"):
            category = "observed_metadata"
        elif relative.suffix in (".pdf", ".png"):
            category = "presentation"
        else:
            category = "deterministic"
        left, right = original / relative, replay / relative
        entry: dict[str, Any] = {}
        report[category][name] = entry
        if not left.is_file() or not right.is_file():
            entry["status"] = "missing_original" if not left.is_file() else "missing_replay"
            continue
        a, b = left.read_bytes(), right.read_bytes()
        entry["original_sha256"] = hashlib.sha256(a).hexdigest()
        entry["replay_sha256"] = hashlib.sha256(b).hexdigest()
        entry["original_size"] = len(a)
        entry["replay_size"] = len(b)
        entry["byte_identical"] = a == b
        if category == "deterministic":
            left_text, left_excluded = _comparison_text(left)
            right_text, right_excluded = _comparison_text(right)
            entry["excluded_timing_fields"] = sorted(set(left_excluded + right_excluded))
            if (left_excluded or right_excluded) and relative.suffix != ".gz" and a != b:
                entry["raw_diff_including_excluded_fields"] = "".join(
                    difflib.unified_diff(
                        a.decode("utf-8").splitlines(keepends=True),
                        b.decode("utf-8").splitlines(keepends=True),
                        fromfile=f"original/{name}",
                        tofile=f"replay/{name}",
                    )
                )
            if left_text is not None and right_text is not None:
                entry["identical"] = left_text == right_text
                if left_text != right_text:
                    entry["diff"] = "".join(
                        difflib.unified_diff(
                            left_text.splitlines(keepends=True),
                            right_text.splitlines(keepends=True),
                            fromfile=f"original/{name}",
                            tofile=f"replay/{name}",
                        )
                    )
            else:
                entry["identical"] = a == b
        elif not entry["byte_identical"]:
            try:
                entry["diff"] = "".join(
                    difflib.unified_diff(
                        a.decode("utf-8").splitlines(keepends=True),
                        b.decode("utf-8").splitlines(keepends=True),
                        fromfile=f"original/{name}",
                        tofile=f"replay/{name}",
                    )
                )
            except UnicodeDecodeError:
                entry["first_differing_byte"] = next(
                    (index for index, (x, y) in enumerate(zip(a, b, strict=False)) if x != y), min(len(a), len(b))
                )
    report["deterministic_identical"] = bool(report["deterministic"]) and all(
        entry.get("identical", False) for entry in report["deterministic"].values()
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--compare-artifacts",
        nargs=2,
        metavar=("ORIGINAL", "REPLAY"),
        help="compare existing artifact directories without running the simulator",
    )
    parser.add_argument("--output-dir", type=Path, help="write artifacts to this directory")
    parser.add_argument("--streams", choices=("dev", "eval"), default="dev")
    parser.add_argument("--dev-condition", action="append", choices=DEV_STREAMS, default=None)
    parser.add_argument("--dev-run-id", default="dev-tuning")
    parser.add_argument("--mode", choices=("record", "replay"), default="replay")
    parser.add_argument(
        "--resume-eval",
        action="store_true",
        help="reconstruct the two completed evaluation streams from cache before continuing",
    )
    parser.add_argument("--allow-eval", action="store_true", help="requires prior preregistration approval")
    parser.add_argument(
        "--phase-limit",
        type=int,
        default=None,
        help="dev tuning: first N tickets from each phase; omitted means the complete stream",
    )
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--warmup", type=int, default=300)
    parser.add_argument("--n-cal", type=int, default=400)
    parser.add_argument("--n-val", type=int, default=400)
    parser.add_argument("--epsilon", type=float, default=0.15)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--audit-rate", type=float, default=1.0)
    parser.add_argument("--refit-interval", type=int, default=200)
    parser.add_argument(
        "--metric",
        choices=("probability", "confidence"),
        default=None,
        help="dev defaults to probability; evaluation requires the E2-selected signal",
    )
    parser.add_argument("--tau-rule", choices=("upper_bound", "margin"), default="margin")
    parser.add_argument("--seed", type=int, default=20261122)
    args = parser.parse_args()
    if args.compare_artifacts:
        report = compare_replay(*(Path(path) for path in args.compare_artifacts))
        print(json.dumps(report, indent=2, ensure_ascii=False))
        if not report["deterministic_identical"]:
            raise SystemExit(1)
        return
    if args.streams != "dev" and (args.dev_condition or args.dev_run_id != "dev-tuning"):
        parser.error("development condition and run id apply only to development")
    if "/" in args.dev_run_id or args.dev_run_id in ("", ".", ".."):
        parser.error("invalid development run id")
    if args.streams == "eval" and not args.allow_eval:
        parser.error("evaluation requires preregistration approval and --allow-eval")
    if args.streams == "eval" and args.phase_limit is not None:
        parser.error("evaluation streams must not be truncated")
    if args.streams == "eval" and (args.epsilon != 0.15 or args.audit_rate != 1.0):
        parser.error("evaluation requires the selected epsilon 0.15 and audit rate 1.0")
    if args.streams == "eval" and args.metric not in (None, "probability"):
        parser.error("evaluation requires the E2-selected probability metric")
    if args.resume_eval and (args.streams != "eval" or args.mode != "record"):
        parser.error("--resume-eval requires --streams eval --mode record")
    if args.resume_eval and args.output_dir is None:
        parser.error("--resume-eval requires a distinct, empty --output-dir")
    if args.resume_eval:
        original = (ROOT / "results" / "e3a" / "evaluation").resolve()
        output = args.output_dir.resolve()
        if output == original or original in output.parents or output in original.parents:
            parser.error("--resume-eval output must not overlap the original evaluation directory")
        if output.exists() and (not output.is_dir() or any(output.iterdir())):
            parser.error("--resume-eval output directory must be empty")
        if (args.warmup, args.n_cal, args.n_val, args.alpha, args.refit_interval, args.tau_rule, args.seed) != (
            300,
            400,
            400,
            0.05,
            200,
            "margin",
            20261122,
        ):
            parser.error("--resume-eval requires the original evaluation parameters")
    if args.metric is None:
        args.metric = "probability"
    from bench.e3a.baselines import run_baseline
    from bench.e3a.lifecycle_runner import ARMS, FACTORIAL, SECONDARY_AUDIT_RATES, run_lifecycle

    names = (
        (tuple(args.dev_condition) if args.dev_condition else DEV_STREAMS) if args.streams == "dev" else EVAL_STREAMS
    )
    run_id = args.dev_run_id if args.streams == "dev" else "evaluation"
    directory = args.output_dir or ROOT / "results" / "e3a" / run_id
    if args.mode == "replay" and directory.exists() and any(directory.iterdir()):
        parser.error("replay output directory must be empty; use --output-dir to preserve recorded artifacts")
    directory.mkdir(parents=True, exist_ok=True)
    config = {key: value for key, value in vars(args).items() if key not in ("output_dir", "compare_artifacts")}
    manifest = Manifest("e3a", run_id, config)
    for filename in ("banking_policy_4.json", "banking_policy_12.json", "clinc_map.json"):
        source = ROOT / "tasks" / filename
        manifest.data[filename] = hashlib.sha256(source.read_bytes()).hexdigest()
    budget = JournaledBudget({"openai": 75.0, "typesafe": TYPESAFE_CAP}, initial={"openai": previous_openai_spend()})
    if budget.spent.get("openai", 0.0) < 15.1003 or budget.spent.get("typesafe", 0.0) < 1.8431:
        raise RuntimeError("budget journal does not include the recorded $15.1003 OpenAI and $1.8431 TypeSafe spend")
    providers = E3aProviders(args.mode, budget)
    embedder = CachedEmbedder(JsonCache(EMBEDDING_NAMESPACE, mode=args.mode))
    mining_timing = JsonCache("e3a_mining_timing_v1", mode=args.mode)
    caches = (
        providers.agent_cache,
        providers.s1.cache,
        providers.writer.cache,
        embedder.cache,
        embedder.timing_cache,
        mining_timing,
    )
    if args.resume_eval:
        for cache in caches:
            cache.mode = "replay"
        # Copy the completed artifacts verbatim; reconstruction below restores
        # in-memory records and paired teacher selections without rewriting them.
        for name in RESUMED_STREAMS:
            artifacts = list(original.glob(f"{name}_*"))
            stream_dir = original / name
            if not artifacts or not stream_dir.is_dir():
                raise RuntimeError(f"missing original completed artifacts for {name}")
            for artifact in artifacts:
                if artifact.is_file():
                    shutil.copy2(artifact, directory / artifact.name)
            shutil.copytree(stream_dir, directory / name)
    all_rows: list[dict[str, Any]] = []
    s5_records: list[dict[str, Any]] = []
    meta_records: list[dict[str, Any]] = []
    discovery: list[dict[str, Any]] = []
    writer_failures: list[dict[str, Any]] = []
    variance_overhead = 0.0
    secondary_inputs = []
    for name in names:
        reconstructing = args.resume_eval and name in RESUMED_STREAMS
        if args.resume_eval and name == EVAL_STREAMS[2]:
            for cache in caches:
                cache.mode = "record"
        stream_seed = args.seed + int(name.split("_")[1]) if name.startswith("seed_") else args.seed
        path = ROOT / "tasks" / "streams" / f"{name}.csv"
        manifest.data[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        frame = pd.read_csv(path)
        items, shift = items_for_stream(frame, phase_limit=args.phase_limit)
        completed = collect(items, providers, workers=args.workers)
        errors = [row for row in completed if row["status"] == "error"]
        if errors:
            pd.DataFrame(completed).to_csv(directory / f"{name}_collection.csv", index=False, lineterminator="\n")
            manifest.notes.append(f"{name}: {len(errors)} failed teacher calls; see collection CSV")
            manifest.new_spend_usd = budget.new_spend()
            manifest.write(directory)
            budget_errors = [row["error"] for row in errors if "budget" in row["error"].lower()]
            if budget_errors:
                raise RuntimeError(budget_errors[0])
            raise RuntimeError(manifest.notes[-1])
        if args.streams == "eval" and name.endswith("_control"):
            variance_rows, overhead = teacher_variance(
                items, providers, seed=stream_seed, size=100, workers=args.workers
            )
            if not reconstructing:
                pd.DataFrame(variance_rows).to_csv(
                    directory / f"{name}_teacher_variance.csv", index=False, lineterminator="\n"
                )
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
            "seed": stream_seed,
            "embedder": embedder,
            "min_support": 5,
            "diagnostics": discovery,
            "stream": name,
            "s5_records": s5_records,
            "meta_records": meta_records,
            "timing_cache": mining_timing,
            "writer_failures": writer_failures,
        }
        visible = name.endswith("_visible")
        if not visible:
            primary = run_lifecycle(items, providers, settings)
            for arm, arm_rows in primary.items():
                for row in arm_rows:
                    row.update(stream=name, shift_at=shift_at, arm=arm)
                rows.extend(arm_rows)
            budgets = {
                row["ticket_index"]: min(primary[arm][pos]["training_available_labels"] for arm in FACTORIAL)
                for pos, row in enumerate(primary[FACTORIAL[0]])
                if row["training_available_labels"] is not None
            }
            secondary_inputs.append((name, shift_at, items, settings, budgets))
        baseline_arms = (
            ("fixed_gate_config_hash",) if visible else ("fixed_gate", "fixed_gate_config_hash", "knn_cache")
        )
        for arm in baseline_arms:
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
                    seed=stream_seed,
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
            predicted_verify = row.get("predicted_verify")
            row["d2_teacher_agreement"] = predicted_verify == teacher.verified if predicted_verify is not None else None
            row["joint_decision_agreement"] = (
                predicted == teacher_entry and predicted_verify == teacher.verified
                if predicted is not None and predicted_verify is not None and teacher_entry is not None
                else None
            )
            for part in ("s1", "agent", "shadow", "audit", "writer", "mining", "embedding"):
                old_name, new_name = f"cost_{part}", f"{part}_cost_usd"
                if old_name in row:
                    row[new_name] = row.pop(old_name)
        table = pd.DataFrame(rows)
        if reconstructing:
            _verify_reconstructed_primary(
                table, original, name, set(ARMS) | {"always_agent", "fixed_gate", "fixed_gate_config_hash", "knn_cache"}
            )
        else:
            for arm, arm_rows in table.groupby("arm", sort=True):
                arm_rows.to_csv(directory / f"{name}_{arm}.csv", index=False, lineterminator="\n")
            summary = summarize_streams(table)
            summary.to_csv(directory / f"{name}_summary.csv", index=False, lineterminator="\n")
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
        if writer_failures:
            pd.DataFrame(writer_failures).to_csv(directory / "writer_failures.csv", index=False, lineterminator="\n")
    if args.streams == "eval":
        from bench.e3a.hypotheses import evaluate

        h3, h4 = evaluate(pd.DataFrame(all_rows), seed=args.seed)
        pd.DataFrame(h3).to_csv(directory / "h3.csv", index=False, lineterminator="\n")
        pd.DataFrame(h4).to_csv(directory / "h4.csv", index=False, lineterminator="\n")
    # Replay after all primary streams, retaining their exact paired teacher draws.
    replay_caches = {
        "teacher": providers.agent_cache,
        "s1": providers.s1.cache,
        "writer": providers.writer.cache,
        "mining_timings": mining_timing,
    }
    replay_start = {key: (cache.hits, cache.misses) for key, cache in replay_caches.items()}
    replay_error = None
    try:
        for name, shift_at, items, settings, budgets in secondary_inputs:
            replay_settings = {
                **settings,
                "secondary_only": True,
                "primary_training_budgets": budgets,
                "timing_cache": None,
            }
            replay = run_lifecycle(items, providers, replay_settings)
            by_index = {item["index"]: item for item in items}
            for arm, arm_rows in replay.items():
                for row in arm_rows:
                    row.update(stream=name, shift_at=shift_at, arm=arm)
                    teacher = by_index[row["ticket_index"]]["teacher"]
                    route = row.get("route") or {}
                    row["teacher_agreement"] = (
                        (
                            route.get("department") == teacher.route.get("department")
                            and route.get("priority") == teacher.route.get("priority")
                            and row.get("verified") == teacher.verified
                        )
                        if teacher.route
                        else None
                    )
                    teacher_entry = None
                    for event in teacher.events:
                        if event["tool"] == "route_ticket":
                            break
                        if event["tool"] == "get_policy":
                            teacher_entry = event["entry_id"]
                    predicted = row.get("predicted_entry")
                    verify = row.get("predicted_verify")
                    row["d1_teacher_agreement"] = (
                        predicted == teacher_entry if predicted is not None and teacher_entry is not None else None
                    )
                    row["d2_teacher_agreement"] = verify == teacher.verified if verify is not None else None
                    row["joint_decision_agreement"] = (
                        predicted == teacher_entry and verify == teacher.verified
                        if predicted is not None and verify is not None and teacher_entry is not None
                        else None
                    )
                    for part in ("s1", "agent", "shadow", "audit", "writer", "mining", "embedding"):
                        row[f"{part}_cost_usd"] = row.pop(f"cost_{part}")
                pd.DataFrame(arm_rows).to_csv(directory / f"{name}_{arm}.csv", index=False, lineterminator="\n")
                all_rows.extend(arm_rows)
    except Exception as exc:
        replay_error = {"type": type(exc).__name__, "message": str(exc)}
        raise
    finally:
        replay_cache = {
            key: {"hits": cache.hits - replay_start[key][0], "misses": cache.misses - replay_start[key][1]}
            for key, cache in replay_caches.items()
        }
        (directory / "secondary_replay_cache.json").write_text(
            json.dumps({"caches": replay_cache, "error": replay_error}, indent=2) + "\n"
        )
    if writer_failures:
        pd.DataFrame(writer_failures).to_csv(directory / "writer_failures.csv", index=False, lineterminator="\n")
    if discovery:
        summaries = []
        candidates = []
        for report in discovery:
            info = {key: value for key, value in report.items() if key != "candidates"}
            summaries.append(info)
            candidates.extend({**info, **candidate} for candidate in report.get("candidates", []))
        pd.DataFrame(summaries).to_csv(directory / "discovery_summary.csv", index=False, lineterminator="\n")
        pd.DataFrame(candidates).to_csv(directory / "discovery.csv", index=False, lineterminator="\n")
    for filename, records in (("s5-records.jsonl", s5_records), ("meta-records.jsonl", meta_records)):
        with (directory / filename).open("w") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    manifest.counts["s5_records"] = len(s5_records)
    manifest.counts["meta_records"] = len(meta_records)
    result = pd.DataFrame(all_rows)
    summary = summarize_streams(result)
    summary.to_csv(directory / "summary.csv", index=False, lineterminator="\n")
    for stream, part in summary.groupby("stream"):
        if not args.resume_eval or stream not in RESUMED_STREAMS:
            part.to_csv(directory / f"{stream}_summary.csv", index=False, lineterminator="\n")
    audit_rates = {**SECONDARY_AUDIT_RATES, "s1_audit": args.audit_rate}
    audit_curve = summary[summary["arm"].isin(audit_rates)].copy()
    audit_curve["audit_rate"] = audit_curve["arm"].map(audit_rates)
    reference_costs = summary[summary["arm"] == "always_agent"].set_index("stream")["cost_per_ticket_usd"]
    audit_curve["always_agent_cost_per_ticket_usd"] = audit_curve["stream"].map(reference_costs)
    denominator = audit_curve["always_agent_cost_per_ticket_usd"].where(
        audit_curve["always_agent_cost_per_ticket_usd"] != 0
    )
    audit_curve["cost_ratio_vs_always_agent"] = audit_curve["cost_per_ticket_usd"] / denominator
    audit_curve.to_csv(directory / "audit_rate_curve.csv", index=False, lineterminator="\n")
    if args.streams == "eval":
        summary[summary["arm"].isin(["s1_audit", "surrogate_audit", "s1_refit", "surrogate_refit"])].to_csv(
            directory / "h5_exploratory.csv", index=False, lineterminator="\n"
        )
    manifest.new_spend_usd = budget.new_spend()
    manifest.cost_usd = {str(arm): float(part["cost_usd"].sum()) for arm, part in result.groupby("arm")}
    failed_attempt = directory / "initial_writer_failure.json"
    if args.streams == "dev" and failed_attempt.exists():
        failure = json.loads(failed_attempt.read_text())
        manifest.cost_usd["discarded_initial_writer_calls"] = failure["initial_attempt_all_writer_calls_cost_usd"]
        manifest.notes.append(
            "Initial failed simulator attempt and its prior TypeSafe spend are documented in "
            "initial_writer_failure.json; cached calls may also appear in logical arm costs."
        )
    if args.streams == "eval":
        manifest.cost_usd["teacher_variance_unused_draws"] = variance_overhead
    caches = {
        "teacher": providers.agent_cache,
        "s1": providers.s1.cache,
        "writer": providers.writer.cache,
        "embeddings": embedder.cache,
        "local_timings": embedder.timing_cache,
        "mining_timings": mining_timing,
    }
    manifest.cache = {name: {"hits": cache.hits, "misses": cache.misses} for name, cache in caches.items()}
    manifest.models = {
        "teacher": providers.actual_model or "not returned",
        "s1": providers.s1.pinned_model or "not called",
        "writer": providers.writer.actual_model or "not called",
        "embedder": "embeddinggemma",
    }
    manifest.write(directory)
    analysis = [
        "# E3a development tuning" if args.streams == "dev" else "# E3a evaluation",
        "",
        f"Mode: {args.mode}; parameters: `{json.dumps(config, sort_keys=True)}`.",
        "Costs are token-usage list-price estimates; local hardware and energy are not priced.",
        "Secondary audit-rate arms replay shared teacher trajectories after all primary arms. "
        "Divergent recompilations and questions can require uncached writer or S1 calls; "
        "secondary_replay_cache.json records observed cache hits and misses.",
        "audit_rate_curve.csv reports per-stream cost ratios, detection delays and misses, "
        "and control false demotions for each audit rate.",
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
    try:
        main()
    except RuntimeError as exc:
        if "budget" in str(exc).lower() or "spend exceeds cap" in str(exc).lower():
            import sys

            stream = (
                "evaluation"
                if "--streams" in sys.argv and sys.argv[sys.argv.index("--streams") + 1] == "eval"
                else "dev-tuning"
            )
            if stream != "evaluation" and "--dev-run-id" in sys.argv:
                stream = sys.argv[sys.argv.index("--dev-run-id") + 1]
            directory = (
                Path(sys.argv[sys.argv.index("--output-dir") + 1])
                if "--output-dir" in sys.argv
                else ROOT / "results" / "e3a" / stream
            )
            directory.mkdir(parents=True, exist_ok=True)
            budget = JournaledBudget(
                {"openai": 75.0, "typesafe": TYPESAFE_CAP}, initial={"openai": previous_openai_spend()}
            )
            (directory / "budget_stop.json").write_text(
                json.dumps(
                    {
                        "error": re.sub(r"org-[A-Za-z0-9_-]+", "org-REDACTED", str(exc)),
                        "spent_usd": dict(budget.spent),
                        "caps_usd": budget.caps,
                    },
                    indent=2,
                )
                + "\n"
            )
        raise
