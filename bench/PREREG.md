# E3a preregistration

## Scope and provenance

The v2 environment has `search_policy(query)` return up to five ID/title pairs, followed by
`get_policy(entry_id)` to read the routing fields. The free-form lookup choice is D1; the
verify-identity branch is D2. The pilot and all tuning use only the disjoint development pool;
evaluation comprises control, 15% restructure, and CLINC traffic shift for each of
the three frozen 2,400-ticket streams, with shift after ticket 1,199. The 5% and 30%
restructure and visible-prompt conditions are dropped for budget, not evaluation results.
Restructure severity is the fraction of post-shift tickets moved to split entries; a synthetic
cohort marker makes those entries identifiable.

After the Luna pilot, estimated cumulative OpenAI spend was $15.1298 of $75 and TypeSafe spend
$1.8431 of $5. Assuming shared pre-shift cache hits across each paired condition,
the three-condition design needs approximately 14,400 distinct teacher tickets and
600 extra variance draws. At the Terra joint-dev mean $0.00291197 per ticket with
20% margin, the projected agent-only cost is $52.4155, or $67.5453 cumulative.
This excludes writer calls and unanticipated cache misses; those and any new dev spend
consume the remaining headroom. The runner must abort, record and report on budget
exhaustion, not silently sample or truncate. Provider-side spending limits are needed
to guarantee billed dollars, since reported usage and list prices are estimates.

The analysis/simulation code is `bench/e3a/run.py` and related modules at git SHA `b5d36171b849454c879a87509de514ba3561f454`;
the development run's git SHA is `bf64e6d7ee38e00a70596d5a2cdf66f90e1e31a5`, with manifest at `bench/results/e3a/dev-tuning-joint/manifest.json`.
TypeSafe `jev-1.14.0` is S1,
Responses `gpt-6.1-terra` (low reasoning) is agent and writer, and Ollama `embeddinggemma` plus
logistic regression is the local surrogate. Responses and embeddings are cached and retain
original usage-weighted list-price cost and latency. The unpriced hardware/energy cost of local
inference is a limitation.

On the same 100 v2 pilot tickets, Luna achieved 68% joint gold accuracy (95%
Wilson 58.3%–76.3%) at $0.000295/ticket; Terra achieved 78% (68.9%–85.0%)
at $0.002948/ticket. The paired Luna-minus-Terra difference was −10 percentage
points (95% ticket-paired bootstrap interval −18 to −3 points; 100,000 resamples,
seed 20261122). Luna alone was correct on three tickets and Terra alone on 13.
The preselected Luna GO criterion was point accuracy at least 73%; Luna failed,
so no Luna development rerun was performed. Pilot results are in
`bench/results/e3a/pilot-v2-luna/`.

The policy fixes identity by entry. In 972 routed pre-control dev traces, the teacher agreed with
the entry policy on 946 (97.3%); 26 minority deviations occurred across 21 of 77 entries. The dev
miner still accepted the identity branch rather than rejecting it as a functional dependency,
apparently because of teacher noise. This false negative is reported, not corrected in the miner.
The lifecycle asks S1 only D1 and learns D1-to-D2 by majority vote on its own training traces;
ties and unseen entries escalate. Shadow validation and audits score the joint D1 plus mapped D2
outcome against the teacher, and the e-process monitors this same joint error. D1-only, D2-only
and joint teacher agreement are reported separately.

## Frozen parameters

- Warm-up W=300; disjoint calibration and validation windows n_cal=400,
  n_val=400; risk target epsilon=0.15; per-stream alpha=0.05;
  max one promotion attempt per compilation. The dev warm-up contains 77 distinct
  gold intents; these labels are used only to assess diversity, never provided to the miner or writer.
  With complete shadow labels the first promotion is recorded on ticket index 1,099;
  the earliest compiled service is index 1,100. Thus at most 100 tickets can be
  compiled before the shift at 1,200, and fewer will be served when the gate
  escalates, mappings are missing or promotion is delayed or fails. An optimistic
  dev bootstrap projects about 45 served tickets in those 100 opportunities:
  351/500 promotion replicates, with mean 64.6% threshold coverage among promoted
  replicates, resampled from the 569 matched shadow observations. This assumes
  promotion at the earliest opportunity and that all 100 post-promotion tickets
  resemble that selected matched pool; missing mappings and delays can lower it.
  It is not a measured full-lifecycle estimate.
  H4 therefore primarily measures post-shift behaviour of decisions promoted
  shortly before the shift.
