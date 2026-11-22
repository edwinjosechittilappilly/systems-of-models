"""Derive the E3a preregistration from completed development results only."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict
from pathlib import Path

import pandas as pd
from bench.e3a.power import find_minimum_audit_rate

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "results" / "e3a" / "dev-tuning"


def measured_effect(directory: Path = DEV) -> tuple[float, float, float, dict]:
    """Observed conditional D1 teacher disagreement and coverage, without imputing missing service."""
    control = pd.read_csv(directory / "dev_control_s1_audit.csv")
    shifted = pd.read_csv(directory / "dev_restructure_15_s1_audit.csv")
    shift_at = int(shifted["shift_at"].dropna().iloc[0])
    pre = control[(control["ticket_index"] < shift_at) & (control["served_by"] != "agent")]
    post = shifted[(shifted["ticket_index"] >= shift_at) & (shifted["served_by"] != "agent")]
    parse = {True: True, False: False, "True": True, "False": False}
    before = pre["d1_teacher_agreement"].map(parse).dropna()
    after = post["d1_teacher_agreement"].map(parse).dropna()
    if len(before) < 30 or len(after) < 30:
        raise ValueError(f"insufficient served D1 comparisons: pre={len(before)}, post={len(after)}")
    baseline = 1.0 - before.astype(bool).mean()
    post_error = 1.0 - after.astype(bool).mean()
    coverage = len(pre) / int((control["ticket_index"] < shift_at).sum())
    difference = post_error - baseline
    if difference <= 0:
        raise ValueError(f"development shift did not increase observed conditional error ({difference:.4f})")
    return baseline, difference, coverage, {"n_pre": len(before), "n_post": len(after), "post_error": post_error}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=500)
    args = parser.parse_args()
    manifest = json.loads((DEV / "manifest.json").read_text())
    cfg = manifest["config"]
    baseline, effect, coverage, details = measured_effect()
    if baseline >= cfg["epsilon"]:
        raise RuntimeError("development pre-shift teacher disagreement exceeds the proposed risk target")
    search = find_minimum_audit_rate(
        severity=effect,
        epsilon=cfg["epsilon"],
        alpha=cfg["alpha"] / 4,
        baseline_error=baseline,
        coverage=coverage,
        horizon=1200,
        seed=cfg["seed"],
        repetitions=args.repetitions,
        pre_shift_horizon=600,
        rates=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
    )
    (DEV / "power.json").write_text(
        json.dumps(
            {
                "observed": {"baseline_error": baseline, "effect": effect, "coverage": coverage, **details},
                "minimum_rate": search.minimum_rate,
                "results": [asdict(result) for result in search.results],
            },
            indent=2,
        )
        + "\n"
    )
    if search.minimum_rate is None:
        raise RuntimeError("no tested audit rate achieves >=0.8 power on the lower 95% Monte Carlo bound")
    control = pd.read_csv(DEV / "dev_control_s1_audit.csv")
    reference = pd.read_csv(DEV / "dev_control_always_agent.csv")
    boundary = int(pd.read_csv(DEV / "dev_restructure_15_s1_audit.csv")["shift_at"].dropna().iloc[0])
    numerator = control.loc[control["ticket_index"] < boundary, "cost_usd"].mean()
    denominator = reference.loc[reference["ticket_index"] < boundary, "cost_usd"].mean()
    ratio = numerator / denominator
    bound = math.ceil(float(ratio) * 20) * 5
    sha = manifest["git_sha"]
    text = f"""# E3a preregistration (pending review and tag)

## Scope and provenance

The v2 environment has `search_policy(query)` return up to five ID/title pairs, followed by
`get_policy(entry_id)` to read the routing fields. The free-form lookup choice is D1; the
verify-identity branch is D2. The pilot and all tuning use only the disjoint development pool;
evaluation comprises the three frozen 2,400-ticket Banking77 training streams with shift after
ticket 1,199. The CLINC shift replaces 20% of post-shift tickets with disjoint banking/credit-card
utterances. Restructure severity is the fraction of post-shift tickets moved to split entries;
a synthetic cohort marker makes those entries identifiable. The 5% and visible-prompt streams
are exploratory.

The analysis/simulation code is `bench/e3a/run.py` and related modules at git SHA `{sha}`;
development manifest: `bench/results/e3a/dev-tuning/manifest.json`. TypeSafe `jev-1.14.0` is S1,
Responses `gpt-6.1-terra` (low reasoning) is agent and writer, and Ollama `embeddinggemma` plus
logistic regression is the local surrogate. Responses and embeddings are cached and retain
original usage-weighted list-price cost and latency. The unpriced hardware/energy cost of local
inference is a limitation.

## Frozen parameters

