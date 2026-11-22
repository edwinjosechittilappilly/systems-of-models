"""Run the registered E3b analysis, recording or replaying all provider calls."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import som
from bench.common.budget import Budget, BudgetExceeded
from bench.common.cache import CacheMiss, JsonCache, answer_from_dict, answer_to_dict
from bench.common.manifest import Manifest
from bench.e3b.data import COMMIT, DOMAINS, MODELS, fetch, file_name, load
from bench.e3b.extract import instances, to_trace
from bench.e3b.metrics import (
    aurc,
    aurc_cluster_bootstrap,
    calibrate_threshold,
    discovery_metrics,
    risk_coverage,
    summary_metrics,
    wilson,
)
from som.compile import OpenAIQuestionWriter, mine, write_question
from som.compile.mining import Example

ROOT = Path(__file__).parent
RUN_ID = "tau2-768f3d8"
TRAIN = "gpt-4.1"
HELD_OUT = tuple(model for model in MODELS if model != TRAIN)


def calibration(domain: str, task_id: str) -> bool:
    key = f"e3b-calibration:{domain}:{task_id}".encode()
    return int(hashlib.sha256(key).hexdigest(), 16) % 5 == 0


def labels() -> dict[str, dict[str, Any]]:
    """Read the restricted, frozen YAML label format without an optional YAML dependency."""
    result: dict[str, dict[str, Any]] = {}
    domain = None
    in_arguments = False
    for line in (ROOT / "decision_labels.yaml").read_text().splitlines():
        if line and not line.startswith((" ", "#")) and line.endswith(":"):
            domain = line[:-1]
            result[domain] = {"branch": [], "arguments": {}}
        elif line.strip().startswith("branch_tools:"):
            assert domain
            result[domain]["branch"] = [s.strip() for s in line.split("[", 1)[1].split("]", 1)[0].split(",")]
        elif line.strip() == "tool_arguments:":
            in_arguments = True
        elif line.startswith("  distractor:"):
            in_arguments = False
        elif in_arguments and line.startswith("      ") and ": [" in line:
            assert domain
            tool, values = line.strip().split(": [", 1)
            result[domain]["arguments"][tool] = [s.strip() for s in values.rstrip("]").split(",")]
    return result


def judgement(rules: dict[str, Any], candidate: Any) -> bool:
    return (candidate.kind == "branch" and candidate.tool in rules["branch"]) or (
        candidate.kind == "tool_argument" and candidate.argument in rules["arguments"].get(candidate.tool, [])
    )


def csv_write(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    k: json.dumps(v, ensure_ascii=False, sort_keys=True) if isinstance(v, (dict, list, tuple)) else v
                    for k, v in row.items()
                }
            )


def _safe_error(error: Exception) -> str:
    # Avoid emitting HTTP response bodies or credentials into results.
    return type(error).__name__


class Calls:
    def __init__(self, mode: str, directory: Path) -> None:
        cache_dir = directory if mode == "replay" and (directory / "e3b_writer.jsonl").exists() else None
        self.writer_cache = JsonCache("e3b_writer", mode=mode, **({"directory": cache_dir} if cache_dir else {}))
        self.jev_cache = JsonCache("e3b_jev", mode=mode, **({"directory": cache_dir} if cache_dir else {}))
        self.budget = Budget({"openai": 5.0, "typesafe": 3.0})
        self.costs = Counter()
        self.prior = {
            provider: sum(
                json.loads(line)["response"].get("cost", 0.0)
                for line in cache.path.read_text().splitlines()
                if line.strip()
            )
            if cache.path.exists()
            else 0.0
            for provider, cache in (("openai", self.writer_cache), ("typesafe", self.jev_cache))
        }
        self.jev = None

    def writer(self, samples: list[dict[str, Any]]) -> dict[str, str]:
        payload = {"model": "gpt-6.1-terra", "samples": samples, "max_output_tokens": 1200}

        def call() -> dict[str, Any]:
            # UTF-8 bytes upper-bound text tokens; include request overhead and bounded output.
            bound = (len(json.dumps(payload, ensure_ascii=False).encode()) + 4096) / 1e6 + 1200 * 5 / 1e6
            if self.prior["openai"] + self.budget.spent["openai"] + bound > 5:
                raise BudgetExceeded("openai budget would be exceeded")
            try:
                from openai import OpenAI

                client = OpenAI(max_retries=0)

                class Responses:
                    def create(inner_self: Any, **kwargs: Any) -> Any:
                        response = client.responses.create(**kwargs, max_output_tokens=1200)
                        usage = response.usage
                        inner_self.amount = (usage.input_tokens + 5 * usage.output_tokens) / 1e6
                        self.budget.charge("openai", inner_self.amount)
                        inner_self.model = response.model
                        return response

                proxy = Responses()
                draft = OpenAIQuestionWriter(model="gpt-6.1-terra", client=type("Client", (), {"responses": proxy})())(
                    samples
                )
                return {"draft": draft, "cost": proxy.amount, "model": proxy.model}
            except BudgetExceeded:
                raise
            except Exception as error:
                return {"error": _safe_error(error), "cost": getattr(locals().get("proxy"), "amount", 0.0)}

        result = self.writer_cache.get_or_call(payload, call)
        self.costs["openai"] += result["cost"]
        if "error" in result:
            raise ValueError(result["error"])
        if result["model"] != "gpt-6.1-terra":
            raise ValueError(f"writer model mismatch: {result['model']}")
        return result["draft"]

    def decide(self, state: dict[str, Any], question: Any) -> dict[str, Any]:
        payload = {"model": "jev-1.14.0", "state": state, "question": question.to_contract()}

        def call() -> dict[str, Any]:
            bound = (len(json.dumps(payload, ensure_ascii=False).encode()) + 4096) * 0.042 / 1e6
            if self.prior["typesafe"] + self.budget.spent["typesafe"] + bound > 3:
                raise BudgetExceeded("TypeSafe budget would be exceeded")
            try:
                if self.jev is None:
                    self.jev = som.TypeSafe("jev-1.14.0", max_retries=0)
                decision = self.jev.decide(state, [question])
                amount = decision.envelope.cost.amount
                if amount is None:
                    raise ValueError("missing cost")
                self.budget.charge("typesafe", amount)
                model = decision.envelope.implementation.model if decision.envelope.implementation else None
                return {"answer": answer_to_dict(decision.answers[question.name]), "cost": amount, "model": model}
            except BudgetExceeded:
                raise
            except Exception as error:
                return {"error": _safe_error(error), "cost": 0.0}

        result = self.jev_cache.get_or_call(payload, call)
        self.costs["typesafe"] += result["cost"]
        if "answer" in result and result["model"] != "jev-1.14.0":
            raise ValueError(f"Jev model mismatch: {result['model']}")
        return result


def _prefix(episode: Any) -> list[dict[str, str]]:
    for turn in episode.turns:
        if turn.role == "user" and turn.content:
            return [{"role": "user", "content": turn.content[-2000:]}]
    return []


def writer_candidate(candidate: Any, episodes: list[Any]) -> Any:
    examples = []
    if candidate.kind == "tool_argument":
        for episode in episodes:
            for row in instances(episode, candidate):
                examples.append(Example(episode.episode_id, row["state"]["transcript"], row["teacher"]))
    else:
        for episode in episodes:
            called = any(call.name == candidate.tool for turn in episode.turns for call in turn.tool_calls)
            examples.append(Example(episode.episode_id, _prefix(episode), called))
    values = list(dict.fromkeys(json.dumps(e.value, sort_keys=True) for e in examples))
    return replace(candidate, examples=examples, values=[json.loads(v) for v in values])


def _flatten_summary(row: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    for key, value in summary.items():
        if isinstance(value, dict):
            for subkey, subvalue in value.items():
                row[f"{key}_{subkey}"] = subvalue
        else:
            row[key] = value
    return row


def run(mode: str) -> None:
    directory = Path("bench/results/e3b") / RUN_ID
    directory.mkdir(parents=True, exist_ok=True)
    calls = Calls(mode, directory)
    rules = labels()
    manifest = Manifest("e3b", RUN_ID, {"tau2_commit": COMMIT, "mode": mode, "min_support": 10, "seed": 0})
    manifest.config["source_sha256"] = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in ("PROTOCOL.md", "decision_labels.yaml", "data.py", "extract.py", "metrics.py", "run.py")
    }
    mining_rows: list[dict[str, Any]] = []
    discovery_rows: list[dict[str, Any]] = []
    questions: list[dict[str, Any]] = []
    all_rows: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    failures: list[str] = []
    curves: list[tuple[str, Any, Any]] = []
    for domain in DOMAINS:
        if mode == "replay":
            for model in MODELS:
                from bench.common.data import DATA_DIR

                if not (DATA_DIR / "tau2" / file_name(model, domain)).exists():
                    raise FileNotFoundError(f"offline replay needs cached tau2 data: {file_name(model, domain)}")
        for model in MODELS:
            path = fetch(model, domain)
            manifest.data[f"tau2/{path.name}"] = hashlib.sha256(path.read_bytes()).hexdigest()
        training = list(load(TRAIN, domain))
        held = [episode for model in HELD_OUT for episode in load(model, domain)]
        report = mine([to_trace(e) for e in training], min_support=10)
        for row in report.to_rows():
            mining_rows.append({"domain": domain, **row})
        candidates = report.accepted + report.rejected
        expected = [c.name for c in candidates if judgement(rules[domain], c)]
        predicted = [c.name for c in report.accepted]
        discovery_rows.append(
            {"domain": domain, "candidates": len(candidates), **discovery_metrics(predicted, expected)}
        )
        discovery_rows[-1]["ambiguous_retrieval_count"] = report.ambiguous_retrieval_count
        discovery_rows[-1]["precision_ci"] = wilson(
            discovery_rows[-1]["tp"], discovery_rows[-1]["tp"] + discovery_rows[-1]["fp"]
        )
        discovery_rows[-1]["recall_ci"] = wilson(
            discovery_rows[-1]["tp"], discovery_rows[-1]["tp"] + discovery_rows[-1]["fn"]
        )
        for c in candidates:
            # Candidate-level truth is preserved alongside the complete miner output.
            row = next(r for r in mining_rows if r["domain"] == domain and r["name"] == c.name and r["kind"] == c.kind)
            row["judgement"] = judgement(rules[domain], c)
        for candidate in report.accepted:
            if not judgement(rules[domain], candidate):
                continue
            label = f"{domain}/{candidate.name}"
            writing = [e for e in training if not calibration(domain, e.task_id)]
            cal_episodes = [e for e in training if calibration(domain, e.task_id)]
            source = writer_candidate(candidate, writing)
            try:
                question, provenance = write_question(source, calls.writer, n_samples=20, seed=0)
            except (BudgetExceeded, CacheMiss):
                raise
            except Exception as error:
                failures.append(f"{label}: writer failed ({_safe_error(error)})")
                questions.append({"domain": domain, "candidate": candidate.name, "error": _safe_error(error)})
                continue
            provenance["writer"] = "gpt-6.1-terra"
            questions.append(
                {
                    "domain": domain,
                    "candidate": candidate.name,
                    "question": question.to_contract(),
                    "provenance": provenance,
                }
            )
            if candidate.kind != "tool_argument":
                failures.append(f"{label}: episode-wide branch has no defensible decision boundary; not evaluated")
                continue
            train_values = [str(example.value) for example in source.examples]
            majority = Counter(train_values).most_common(1)[0][0] if train_values else None
            calibration_rows = [row for e in cal_episodes for row in instances(e, candidate)]
            eval_rows = [row for e in held for row in instances(e, candidate)]
            for row in calibration_rows + eval_rows:
                result = calls.decide(row["state"], question)
                answer = answer_from_dict(result["answer"]) if "answer" in result else None
                row["prediction"] = answer.value if answer else None
                row["signal"] = answer.top_probability if answer else None
                row["error"] = (
                    result.get("error", "") if answer is None else ("refusal" if answer.value is None else "")
                )
                row["teacher"] = str(row["teacher"])
                row["gold"] = str(row["gold"]) if row["gold"] is not None else None
            valid_cal = [r for r in calibration_rows if r["prediction"] is not None and r["signal"] is not None]
            threshold = calibrate_threshold(
                [r["signal"] for r in valid_cal], [r["prediction"] == r["teacher"] for r in valid_cal]
            )
            for row in eval_rows:
                row["threshold"] = threshold if math.isfinite(threshold) else None
                row["served"] = row["signal"] is not None and row["signal"] >= threshold
                row["majority"] = majority
            all_rows.extend(eval_rows)
            valid = [r for r in eval_rows if r["prediction"] is not None and r["signal"] is not None]
            confidence = [r["signal"] for r in valid]
            correct = [r["prediction"] == r["teacher"] for r in valid]
            coverage, risk = risk_coverage(confidence, correct)
            if len(coverage):
                curves.append((label, coverage, risk))
            gold_valid = [r for r in valid if r["gold"] is not None]
            gold_confidence = [r["signal"] for r in gold_valid]
            gold_correct = [r["prediction"] == r["gold"] for r in gold_valid]
            gold_coverage, gold_risk = risk_coverage(gold_confidence, gold_correct)
            if len(gold_coverage):
                curves.append((f"{label} (gold)", gold_coverage, gold_risk))
            summary = summary_metrics(
                [r["prediction"] for r in eval_rows],
                [r["teacher"] for r in eval_rows],
                [r["gold"] for r in eval_rows],
                [f"{domain}/{r['task_id']}" for r in eval_rows],
                training_majority=majority,
            )
            served = [r for r in eval_rows if r["served"]]
            errors = sum(r["prediction"] != r["teacher"] for r in served)
            served_gold = [r for r in served if r["gold"] is not None]
            gold_errors = sum(r["prediction"] != r["gold"] for r in served_gold)
            summaries.append(
                _flatten_summary(
                    {
                        "domain": domain,
                        "candidate": candidate.name,
                        "calibration_n": len(valid_cal),
                        "threshold": threshold if math.isfinite(threshold) else None,
                        "threshold_coverage": len(served) / len(eval_rows) if eval_rows else None,
                        "threshold_coverage_ci": wilson(len(served), len(eval_rows)),
                        "threshold_risk": errors / len(served) if served else None,
                        "threshold_risk_ci": wilson(errors, len(served)),
                        "aurc": aurc(confidence, correct),
                        "aurc_ci": aurc_cluster_bootstrap(
                            confidence, correct, [f"{domain}/{r['task_id']}" for r in valid]
                        ),
                        "gold_aurc": aurc(gold_confidence, gold_correct),
                        "gold_aurc_ci": aurc_cluster_bootstrap(
                            gold_confidence, gold_correct, [f"{domain}/{r['task_id']}" for r in gold_valid]
                        ),
                    },
                    summary,
                )
            )
            summaries[-1]["threshold_gold_n"] = len(served_gold)
            summaries[-1]["threshold_gold_risk"] = gold_errors / len(served_gold) if served_gold else None
            summaries[-1]["threshold_gold_risk_ci"] = wilson(gold_errors, len(served_gold))
    totals = {key: sum(row[key] for row in discovery_rows) for key in ("candidates", "tp", "fp", "fn")}
    totals["precision"] = totals["tp"] / (totals["tp"] + totals["fp"]) if totals["tp"] + totals["fp"] else float("nan")
    totals["recall"] = totals["tp"] / (totals["tp"] + totals["fn"]) if totals["tp"] + totals["fn"] else float("nan")
    totals["precision_ci"] = wilson(totals["tp"], totals["tp"] + totals["fp"])
    totals["recall_ci"] = wilson(totals["tp"], totals["tp"] + totals["fn"])
    discovery_rows.append({"domain": "pooled", **totals})
    if all_rows:
        clusters = [f"{row['domain']}/{row['task_id']}" for row in all_rows]
        pooled = summary_metrics(
            [row["prediction"] for row in all_rows],
            [row["teacher"] for row in all_rows],
            [row["gold"] for row in all_rows],
            clusters,
            training_majority=None,
        )
        for reference in ("teacher", "gold"):
            baseline = summary_metrics(
                [row["majority"] for row in all_rows],
                [row["teacher"] for row in all_rows],
                [row["gold"] for row in all_rows],
                clusters,
                training_majority=None,
            )
            pooled[f"majority_{reference}"] = baseline[reference]
        valid = [row for row in all_rows if row["prediction"] is not None and row["signal"] is not None]
        confidence = [row["signal"] for row in valid]
        correct = [row["prediction"] == row["teacher"] for row in valid]
        coverage, risk = risk_coverage(confidence, correct)
        if len(coverage):
            curves.append(("pooled", coverage, risk))
        gold_valid = [r for r in valid if r["gold"] is not None]
        gold_confidence = [r["signal"] for r in gold_valid]
        gold_correct = [r["prediction"] == r["gold"] for r in gold_valid]
        gold_coverage, gold_risk = risk_coverage(gold_confidence, gold_correct)
        if len(gold_coverage):
            curves.append(("pooled (gold)", gold_coverage, gold_risk))
        served = [row for row in all_rows if row["served"]]
        errors = sum(row["prediction"] != row["teacher"] for row in served)
        served_gold = [r for r in served if r["gold"] is not None]
        gold_errors = sum(r["prediction"] != r["gold"] for r in served_gold)
        summaries.append(
            _flatten_summary(
                {
                    "domain": "pooled",
                    "candidate": "all",
                    "threshold": None,
                    "threshold_coverage": len(served) / len(all_rows),
                    "threshold_coverage_ci": wilson(len(served), len(all_rows)),
                    "threshold_risk": errors / len(served) if served else None,
                    "threshold_risk_ci": wilson(errors, len(served)),
                    "threshold_gold_n": len(served_gold),
                    "threshold_gold_risk": gold_errors / len(served_gold) if served_gold else None,
                    "threshold_gold_risk_ci": wilson(gold_errors, len(served_gold)),
                    "aurc": aurc(confidence, correct),
                    "aurc_ci": aurc_cluster_bootstrap(
                        confidence, correct, [f"{r['domain']}/{r['task_id']}" for r in valid]
                    ),
                    "gold_aurc": aurc(gold_confidence, gold_correct),
                    "gold_aurc_ci": aurc_cluster_bootstrap(
                        gold_confidence, gold_correct, [f"{r['domain']}/{r['task_id']}" for r in gold_valid]
                    ),
                },
                pooled,
            )
        )
    curve_rows = [
        {"decision": label, "coverage": float(x), "risk": float(y)}
        for label, coverage, risk in curves
        for x, y in zip(coverage, risk, strict=True)
    ]
    csv_write(directory / "risk_coverage.csv", curve_rows, fields=["decision", "coverage", "risk"])
    csv_write(directory / "mining_report.csv", mining_rows)
    csv_write(directory / "discovery.csv", discovery_rows)
    csv_write(
        directory / "instances.csv",
        all_rows,
        fields=[
            "domain",
            "candidate",
            "episode_id",
            "model",
            "task_id",
            "state",
            "teacher",
            "gold",
            "prediction",
            "signal",
            "error",
            "majority",
            "threshold",
            "served",
        ],
    )
    csv_write(directory / "summary.csv", summaries)
    (directory / "questions.json").write_text(json.dumps(questions, indent=2, ensure_ascii=False) + "\n")
    with plt.style.context("bench/ieee.mplstyle"):
        fig, ax = plt.subplots()
        for label, x, y in curves:
            ax.plot(x, y, label=label)
        ax.set(xlabel="Coverage", ylabel="Teacher error", xlim=(0, 1), ylim=(0, 1))
        if curves:
            ax.legend(fontsize="small")
        fig.tight_layout()
        fig.savefig(directory / "risk_coverage.pdf")
        fig.savefig(directory / "risk_coverage.png", dpi=200)
        plt.close(fig)
    if mode == "record":
        for cache in (calls.writer_cache, calls.jev_cache):
            (directory / cache.path.name).write_bytes(cache.path.read_bytes() if cache.path.exists() else b"")
    for cache in (calls.writer_cache, calls.jev_cache):
        archive = directory / cache.path.name
        if archive.exists():
            manifest.data[archive.name] = hashlib.sha256(archive.read_bytes()).hexdigest()
    manifest.models = {"writer": "gpt-6.1-terra", "s1": "jev-1.14.0"}
    manifest.counts = {
        "candidates": len(mining_rows),
        "questions": len(questions),
        "instances": len(all_rows),
        "failures": len(failures),
    }
    manifest.cost_usd = dict(calls.costs)
    manifest.config["recorded_unique_call_cost_usd"] = {
        provider: sum(
            json.loads(line)["response"].get("cost", 0.0)
            for line in (directory / cache.path.name).read_text().splitlines()
            if line.strip()
        )
        for provider, cache in (("openai", calls.writer_cache), ("typesafe", calls.jev_cache))
    }
    manifest.new_spend_usd = calls.budget.summary()
    manifest.cache = {
        "writer": {"hits": calls.writer_cache.hits, "misses": calls.writer_cache.misses},
        "jev": {"hits": calls.jev_cache.hits, "misses": calls.jev_cache.misses},
    }
    manifest.notes = failures
    manifest.write()
    errors = Counter(row["error"] for row in all_rows if row["error"])
    lines = [
        "# E3b analysis",
        "",
        "## Discovery",
        "",
        *[
            f"- {r['domain']}: {r['tp']} TP, {r['fp']} FP, {r['fn']} FN; "
            f"precision {r['precision']:.3f} (Wilson {r['precision_ci']}), "
            f"recall {r['recall']:.3f} (Wilson {r['recall_ci']})."
            for r in discovery_rows
        ],
        "",
        "## Evaluation",
        "",
        *[
            f"- {r['domain']}/{r['candidate']}: n={r['n']}; teacher accuracy "
            f"{r['teacher_accuracy']:.3f} (Wilson {r['teacher_wilson_ci']}, "
            f"task-bootstrap {r['teacher_cluster_bootstrap_ci']}); gold accuracy "
            f"{r['gold_accuracy']:.3f} (n={r['gold_n']}, Wilson {r['gold_wilson_ci']}, "
            f"task-bootstrap {r['gold_cluster_bootstrap_ci']}); majority teacher "
            f"{r['majority_teacher_accuracy']:.3f}; AURC {r['aurc']:.3f} "
            f"(task-bootstrap {r['aurc_ci']}); calibrated coverage {r['threshold_coverage']}, "
            f"served error {r['threshold_risk']}."
            for r in summaries
        ],
        "",
        "## Failures and limitations",
        "",
        f"- Held-out API failures/refusals: {dict(errors)}; these are not scored as correct.",
        *[f"- {failure}" for failure in failures],
        "- After the first results were observed, an independent compiler review corrected the miner; "
        "this run uses the corrected compiler and is not a fully pre-registered implementation. "
        "The initial miner yielded 15 TP, 38 FP and 5 FN (precision 0.283, recall 0.750); "
        "the labels and protocol remained frozen.",
        "- Offline replay requires the pinned τ²-bench data files to have been downloaded into bench/data; "
        "the recorded provider-call cache is archived beside these results.",
        "- The preceding assistant text can already communicate the tool argument before the call. "
        "These scores measure recovery at the tool-call boundary, not anticipation before the agent decided.",
        *[
            f"- The {q['candidate']} draft asks about a tracking number, apparently off target."
            for q in questions
            if q["domain"] == "retail"
            and q["candidate"] == "cancel_pending_order.branch"
            and "tracking number" in q.get("question", {}).get("instructions", "").lower()
        ],
        *[
            f"- The {q['candidate']} draft asks about jigsaw returns, apparently off target."
            for q in questions
            if q["domain"] == "retail"
            and q["candidate"] == "modify_pending_order_address.branch"
            and "jigsaw" in q.get("question", {}).get("instructions", "").lower()
        ],
        "- All rewards included; reward filtering would bias results. Published trajectories use a user simulator, "
        "not real customers. Teacher choices and gold actions can be ambiguous; "
        "missing/conflicting gold is not scored.",
        "- Episode-wide branches lack a defensible decision boundary and are not evaluated. Confirmation and "
        "multiclass action choices are not miner candidates; candidate-universe recall does not measure them.",
        "- Repeated trials and shared tasks limit independence. Model transfer is not task generalization; "
        "public data contamination is possible. Wilson intervals assume independent observations; task-cluster "
        "bootstrap intervals account for repeated task observations.",
    ]
    (directory / "ANALYSIS.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("record", "replay"), default="replay")
    args = parser.parse_args()
    run(args.mode)


if __name__ == "__main__":
    main()