- The question writer receives at most 20 sampled trace examples and at most 2,048 output tokens.
  Choice questions request only name/instructions; branch questions additionally request true/false
  descriptions. A malformed or incomplete structured response gets one retry using a different
  deterministic sampling seed; if both fail, the compile fails and the agent continues serving.
  Both attempts' list-price costs and latency are charged to that arm; incomplete responses are
  retained, not repaired.
- Calibration rule `margin`; margin rule uses empirical calibration error at most
  0.6 epsilon; an independent one-sided Clopper-Pearson validation bound controls promotion.
  Recompilation allocates alpha / [2(g+1)(g+2)] to each decision in generation g=0,1,... .
  E-process uses the package's nine-component mixture and tests at the allocated alpha.
- Gate signal: top probability (`probability`). In E2, vendor confidence ranked
  identically and therefore had identical AURC; margin differed by less than 0.001
  AURC in mixed directions (Banking77 Jev: 0.0630 probability vs 0.0638 margin;
  CLINC Jev: 0.0508 vs 0.0498). Source: `bench/results/e2/full/ANALYSIS.md`
  on `origin/main`.
- Audit rate a=1.00. The dev-only selection maximizes the product of estimated
  promotion probability and conditional detection probability, subject to epsilon
  at most 0.20. With 400+400 windows and margin calibration the grid is:

  | epsilon | audit | P(promote) | P(detect given promotion) | product |
  |---|---:|---:|---:|---:|
  | 0.10 | 0.30 | 0.528 | 0.522 | 0.276 |
  | 0.10 | 0.60 | 0.528 | 0.894 | 0.472 |
  | 0.10 | 1.00 | 0.528 | 0.992 | 0.524 |
  | 0.15 | 0.30 | 0.732 | 0.142 | 0.104 |
  | 0.15 | 0.60 | 0.732 | 0.432 | 0.316 |
  | 0.15 | 1.00 | 0.732 | 0.750 | 0.549 |
  | 0.20 | 0.30 | 0.874 | 0.028 | 0.024 |
  | 0.20 | 0.60 | 0.874 | 0.070 | 0.061 |
  | 0.20 | 1.00 | 0.874 | 0.168 | 0.147 |

  Promotion is based on 500 bootstrap resamples of 569 matched dev shadow tickets;
  detection uses a separate 500-run simulation of a synthetic successful promotion.
  At the selected setting, promotion was 366/500 (Wilson 0.692–0.769) and
  detection 375/500 (Wilson 0.710–0.786). Multiplication is an extrapolation,
  not measured end-to-end power, and bootstrap reuse can be optimistic. Conditional
  observed joint teacher error was 0.0698 pre-shift and 0.3946 post-shift on 86 and
  223 served tickets; pre-shift coverage was 0.086. These data were generated with
  epsilon=0.10 and 250+250 windows, not the selected settings. The simulation assumes
  independent Bernoulli errors, constant coverage, alpha=0.0125 and a 1,200-ticket
  post-shift horizon. Unseen mappings can defer promotion beyond the shift.
- Refit cadence R=200; training window W and fixed per-epoch subsampling.
  Equal TRAINING-LABEL budget means the same number of teacher-labelled tickets available to
  fit/recompile each S1 question or surrogate per epoch, via fixed per-epoch subsampling with the
  same seed. Every escalation, audit and shadow agent call is costed separately; total agent calls
  may differ and are reported.
  Pseudorandom operations use base seed 20261122 plus the evaluation stream seed (11, 23 or 37);
  the same stream seed is used for paired shift conditions.
