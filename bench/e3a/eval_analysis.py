"""Generate a post-run E3a report without model calls or modification of run artifacts.

Run from the repository root, passing both retained stops explicitly for the resumed evaluation:

    python -m bench.e3a.eval_analysis --input-dir bench/results/e3a/evaluation-resumed \\
        --stop-history bench/results/e3a/evaluation-resumed/budget_stop.json \\
        --stop-history bench/results/e3a/evaluation/budget_stop.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "results/e3a/evaluation"
DEFAULT_OUTPUT = ROOT / "results/e3a/eval/ANALYSIS.md"
STREAMS = tuple(f"seed_{seed}_{kind}" for seed in (11, 23, 37) for kind in ("control", "restructure_15", "clinc"))
ARMS = (
    "always_agent",
    "s1_audit",
    "s1_refit",
    "escalation_only",
    "fixed_gate",
    "fixed_gate_config_hash",
    "oracle_audit",
    "knn_cache",
    "surrogate_audit",
    "surrogate_refit",
    "s1_audit_0.1",
    "s1_audit_0.3",
    "s1_audit_0.6",
)
FROZEN = {
    "streams": "eval",
    "warmup": 300,
    "n_cal": 400,
    "n_val": 400,
    "epsilon": 0.15,
    "alpha": 0.05,
    "audit_rate": 1.0,
    "refit_interval": 200,
    "metric": "probability",
    "tau_rule": "margin",
    "seed": 20261122,
    "phase_limit": None,
}


def fmt(value):
    if value is None or pd.isna(value):
        return "NA"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value).replace("|", "\\|").replace("\n", " ")


def table(frame, columns):
    columns = [column for column in columns if column in frame.columns]
    if not columns or frame.empty:
        return ["No rows available."]
    return ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"] + [
        "| " + " | ".join(fmt(value) for value in row) + " |"
        for row in frame[columns].itertuples(index=False, name=None)
    ]


def report(directory: Path, stop_history: tuple[Path, ...] = ()) -> str:
    lines = [
        "# E3a post-evaluation analysis",
        "",
        "Generated from retained evaluation artifacts; no model calls. NA means unavailable, not zero.",
    ]
    missing = []
    problems = []

    def csv(name):
        path = directory / name
        if not path.exists():
            missing.append(name)
            return None
        try:
            return pd.read_csv(path)
        except (ValueError, OSError) as exc:
            problems.append(f"{name}: {exc}")
            return None

    def json_file(name):
        path = directory / name
        if not path.exists():
            missing.append(name)
            return None
        try:
            return json.loads(path.read_text())
        except (ValueError, OSError) as exc:
            problems.append(f"{name}: {exc}")
            return None

    manifest = json_file("manifest.json")
    lines += ["", "## Run provenance, deviations and spend"]
    if manifest:
        config = manifest.get("config", {})
        lines.append(
            f"- Run ID: {fmt(manifest.get('run_id'))}; git SHA: {fmt(manifest.get('git_sha'))}; "
            f"dirty: {fmt(manifest.get('git_dirty'))}."
        )
        lines.append(f"- Models: `{json.dumps(manifest.get('models', {}), sort_keys=True)}`.")
        deviations = [
            f"{key}: expected {expected!r}, observed {config.get(key, '<missing>')!r}"
            for key, expected in FROZEN.items()
            if key not in config or config[key] != expected
        ]
        lines.append(
            "- Frozen configuration deviations: "
            + ("; ".join(deviations) if deviations else "none detected in checked fields")
            + "."
        )
        lines.append(
            f"- Manifest new provider spend (USD): `{json.dumps(manifest.get('new_spend_usd', {}), sort_keys=True)}`; "
            f"logical arm costs (USD): `{json.dumps(manifest.get('cost_usd', {}), sort_keys=True)}`."
        )
        lines.append(f"- Manifest notes: `{json.dumps(manifest.get('notes', []), ensure_ascii=False)}`.")
        counts = manifest.get("counts", {})
        for stream in STREAMS:
            if counts.get(stream) != 2400:
                problems.append(f"{stream}: manifest count {counts.get(stream, 'missing')}, expected 2400")
    else:
        lines.append("- Manifest unavailable; frozen configuration, run completion and spend cannot be verified.")
    stops = []
    paths = (*stop_history, directory / "budget_stop.json")
    seen = set()
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if not path.exists() and path == directory / "budget_stop.json":
            continue
        try:
            data = json.loads(path.read_text())
        except (ValueError, OSError) as exc:
            problems.append(f"{path}: {exc}")
            continue
        stops.append(data)
        lines.append(f"- Recorded budget stop ({path}): `{json.dumps(data, sort_keys=True)}`.")
    if any(
        isinstance(stop, dict)
        and "402" in str(stop.get("error", ""))
        and isinstance(stop.get("spent_usd"), dict)
        and isinstance(stop["spent_usd"].get("typesafe"), (int, float))
        and abs(stop["spent_usd"]["typesafe"] - 2.8020353839984793) < 1e-6
        for stop in stops
    ):
        lines.append(
            "- At the TypeSafe 402 stop, the dashboard showed $4.89 billed versus approximately $2.75 "
            "settled list-price spend (about 1.78 times). After two authorized top-ups, $9.89 of balance "
            "remained on top of $4.89 already billed ($14.78 total available). The cumulative list-price "
            "proxy cap was raised to $8.00 (about $14.24 billed at the observed ratio). The previous $0.05 "
            "unpriced-call reservation is conservatively retained. This proxy cannot guarantee the actual billed "
            "cap; dashboard billing must be monitored separately."
        )
    if any(
        isinstance(stop, dict)
        and "openai: budget reserved for unpriced call" in str(stop.get("error", "")).lower()
        and "503" in str(stop.get("error", ""))
        for stop in stops
    ):
        lines.append(
            "- OpenAI 503 stop deviation: model access verification failed and interrupted evaluation. "
            "The $1.00 unpriced-call reservation is retained; it is not evidence of actual provider billing. "
            "Actual billing for the failed call is unknown."
        )
    if any(
        isinstance(stop, dict)
        and "429" in str(stop.get("error", ""))
        and "no credits remaining" in str(stop.get("error", "")).lower()
        for stop in stops
    ):
        lines.append(
            "- OpenAI 429 deviation: credits were exhausted; after a user-authorized top-up the run resumed "
            "from cache. The $1.00 unpriced-call reservation was retained; actual billing is unknown."
        )
    replay = directory / "secondary_replay_cache.json"
    if replay.exists():
        data = json_file("secondary_replay_cache.json")
        lines.append(f"- Secondary replay status: `{json.dumps(data, sort_keys=True)}`.")
    else:
        missing.append("secondary_replay_cache.json")
    lines.append(
        "- Logical costs can count cached calls across arms and are not provider spend. "
        "Provider dashboard reconciliation is unverified for current spend; "
        "hardware and energy are unpriced."
    )
    lines.append(
        "- Pacing deviation: the runner reserves at most 400,000 estimated tokens per rolling minute, "
        "but does not record individual pacing sleeps; actual waits and any backoff cannot be audited "
        "from the retained artifacts."
    )

    lines += [
        "",
        "## H1 — discovery",
        "Candidate-level precision and recall are per mining report; repeated reports are not independent experiments.",
    ]
    discovery = csv("discovery_summary.csv")
    candidates = csv("discovery.csv")
    if discovery is not None and not discovery.empty:
        cols = [
            "stream",
            "arm",
            "ticket_index",
            "generation",
            "stage",
            "discovery_precision",
            "discovery_recall",
            "discovery_true_positives",
            "discovery_accepted",
            "discovery_rejected",
            "ambiguous_retrieval_count",
        ]
        lines += table(discovery, cols)
        if {"discovery_precision", "discovery_recall"}.issubset(discovery.columns):
            valid = discovery.dropna(subset=["discovery_precision", "discovery_recall"])
            success = ((valid["discovery_precision"] == 1) & (valid["discovery_recall"] == 1)).sum()
            lines.append(
                f"Verdict: {success}/{len(valid)} reports with defined precision attain both precision and recall 1; "
                f"{len(discovery) - len(valid)} have undefined endpoints. Reports are not independent."
            )
        else:
            problems.append("discovery_summary.csv: missing precision or recall")
    else:
        lines.append("Verdict: not evaluable; discovery summaries unavailable or empty.")
    if candidates is not None and not candidates.empty:
        lines.append(
            f"All {len(candidates)} accepted and rejected candidate records, with reasons, are retained in "
            f"`{directory / 'discovery.csv'}`."
        )
    lines.append(
        "The preregistration reports a development identity functional-dependency false negative; it was not "
        "corrected. Candidate-level results above are evaluation observations, not proof of independence."
    )

    lines += ["", "## H2 — promoted-generation risk control"]
    path = directory / "s5-records.jsonl"
    promotions = []
    records_ok = path.exists()
    if records_ok:
        try:
            for text in path.read_text().splitlines():
                record = json.loads(text)
                for mod in record["response"]["body"]["modifications"]:
                    suite = mod.get("evaluation", {}).get("eval_suite")
                    if mod.get("operation") == "add" and suite == "independent shadow calibration and validation":
                        metrics = mod["evaluation"]["candidate"]
                        promotions.append(
                            {
                                "target": mod.get("target_ref"),
                                "generation": mod.get("after", {}).get("value", {}).get("generation"),
                                "validation_served": metrics.get("validation_served"),
                                "validation_errors": metrics.get("validation_errors"),
                                "validation_upper_bound": metrics.get("validation_upper_bound"),
                            }
                        )
        except (ValueError, KeyError, TypeError, OSError) as exc:
            problems.append(f"s5-records.jsonl: {exc}")
            records_ok = False
    else:
        missing.append("s5-records.jsonl")
    if records_ok:
        known = [
            p
            for p in promotions
            if isinstance(p["validation_upper_bound"], (int, float)) and pd.notna(p["validation_upper_bound"])
        ]
        passed = sum(p["validation_upper_bound"] < 0.15 for p in known)
        lines.append(
            f"- Promotion records: {len(promotions)}; bounds available: {len(known)}; "
            f"below 0.15: {passed}/{len(known)} ({fmt(passed / len(known) if known else None)})."
        )
        if not promotions:
            verdict = "not evaluable: no promotions"
        elif len(known) != len(promotions):
            verdict = "not fully evaluable: missing validation bounds"
        elif passed == len(promotions):
            verdict = "all recorded promotion bounds below target"
        else:
            verdict = "some recorded promotion bounds do not meet target"
        lines.append(f"- Verdict: {verdict}.")
        lines += table(
            pd.DataFrame(promotions),
            [
                "target",
                "generation",
                "validation_served",
                "validation_errors",
                "validation_upper_bound",
            ],
        )
        lines.append(
            "- Transition records omit stream identity; each row is one recorded decision promotion, "
            "not an independent stream-level experiment."
        )
    else:
        lines.append("- Verdict: not evaluable; promotion records unavailable or invalid.")
    lines.append(
        "- No promotion is not zero-error success. Validation controls teacher disagreement under its assumptions, "
        "not gold error or post-shift risk."
    )
    lines += ["", "## H3 — control noninferiority"]
    h3 = csv("h3.csv")
    if (
        h3 is not None
        and len(h3) == 1
        and {"paired_accuracy_loss", "upper_one_sided_95", "margin", "noninferior"}.issubset(h3.columns)
        and h3[["paired_accuracy_loss", "upper_one_sided_95", "margin"]].notna().all().all()
    ):
        row = h3.iloc[0]
        lines.append(
            f"- Paired reference-minus-S1 accuracy loss: {fmt(row['paired_accuracy_loss'])}; "
            f"one-sided 95% upper bound: {fmt(row['upper_one_sided_95'])}; margin: {fmt(row['margin'])}."
        )
        verdict = (
            "noninferiority demonstrated" if row["upper_one_sided_95"] < 0.02 else "noninferiority not demonstrated"
        )
        lines.append(
            f"- Verdict: {verdict} using the preregistered 0.02 margin; stored flag: {fmt(row['noninferior'])}."
        )
        lines += table(
            h3,
            [
                "served_count",
                "served_arm_accuracy",
                "served_reference_accuracy",
                "served_paired_accuracy_loss",
                "resamples",
            ],
        )
        lines.append(
            "- Served subset is selected and descriptive; the primary estimand includes all post-1200 tickets "
            "and has no cost condition."
        )
    else:
        lines.append("- Verdict: not evaluable; valid h3.csv unavailable.")

    lines += ["", "## H4 — 15% restructure"]
    h4 = csv("h4.csv")
    needed = {
        "comparison",
        "mean_audit_advantage",
        "holm_p_within_severity",
        "per_seed_advantages",
        "all_seed_effects_positive",
    }
    if (
        h4 is not None
        and needed.issubset(h4.columns)
        and set(h4["comparison"]) == {"s1_refit", "escalation_only"}
        and len(h4) == 2
        and h4[["mean_audit_advantage", "holm_p_within_severity"]].notna().all().all()
    ):
        lines += table(
            h4,
            [
                "comparison",
                "mean_audit_advantage",
                "ci_low",
                "ci_high",
                "ticket_permutation_one_sided_p",
                "holm_p_within_severity",
                "per_seed_advantages",
                "all_seed_effects_positive",
            ],
        )
        for _, row in h4.iterrows():
            supported = row["mean_audit_advantage"] > 0 and row["holm_p_within_severity"] < 0.05
            verdict = "lower error demonstrated" if supported else "lower error not demonstrated"
            lines.append(f"- Against {row['comparison']}: {verdict} at Holm-adjusted 0.05.")
        lines.append(
            "- Positive advantage favors audit. Ticket sign flips assume exchangeability; adaptation and temporal "
            "dependence may make uncertainty anti-conservative. Three seed effects are an essential secondary check; "
            "traffic shift is exploratory."
        )
    else:
        lines.append("- Verdict: not evaluable; both valid Holm-family comparisons are required.")

    lines += ["", "## H5 — exploratory equal-training-label comparison"]
    h5 = csv("h5_exploratory.csv")
    if h5 is not None and not h5.empty:
        lines += table(
            h5,
            [
                "stream",
                "arm",
                "tickets",
                "joint_accuracy",
                "teacher_agreement",
                "coverage",
                "cost_per_ticket_usd",
                "agent_calls",
                "promotions",
                "audits",
                "detection_delay_tickets",
                "detection_miss",
                "false_demotions",
                "recovery_ticket",
                "amortization_ticket",
            ],
        )
        lines.append(
            "- Descriptive comparison only; no preregistered significance criterion. Equal training-label "
            "availability is not equal total agent calls."
        )
    else:
        lines.append("- Verdict: not evaluable; exploratory comparison unavailable.")
    lines += ["", "## Per-stream outcomes and audit-rate replay"]
    summary = csv("summary.csv")
    if summary is not None:
        lines += table(
            summary,
            [
                "stream",
                "arm",
                "tickets",
                "joint_accuracy",
                "teacher_agreement",
                "coverage",
                "total_cost_usd",
                "cost_per_ticket_usd",
                "agent_calls",
                "promotions",
                "demotions",
                "audits",
                "detection_delay_tickets",
                "detection_delay_audits",
                "detection_miss",
                "false_demotions",
                "recovery_ticket",
                "amortization_ticket",
            ],
        )
    curve = csv("audit_rate_curve.csv")
    if curve is not None:
        lines += ["", "### Secondary audit rates"]
        lines += table(
            curve,
            [
                "stream",
                "arm",
                "audit_rate",
                "cost_ratio_vs_always_agent",
                "detection_delay_tickets",
                "detection_delay_audits",
                "detection_miss",
                "false_demotions",
            ],
        )
    lines += ["", "## Ticket-level agreement and completeness"]
    outcome_rows = []
    for stream in STREAMS:
        if stream.endswith("_clinc"):
            lines.append(f"- {stream}: secondary audit-rate replays skipped by user instruction (deviation).")
        for arm in ARMS:
            if stream.endswith("_clinc") and arm in {"s1_audit_0.1", "s1_audit_0.3", "s1_audit_0.6"}:
                continue
            name = f"{stream}_{arm}.csv"
            frame = csv(name)
            if frame is None:
                continue
            if len(frame) != 2400 or "ticket_index" not in frame or set(frame["ticket_index"]) != set(range(2400)):
                problems.append(f"{name}: incomplete or duplicate ticket indices ({len(frame)} rows)")
            if not {"served_by", "audited", "joint_decision_agreement"}.issubset(frame.columns):
                problems.append(f"{name}: missing agreement columns")
                continue
            served = frame[frame["served_by"] != "agent"]
            row = {
                "stream": stream,
                "arm": arm,
                "served": len(served),
                "audits": int(frame["audited"].fillna(False).astype(bool).sum()),
            }
            for column in (
                "gold_department_correct",
                "gold_priority_correct",
                "gold_identity_correct",
                "d1_teacher_agreement",
                "d2_teacher_agreement",
                "joint_decision_agreement",
                "latency_ms",
            ):
                if column in frame:
                    row[column] = frame[column].mean()
            agreement = served["joint_decision_agreement"].dropna()
            row["served_joint_labeled"] = len(agreement)
            row["served_joint_error"] = 1 - agreement.mean() if len(agreement) else None
            outcome_rows.append(row)
    lines += table(
        pd.DataFrame(outcome_rows),
        [
            "stream",
            "arm",
            "served",
            "audits",
            "served_joint_labeled",
            "served_joint_error",
            "gold_department_correct",
            "gold_priority_correct",
            "gold_identity_correct",
            "d1_teacher_agreement",
            "d2_teacher_agreement",
            "joint_decision_agreement",
            "latency_ms",
        ],
    )
    lines.append(
        "- Served joint error uses only served tickets with observed teacher labels; selective missing labels can "
        "bias it. Overall agreement columns use available labels."
    )
    lines += ["", "## Missing outputs and limitations"]
    lines.append(
        "- Missing files: "
        + (", ".join(f"`{name}`" for name in missing) if missing else "none among expected files")
        + "."
    )
    lines.append(
        "- Data/completeness issues: " + ("; ".join(problems) if problems else "none detected by these checks") + "."
    )
    lines.append(
        "- Public benchmark contamination, synthetic policy/cohort markers, teacher error, adaptive temporal "
        "dependence and selectively observed labels limit interpretation. Missing or interrupted outputs "
        "cannot establish a hypothesis."
    )
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--stop-history",
        type=Path,
        action="append",
        default=[],
        help="include a retained budget_stop.json (repeatable; current input stop is also included automatically)",
    )
    args = parser.parse_args()
    text = report(args.input_dir, tuple(args.stop_history))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as output:
        output.write(text)


if __name__ == "__main__":
    main()
