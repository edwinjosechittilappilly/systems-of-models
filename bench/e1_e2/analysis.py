"""Reproducible paired E1/E2 analyses; all fitting uses calibration only."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from bench.common.data import DATA_DIR, label_names
from bench.common.stats import aurc, auroc, brier, ece, nll, paired_difference, risk_coverage, wilson
from bench.e1_e2.calibration import apply_isotonic, apply_temperature, fit_isotonic, fit_temperature
from bench.e1_e2.metrics import cascade_sweep, choose_joint_threshold, choose_threshold, paired_aurc_difference

GRID = np.linspace(0, 1, 101)
RULE = (
    "for each S1 and metric, tau* = the smallest tau on the FULL calibration split whose S1 selective accuracy "
    "among served items (signal >= tau) is >= A2 - 0.01; if none qualifies, tau* = 1.0 (always escalate). "
    "Report coverage at tau*. Then apply tau* unchanged on test."
)


def prediction(frame):
    result = np.where(frame.fit_answer == False, "oos", frame.answer)  # noqa: E712
    return np.where((frame.dataset == "clinc150") & frame.fit_answer.isna(), None, result)


def with_signals(frame):
    frame = frame.copy()
    frame["prediction"] = prediction(frame)
    frame["correct"] = frame.prediction == frame.gold

    def margin(value):
        values = sorted(json.loads(value).values(), reverse=True)
        return values[0] - values[1] if len(values) >= 2 else np.nan

    frame["margin"] = frame.probabilities.map(margin)
    missing_fit = (frame.dataset == "clinc150") & frame.fit_answer.isna()
    frame.loc[missing_fit, ["top_probability", "confidence", "margin"]] = np.nan
    return frame


def plot_save(fig, root, name):
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(root / f"{name}.{ext}", dpi=180)
    plt.close(fig)


def e1(raw, root):
    raw.drop(columns="probabilities").to_csv(root / "items.csv", index=False)
    sweeps, selected, baselines = [], [], []
    fig, ax = plt.subplots()

    def add_baseline(dataset, system, frame):
        low, high = wilson(int(frame.correct.sum()), len(frame))
        baselines.append(
            {
                "dataset": dataset,
                "system": system,
                "n": len(frame),
                "accuracy": float(frame.correct.mean()),
                "accuracy_ci_low": low,
                "accuracy_ci_high": high,
                "cost_per_request": float(frame.cost.mean()),
                "cost_basis": ",".join(sorted(frame.cost_basis.unique())),
                "latency_p50": float(frame.latency_ms.quantile(0.5)),
                "latency_p95": float(frame.latency_ms.quantile(0.95)),
            }
        )

    for dataset in ("banking77", "clinc150"):
        sub = raw[raw.dataset == dataset]
        teacher_cal = with_signals(sub[(sub.system == "s2") & (sub.split == "calibration")])
        teacher = with_signals(sub[(sub.system == "s2") & (sub.split == "test")]).sort_values("item_id")
        a2 = teacher_cal.correct.mean()
        teacher_low, teacher_high = wilson(int(teacher.correct.sum()), len(teacher))
        add_baseline(dataset, "s2", teacher)
        for system in ("typesafe", "decisions"):
            cal_base = sub[(sub.system == system) & (sub.split == "calibration")].sort_values("item_id")
            test_base = sub[(sub.system == system) & (sub.split == "test")].sort_values("item_id")
            cal, test = with_signals(cal_base), with_signals(test_base)
            if not np.array_equal(test.item_id, teacher.item_id):
                raise ValueError("S1 and teacher test items are not paired")
            add_baseline(dataset, system, test)
            arms = [
                (metric, "fit_and_choice" if dataset == "clinc150" else "choice_only")
                for metric in ("top_probability", "confidence", "margin")
            ]
            if dataset == "clinc150":
                arms.append(("top_probability", "choice_only_sensitivity"))
            for metric, policy in arms:
                sensitivity = policy == "choice_only_sensitivity"
                cal_signal = cal_base[metric] if sensitivity else cal[metric]
                test_signal = test_base[metric] if sensitivity else test[metric]
                cal_correct = cal_base.answer == cal_base.gold if sensitivity else cal.correct
                test_correct = test_base.answer == test_base.gold if sensitivity else test.correct
                c1 = test_base.choice_cost if sensitivity else test.cost
                l1 = test_base.choice_latency_ms if sensitivity else test.latency_ms
                observed = np.asarray(cal_signal, dtype=float)
                grid = np.unique(observed[np.isfinite(observed)])
                if dataset == "clinc150" and not sensitivity:
                    tau, fit_tau, coverage, fallback = choose_joint_threshold(
                        cal_signal, cal.fit_probability, cal_correct, a2
                    )
                    test_fit = test.fit_probability.to_numpy(float)
                else:
                    tau, coverage, fallback = choose_threshold(cal_signal, cal_correct, a2, grid)
                    fit_tau, test_fit = None, None
                sweep = cascade_sweep(
                    test_signal,
                    test_correct,
                    teacher.correct,
                    c1,
                    teacher.cost,
                    l1,
                    teacher.latency_ms,
                    grid,
                    fit_probability=test_fit,
                    fit_threshold=fit_tau if fit_tau is not None else 0.0,
                )
                sweep.insert(0, "gate_policy", policy)
                sweep.insert(0, "metric", metric)
                sweep.insert(0, "system", system)
                sweep.insert(0, "dataset", dataset)
                sweeps.append(sweep)
                signal = np.asarray(test_signal, dtype=float)
                escalate = np.ones(len(test), dtype=bool) if fallback else ~np.isfinite(signal) | (signal < tau)
                if test_fit is not None:
                    escalate |= ~np.isfinite(test_fit) | (test_fit < fit_tau)
                correct = np.where(escalate, teacher.correct, test_correct)
                loss, low, high = paired_difference(teacher.correct.astype(float), correct.astype(float))
                cost = np.mean(c1.to_numpy() + np.where(escalate, teacher.cost, 0))
                accuracy_low, accuracy_high = wilson(int(np.sum(correct)), len(correct))
                selected.append(
                    {
                        "dataset": dataset,
                        "system": system,
                        "metric": metric,
                        "gate_policy": policy,
                        "tau": tau,
                        "fit_threshold": fit_tau,
                        "fallback_always_escalate": fallback,
                        "calibration_coverage": coverage,
                        "teacher_calibration_accuracy": a2,
                        "calibration_teacher_n": len(teacher_cal),
                        "accuracy": float(np.mean(correct)),
                        "s2_accuracy": float(teacher.correct.mean()),
                        "s2_accuracy_ci_low": teacher_low,
                        "s2_accuracy_ci_high": teacher_high,
                        "accuracy_ci_low": accuracy_low,
                        "accuracy_ci_high": accuracy_high,
                        "loss": loss,
                        "loss_ci_low": low,
                        "loss_ci_high": high,
                        "non_inferior": high < 0.02,
                        "cost_ratio": cost / teacher.cost.mean(),
                        "h1_pass": high < 0.02 and cost / teacher.cost.mean() < 0.5,
                        "s2_cost_escalated": float(teacher.cost.to_numpy()[escalate].mean())
                        if escalate.any()
                        else np.nan,
                        "s2_cost_all": float(teacher.cost.mean()),
                        "escalation_rate": float(escalate.mean()),
                    }
                )
                if metric == "top_probability" and not sensitivity:
                    ax.plot(sweep.cost_per_request / teacher.cost.mean(), sweep.accuracy, label=f"{dataset} {system}")
                    near = (sweep.escalation_rate - sweep.breakeven_usage_weighted).abs().idxmin()
                    if pd.notna(near):
                        mark = sweep.loc[near]
                        ax.scatter(mark.cost_per_request / teacher.cost.mean(), mark.accuracy, marker="x")
    pd.concat(sweeps, ignore_index=True).to_csv(root / "sweep.csv", index=False)
    pd.DataFrame(selected).to_csv(root / "selected.csv", index=False)
    pd.DataFrame(baselines).to_csv(root / "baselines.csv", index=False)
    ax.set(xlabel="Cascade / S2 cost", ylabel="Accuracy", title="Exploratory test frontier; x = nearest break-even")
    ax.legend(fontsize="x-small")
    plot_save(fig, root, "cost_accuracy")
    return selected


def _choice_matrix(frame, labels):
    valid, probabilities, gold = [], [], []
    index = {name: i for i, name in enumerate(labels)}
    for pos, row in enumerate(frame.itertuples()):
        values = json.loads(row.probabilities)
        vector = np.array([values.get(label, 0.0) for label in labels], dtype=float)
        if row.gold in index and values and np.isfinite(vector).all() and (vector >= 0).all() and vector.sum() > 0:
            valid.append(pos)
            probabilities.append(vector / vector.sum())
            gold.append(index[row.gold])
    return np.array(valid), np.asarray(probabilities), np.asarray(gold, dtype=int)


def score_items(frame, probabilities, labels, dataset, system, question, method):
    """Keep sufficient per-item statistics to audit calibration metrics without huge vectors."""
    index = np.arange(len(labels))
    winner = probabilities.argmax(axis=1)
    p_gold = probabilities[index, labels]
    result = pd.DataFrame(
        {
            "dataset": dataset,
            "system": system,
            "question": question,
            "method": method,
            "item_id": frame.item_id.to_numpy(),
            "gold": frame.gold.to_numpy(),
            "predicted_class_index": winner,
            "gold_class_index": labels,
            "confidence": probabilities[index, winner],
            "correct": winner == labels,
            "gold_probability": p_gold,
            "brier": np.square(probabilities).sum(axis=1) - 2 * p_gold + 1,
            "nll": -np.log(np.clip(p_gold, 1e-6, 1)),
        }
    )
    if question == "fit_predicate":
        result["oos_probability"] = probabilities[:, 0]
    return result


def e2(raw, root):
    with_signals(raw).drop(columns="probabilities").to_csv(root / "items.csv", index=False)
    scores, differences, curves, reliability, scored_items = [], [], [], [], []
    fig, ax = plt.subplots()
    relfig, relax = plt.subplots()
    for dataset in ("banking77", "clinc150"):
        labels = [x for x in label_names(dataset) if x != "oos"]
        for system in ("typesafe", "decisions"):
            sub = raw[(raw.dataset == dataset) & (raw.system == system)]
            cal = with_signals(sub[sub.split == "calibration"])
            test = with_signals(sub[sub.split == "test"])
            for metric in ("top_probability", "confidence", "margin"):
                valid = np.isfinite(test[metric].to_numpy(float))
                if not valid.any():
                    continue
                signal, correct = test.loc[valid, metric].to_numpy(float), test.loc[valid, "correct"].to_numpy(bool)
                coverage, risk = risk_coverage(signal, correct)
                for c, r in zip(coverage, risk, strict=True):
                    curves.append({"dataset": dataset, "system": system, "metric": metric, "coverage": c, "risk": r})
                scores.append(
                    {
                        "dataset": dataset,
                        "system": system,
                        "question": "gate",
                        "method": metric,
                        "n": len(correct),
                        "aurc": aurc(signal, correct),
                    }
                )
                ax.plot(coverage, risk, label=f"{dataset} {system} {metric}")
            valid = np.isfinite(test.top_probability.to_numpy(float)) & np.isfinite(test.confidence.to_numpy(float))
            if valid.any():
                point, low, high = paired_aurc_difference(
                    test.loc[valid, "top_probability"], test.loc[valid, "confidence"], test.loc[valid, "correct"]
                )
                differences.append(
                    {
                        "dataset": dataset,
                        "system": system,
                        "n": int(valid.sum()),
                        "difference": point,
                        "ci_low": low,
                        "ci_high": high,
                        "h2_pass": high < 0,
                    }
                )
            ci, cp, cy = _choice_matrix(cal, labels)
            ti, tp, ty = _choice_matrix(test, labels)
            if len(ci) and len(ti):
                temp = fit_temperature(cp, cy)
                isotonic = fit_isotonic(cp, cy)
                variants = {
                    "raw": tp,
                    "temperature": apply_temperature(tp, temp),
                    "isotonic": apply_isotonic(tp, isotonic),
                }
                for name, p in variants.items():
                    winner = p.argmax(axis=1)
                    conf, correct = p[np.arange(len(p)), winner], winner == ty
                    scores.append(
                        {
                            "dataset": dataset,
                            "system": system,
                            "question": "choice_in_scope",
                            "method": name,
                            "n": len(p),
                            "ece": ece(conf, correct),
                            "brier": brier(p, ty),
                            "nll": nll(p, ty),
                            "temperature": temp if name == "temperature" else np.nan,
                        }
                    )
                    scored_items.append(score_items(test.iloc[ti], p, ty, dataset, system, "choice_in_scope", name))
                    if name == "raw":
                        for group in np.array_split(np.argsort(conf, kind="stable"), min(15, len(conf))):
                            reliability.append(
                                {
                                    "dataset": dataset,
                                    "system": system,
                                    "confidence": conf[group].mean(),
                                    "accuracy": correct[group].mean(),
                                    "n": len(group),
                                }
                            )
                        values = [x for x in reliability if x["dataset"] == dataset and x["system"] == system]
                        relax.plot(
                            [x["confidence"] for x in values],
                            [x["accuracy"] for x in values],
                            marker=".",
                            label=f"{dataset} {system}",
                        )
            if dataset == "clinc150":
                cfit = cal[np.isfinite(pd.to_numeric(cal.fit_probability, errors="coerce"))]
                tfit = test[np.isfinite(pd.to_numeric(test.fit_probability, errors="coerce"))]
                if len(cfit) and len(tfit):
                    cp1, tp1 = cfit.fit_probability.to_numpy(float), tfit.fit_probability.to_numpy(float)
                    cp = np.column_stack((1 - cp1, cp1))
                    tp = np.column_stack((1 - tp1, tp1))
                    cy = (cfit.gold != "oos").to_numpy(int)
                    ty = (tfit.gold != "oos").to_numpy(int)
                    temp = fit_temperature(cp, cy)
                    iso = fit_isotonic(cp, cy)
                    for name, p in (
                        ("raw", tp),
                        ("temperature", apply_temperature(tp, temp)),
                        ("isotonic", apply_isotonic(tp, iso)),
                    ):
                        winner = p.argmax(axis=1)
                        conf = p[np.arange(len(p)), winner]
                        scores.append(
                            {
                                "dataset": dataset,
                                "system": system,
                                "question": "fit_predicate",
                                "method": name,
                                "n": len(p),
                                "ece": ece(conf, winner == ty),
                                "brier": brier(p, ty),
                                "nll": nll(p, ty),
                                "oos_auroc": auroc(p[:, 0], ty == 0) if len(set(ty)) == 2 else np.nan,
                            }
                        )
                        scored_items.append(score_items(tfit, p, ty, dataset, system, "fit_predicate", name))
    pd.DataFrame(scores).to_csv(root / "metrics.csv", index=False)
    pd.DataFrame(differences).to_csv(root / "h2.csv", index=False)
    pd.DataFrame(curves).to_csv(root / "risk_coverage.csv", index=False)
    pd.DataFrame(reliability).to_csv(root / "reliability.csv", index=False)
    pd.concat(scored_items, ignore_index=True).to_csv(root / "calibration_items.csv", index=False)
    ax.set(xlabel="Coverage", ylabel="Selective risk")
    ax.legend(fontsize="xx-small")
    plot_save(fig, root, "risk_coverage")
    relax.plot([0, 1], [0, 1], "k--")
    relax.set(xlabel="Top probability", ylabel="Observed accuracy")
    relax.legend(fontsize="x-small")
    plot_save(relfig, root, "reliability")
    return scores, differences


def analyse(raw, budget, cache_stats):
    plt.style.use("bench/ieee.mplstyle")
    roots = [Path("bench/results/e1/full"), Path("bench/results/e2/full")]
    for root in roots:
        root.mkdir(parents=True, exist_ok=True)
    selected = e1(raw, roots[0])
    scores, diffs = e2(raw, roots[1])
    manifest = {
        "models": {f"{d}/{s}": list(g.model.unique()) for (d, s), g in raw.groupby(["dataset", "system"])},
        "data_sha256": json.loads((DATA_DIR / "CHECKSUMS.json").read_text()),
        "counts": raw.groupby(["dataset", "system", "split"]).size().to_dict(),
        "usage_weighted_cost_usd": raw.groupby(["dataset", "system", "split"]).cost.sum().to_dict(),
        **budget,
        "cache": cache_stats,
    }
    # JSON keys must be strings.
    for field in ("counts", "usage_weighted_cost_usd"):
        manifest[field] = {"/".join(k): v for k, v in manifest[field].items()}
    for root in roots:
        (root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True, default=str) + "\n")
    notes = (
        "\n\nBanking77 and CLINC choice-only sensitivity threshold rule: "
        + RULE
        + "\n\nA2 is measured on a 500-item, proportionally stratified calibration "
        "subset per dataset (seed 0, including CLINC OOS); no test item is used to fit a threshold or calibrator. "
        "The choice question excludes OOS; a negative companion fit predicate produces the OOS decision. "
        "Choice probability metrics are restricted to in-scope items with valid returned probability vectors; "
        "S1 refusals escalate; a refusal in the served answer is incorrect. ECE uses 15 equal-mass bins. "
        "Option descriptions replace "
        "underscores with spaces. Public dataset contamination is possible. Each teacher answer is one sample; "
        "no teacher sampling variance was measured. Provider usage dashboards were not reconciled. "
        "Costs are usage-weighted list prices, not bills. The budget cap is soft and can be exceeded by up to "
        "one in-flight batch; failed HTTP attempts are assumed not billed. Test sweeps and non-Banking77 endpoints "
        "are exploratory. Confidence intervals are unadjusted; Holm correction across H1-H5 requires the other "
        "experiments. "
        "The original CLINC fit question referred to a list it could not see because Jev evaluates questions "
        "independently. That predicate is invalid: only its accompanying Choice answers may be reused. "
        "We reran the S1 predicates with the full intent list, and reran S2 with Choice and corrected predicate. "
        "For CLINC, both thresholds are selected jointly on calibration to maximize served coverage subject to "
        "selective accuracy >= A2 - 0.01; ties choose smallest choice threshold then smallest fit threshold. "
        "The grid comprises observed calibration signal values, without interpolation; test cost uses the "
        "observed per-call costs. The choice-only sensitivity row turns the fit gate off and counts OOS "
        "items as incorrect whenever served by S1. "
        "Coverage is a cost proxy, not conditional teacher cost. Escalate if fit probability or choice signal "
        "is missing or below its selected threshold. The E2 risk curves rank by each choice signal alone. "
        "S1 CLINC cost and latency sum the Choice and new predicate calls. Rows marked legacy_bundled "
        "include the unusable old predicate's cost, so are conservative for a fresh choice-only deployment. "
    )
    baseline_table = pd.read_csv(roots[0] / "baselines.csv").to_string(index=False)
    primary = [x for x in selected if x["dataset"] == "banking77" and x["metric"] == "top_probability"]
    primary_summary = "\n".join(
        f"- {x['system']}: H1 {'passes' if x['h1_pass'] else 'does not pass'}; "
        f"paired loss {x['loss']:.4f} (95% CI {x['loss_ci_low']:.4f} to {x['loss_ci_high']:.4f}), "
        f"cost ratio {x['cost_ratio']:.3f}."
        for x in primary
    )
    fallbacks = [
        x["system"]
        for x in selected
        if x["dataset"] == "clinc150"
        and x["metric"] == "top_probability"
        and x["gate_policy"] == "fit_and_choice"
        and x["fallback_always_escalate"]
    ]
    finding = (
        "\n\nCLINC top-probability threshold fell back to always escalating for: "
        + (", ".join(fallbacks) if fallbacks else "none")
        + "."
    )
    h2_note = (
        "\n\nSurprise: probability and vendor confidence produced identical AURCs on all four paired "
        "comparisons; H2 is not supported."
        if diffs and all(x["difference"] == 0 for x in diffs)
        else ""
    )
    (roots[0] / "ANALYSIS.md").write_text(
        "# E1 gate economics\n\n## H1: Banking77 top probability\n\n"
        + primary_summary
        + finding
        + "\n\n## S1-only and S2-only\n\n"
        + baseline_table
        + "\n\n## Selected cascades\n\n"
        + pd.DataFrame(selected).to_string(index=False)
        + notes
    )
    (roots[1] / "ANALYSIS.md").write_text(
        "# E2 calibration\n\n"
        + pd.DataFrame(scores).to_string(index=False)
        + "\n\nH2 paired AURC differences (probability minus confidence):\n\n"
        + pd.DataFrame(diffs).to_string(index=False)
        + h2_note
        + notes
    )