- kNN uses prior-only sequential warm-up predictions and the lowest similarity threshold
  with empirical error at most epsilon; audit disagreement invalidates the cache.
  This is a tuning rule, not a risk guarantee.
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
Report component accuracy, D1-only, D2-only and joint agreement, agent calls, all cost lines,
latency and coverage,
detection delay including misses, no-shift false demotions, discovery precision/recall, recovery and
amortization.

The arms are always-agent, S1 with audit/demotion, S1 refit-only, escalation-only,
fixed gate, fixed gate with configuration-hash invalidation, oracle audit, kNN cache,
and local-surrogate audit and refit. They replay the same teacher trajectory per
stream; an audit may replace a compiled answer with the paired teacher answer.

H1 (discovery): the miner identifies the free-form policy-retrieval choice and the
identity-verification branch as decision candidates while rejecting distractors.
The primary endpoints are candidate-level precision and recall against the two
hand-labelled decision types, reported with accepted/rejected reasons and ambiguous
retrievals. The noisy identity functional-dependency false negative is reported.

H2 (risk control): among promoted compiled decisions, the selective joint D1+D2
teacher-disagreement rate is at most the frozen risk target. The primary endpoint is
the number and proportion of promoted generations whose independent validation
one-sided Clopper–Pearson bound is below the target. Also report observed served
joint error and audit counts; a failure to promote is not a zero-error success.
The guarantee depends on the sampling and stationarity assumptions and does not
establish gold correctness or a post-shift risk guarantee.

H3 (primary): on control tickets 1,200–2,399, S1-question plus audit is non-inferior
to always-agent in paired joint gold accuracy by a 2-point margin, using a
seed-stratified ticket-cluster bootstrap. Report the served subset separately;
it is selected and descriptive, not the primary estimand. H3 has no cost condition.

As a secondary analysis, replay S1 audit/demotion at audit rates 0.10, 0.30,
0.60 and 1.00 on the same teacher trajectories. For each rate report cost per
ticket relative to always-agent, shift detection delay and misses, and no-shift
false demotions. At 1.00 every compiled ticket is also audited by the agent, so
this arm tests risk control rather than savings. After all primary arms finish,
secondary replays share the teacher trajectories but may make new S1 and writer
calls; those costs are booked to the corresponding arm. They use the same hard
budget limits and stop with a recorded reason if a cap prevents completion.

H4 (primary): for 15% restructure, S1 plus audit/demotion has lower cumulative excess
error over tickets 1,200-2,399 than refit-only and escalation-only monitoring. For every ticket,
the outcome is the served route's gold-correctness indicator, including escalated and audited
tickets. Use a one-sided paired ticket sign-flip permutation test stratified by seed and Holm
correction across the two comparisons within each severity. Report ticket-cluster bootstrap
intervals stratified by seed, per-seed cumulative effects and whether all three effects have the
same positive sign as a secondary consistency criterion. An exact seed-level sign-flip test would
have minimum one-sided p=1/8 with three seeds, motivating the ticket-level primary analysis.
Ticket-level randomization assumes exchangeable paired differences; adaptive state and temporal
dependence may make its uncertainty anti-conservative, so per-seed results remain essential.

These promotion/detection estimates do not quantify H1–H4 test power; the latter
is unknown and the three-seed experiment may be underpowered. Traffic shift is
exploratory, not another member of the primary H4 family.

The run and cost accounting are in `bench/e3a/run.py`, `collect.py`, `providers.py`
and `spend.py`; lifecycle and mapping in `lifecycle_runner.py`; metrics in
`metrics.py`; paired H3/H4 analyses in `hypotheses.py`; development-only bootstrap
and detection simulations in `promotion_grid.py` and `power_grid.py`. Results and
manifests are retained under `bench/results/e3a/`.

H5 (exploratory): compare S1-question and surrogate under the equal training-label rule. No
evaluation stream is used to choose a parameter. The provider dashboard will be reconciled if
exports are available; otherwise it remains explicitly unreconciled. Public benchmark contamination,
synthetic policy/marker, teacher error and selective escalation labels are threats to validity.
