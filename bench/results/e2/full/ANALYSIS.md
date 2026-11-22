# E2 calibration

  dataset    system        question          method    n     aurc      ece    brier      nll  temperature  oos_auroc
banking77  typesafe            gate top_probability 3080 0.062979      NaN      NaN      NaN          NaN        NaN
banking77  typesafe            gate      confidence 3080 0.062979      NaN      NaN      NaN          NaN        NaN
banking77  typesafe            gate          margin 3080 0.063831      NaN      NaN      NaN          NaN        NaN
banking77  typesafe choice_in_scope             raw 3080      NaN 0.074354 0.298221 1.116355          NaN        NaN
banking77  typesafe choice_in_scope     temperature 3080      NaN 0.134112 0.342211 0.947704     3.676161        NaN
banking77  typesafe choice_in_scope        isotonic 3080      NaN 0.024829 0.299000 1.080880          NaN        NaN
banking77 decisions            gate top_probability 3073 0.079085      NaN      NaN      NaN          NaN        NaN
banking77 decisions            gate      confidence 3073 0.079085      NaN      NaN      NaN          NaN        NaN
banking77 decisions            gate          margin 3073 0.079086      NaN      NaN      NaN          NaN        NaN
banking77 decisions choice_in_scope             raw 3073      NaN 0.082802 0.320211 1.325999          NaN        NaN
banking77 decisions choice_in_scope     temperature 3073      NaN 0.200910 0.399173 1.236357     3.735552        NaN
banking77 decisions choice_in_scope        isotonic 3073      NaN 0.031485 0.315792 1.270660          NaN        NaN
 clinc150  typesafe            gate top_probability 5500 0.050771      NaN      NaN      NaN          NaN        NaN
 clinc150  typesafe            gate      confidence 5500 0.050771      NaN      NaN      NaN          NaN        NaN
 clinc150  typesafe            gate          margin 5500 0.049809      NaN      NaN      NaN          NaN        NaN
 clinc150  typesafe choice_in_scope             raw 4500      NaN 0.017129 0.114144 0.383125          NaN        NaN
 clinc150  typesafe choice_in_scope     temperature 4500      NaN 0.093003 0.143663 0.452875     2.045583        NaN
 clinc150  typesafe choice_in_scope        isotonic 4500      NaN 0.009326 0.114437 0.368018          NaN        NaN
 clinc150  typesafe   fit_predicate             raw 5500      NaN 0.038635 0.091252 0.166326          NaN   0.976239
 clinc150  typesafe   fit_predicate     temperature 5500      NaN 0.021339 0.090258 0.152987          NaN   0.976239
 clinc150  typesafe   fit_predicate        isotonic 5500      NaN 0.018923 0.088372 0.172670          NaN   0.971897
 clinc150 decisions            gate top_probability 5310 0.111656      NaN      NaN      NaN          NaN        NaN
 clinc150 decisions            gate      confidence 5310 0.111656      NaN      NaN      NaN          NaN        NaN
 clinc150 decisions            gate          margin 5310 0.110719      NaN      NaN      NaN          NaN        NaN
 clinc150 decisions choice_in_scope             raw 4486      NaN 0.027824 0.175225 0.515846          NaN        NaN
 clinc150 decisions choice_in_scope     temperature 4486      NaN 0.047211 0.182389 0.542405     1.223767        NaN
 clinc150 decisions choice_in_scope        isotonic 4486      NaN 0.012790 0.174305 0.498932          NaN        NaN
 clinc150 decisions   fit_predicate             raw 5500      NaN 0.107180 0.262442 0.631338          NaN   0.935343
 clinc150 decisions   fit_predicate     temperature 5500      NaN 0.046948 0.233715 0.369829          NaN   0.935343
 clinc150 decisions   fit_predicate        isotonic 5500      NaN 0.026200 0.224459 0.357466          NaN   0.934484

H2 paired AURC differences (probability minus confidence):

  dataset    system    n  difference  ci_low  ci_high  h2_pass
banking77  typesafe 3080         0.0     0.0      0.0    False
banking77 decisions 3073         0.0     0.0      0.0    False
 clinc150  typesafe 5500         0.0     0.0      0.0    False
 clinc150 decisions 5310         0.0     0.0      0.0    False

Surprise: probability and vendor confidence produced identical AURCs on all four paired comparisons; H2 is not supported.

Banking77 and CLINC choice-only sensitivity threshold rule: for each S1 and metric, tau* = the smallest tau on the FULL calibration split whose S1 selective accuracy among served items (signal >= tau) is >= A2 - 0.01; if none qualifies, tau* = 1.0 (always escalate). Report coverage at tau*. Then apply tau* unchanged on test.

A2 is measured on a 500-item, proportionally stratified calibration subset per dataset (seed 0, including CLINC OOS); no test item is used to fit a threshold or calibrator. The choice question excludes OOS; a negative companion fit predicate produces the OOS decision. Choice probability metrics are restricted to in-scope items with valid returned probability vectors; S1 refusals escalate; a refusal in the served answer is incorrect. ECE uses 15 equal-mass bins. Option descriptions replace underscores with spaces. Public dataset contamination is possible. Each teacher answer is one sample; no teacher sampling variance was measured. Provider usage dashboards were not reconciled. Costs are usage-weighted list prices, not bills. The budget cap is soft and can be exceeded by up to one in-flight batch; failed HTTP attempts are assumed not billed. Test sweeps and non-Banking77 endpoints are exploratory. Confidence intervals are unadjusted; Holm correction across H1-H5 requires the other experiments. The original CLINC fit question referred to a list it could not see because Jev evaluates questions independently. That predicate is invalid: only its accompanying Choice answers may be reused. We reran the S1 predicates with the full intent list, and reran S2 with Choice and corrected predicate. For CLINC, both thresholds are selected jointly on calibration to maximize served coverage subject to selective accuracy >= A2 - 0.01; ties choose smallest choice threshold then smallest fit threshold. The grid comprises observed calibration signal values, without interpolation; test cost uses the observed per-call costs. The choice-only sensitivity row turns the fit gate off and counts OOS items as incorrect whenever served by S1. Coverage is a cost proxy, not conditional teacher cost. Escalate if fit probability or choice signal is missing or below its selected threshold. The E2 risk curves rank by each choice signal alone. Per-item CSVs are gzip-compressed with mtime 0; risk curves and supervised sweeps are plain CSV shards. S1 CLINC cost and latency sum the Choice and new predicate calls. Rows marked legacy_bundled include the unusable old predicate's cost, so are conservative for a fresh choice-only deployment.

Task-wide cache-accounted list-price spend (including invalid first CLINC calls): {"openai": 29.145689, "typesafe": 1.640737}. This is not a provider billing reconciliation.