- Warm-up W={cfg["warmup"]}; disjoint calibration and validation windows n_cal={cfg["n_cal"]},
  n_val={cfg["n_val"]}; risk target epsilon={cfg["epsilon"]}; per-stream alpha={cfg["alpha"]};
  max one promotion attempt per compilation.
- Calibration rule `{cfg["tau_rule"]}`; margin rule uses empirical calibration error at most
  0.6 epsilon; an independent one-sided Clopper-Pearson validation bound controls promotion.
  Recompilation allocates alpha / [2(g+1)(g+2)] to each decision in generation g=0,1,... .
  E-process uses the package's nine-component mixture and tests at the allocated alpha.
- Gate signal: **TO-BE-FIXED-FROM-E2** (top probability versus vendor confidence); probability
  was provisional for dev only. Evaluation must not run until E2 and this field are fixed.
- Audit rate a={search.minimum_rate:.2f}, chosen as the smallest of 0.10, 0.20, ..., 1.00 whose
  lower 95% Monte Carlo Wilson bound on power reaches 0.8, using the actual e-process with
  per-decision generation-zero alpha={cfg["alpha"] / 4:.5f}, {args.repetitions} replicates and seed
  {cfg["seed"]}. Conditional dev D1 teacher error was
  {baseline:.4f} before and {baseline + effect:.4f} after 15% restructure, on {details["n_pre"]}
  and {details["n_post"]} served tickets; observed pre-shift coverage was {coverage:.4f}.
  Simulation assumes independent Bernoulli errors, constant coverage and a 1,200-ticket
  post-shift horizon; this is an assumption, not measured power.
- Refit cadence R={cfg["refit_interval"]}; training window W and fixed per-epoch subsampling.
  Equal TRAINING-LABEL budget means the same number of teacher-labelled tickets available to
  fit/recompile each S1 question or surrogate per epoch, via fixed per-epoch subsampling with the
  same seed. Every escalation, audit and shadow agent call is costed separately; total agent calls
  may differ and are reported.
- H3 cost bound X={bound}% of always-agent cost/ticket, the development control ratio rounded up
  to the next five percentage points. kNN uses prior-only sequential warm-up predictions and the
  lowest similarity threshold with empirical error at most epsilon; audit disagreement invalidates
  the cache. This is a tuning rule, not a risk guarantee.
- The fixed developer question is: "Which policy title best matches the customer's request? Select
  the most directly applicable policy." Its choice descriptions are the original frozen policy
  titles; it sees no routing fields. The config-hash arm recompiles when the KB hash changes.
  Silent traffic shifts do not change that hash.
- Teacher noise: on 100 stratified tickets in each of the three control streams (300 total), cache
  three independent agent samples. One randomly chosen sample is shared by all arms and the paired
  reference for that ticket; the unused two draws are booked separately as variance-estimation
  overhead. Samples are not independent replicates of the whole experiment.

## Outcomes and hypotheses

Discovery truth labels are `search_policy.retrieval_choice` (D1) and `verify_identity.branch` (D2);
every other candidate is a distractor. Report all accepted/rejected candidates and ambiguous
retrieval counts. The full always-agent trajectory is the paired reference. Joint gold correctness
requires department, priority and the account-specific verification before routing all to be correct.
Report component accuracy, D1 agreement, agent calls, all cost lines and latency as well as coverage,
detection delay including misses, no-shift false demotions, discovery precision/recall, recovery and
amortization.

H3 (primary): on tickets 600-1,199, S1-question plus audit is non-inferior to always-agent in
paired joint gold accuracy by a 2-point margin, using a ticket-cluster bootstrap pooled across seeds,
and costs at most X% of always-agent per ticket.

H4 (primary): for 15% and 30% restructure, S1 plus audit/demotion has lower cumulative excess
error over tickets 1,200-2,399 than refit-only and escalation-only monitoring. For every ticket,
the outcome is the served route's gold-correctness indicator, including escalated and audited
tickets. Use a one-sided paired ticket sign-flip permutation test stratified by seed and Holm
correction across the two comparisons within each severity. Report ticket-cluster bootstrap
intervals stratified by seed, per-seed cumulative effects and whether all three effects have the
same positive sign as a secondary consistency criterion. An exact seed-level sign-flip test would
have minimum one-sided p=1/8 with three seeds, motivating the ticket-level primary analysis.
Ticket-level randomization assumes exchangeable paired differences; adaptive state and temporal
dependence may make its uncertainty anti-conservative, so per-seed results remain essential.

H5 (exploratory): compare S1-question and surrogate under the equal training-label rule. No
evaluation stream is used to choose a parameter. The provider dashboard will be reconciled if
exports are available; otherwise it remains explicitly unreconciled. Public benchmark contamination,
synthetic policy/marker, teacher error and selective escalation labels are threats to validity.
"""
    (ROOT / "PREREG.md").write_text(text)


if __name__ == "__main__":
    main()
