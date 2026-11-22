# E2 calibration

  dataset    system        question          method    n  n_missing_signals     aurc      ece    brier      nll  temperature  oos_auroc
banking77  typesafe            gate top_probability 3080                0.0 0.062979      NaN      NaN      NaN          NaN        NaN
banking77  typesafe            gate      confidence 3080                0.0 0.062979      NaN      NaN      NaN          NaN        NaN
banking77  typesafe            gate          margin 3080                0.0 0.063831      NaN      NaN      NaN          NaN        NaN
banking77  typesafe choice_in_scope             raw 3080                NaN      NaN 0.074354 0.298221 1.116355          NaN        NaN
banking77  typesafe choice_in_scope     temperature 3080                NaN      NaN 0.049431 0.297288 0.852526     1.864179        NaN
banking77  typesafe choice_in_scope        isotonic 3080                NaN      NaN 0.018990 0.299000 1.080880          NaN        NaN
banking77 decisions            gate top_probability 3080                7.0 0.079376      NaN      NaN      NaN          NaN        NaN
banking77 decisions            gate      confidence 3080                7.0 0.079376      NaN      NaN      NaN          NaN        NaN
banking77 decisions            gate          margin 3080                7.0 0.079377      NaN      NaN      NaN          NaN        NaN
banking77 decisions choice_in_scope             raw 3073                NaN      NaN 0.082802 0.320211 1.325999          NaN        NaN
banking77 decisions choice_in_scope     temperature 3073                NaN      NaN 0.075883 0.325844 1.042016     1.861115        NaN
banking77 decisions choice_in_scope        isotonic 3073                NaN      NaN 0.028766 0.315792 1.270660          NaN        NaN
 clinc150  typesafe            gate top_probability 5500                0.0 0.050771      NaN      NaN      NaN          NaN        NaN
 clinc150  typesafe            gate      confidence 5500                0.0 0.050771      NaN      NaN      NaN          NaN        NaN
 clinc150  typesafe            gate          margin 5500                0.0 0.049809      NaN      NaN      NaN          NaN        NaN
 clinc150  typesafe choice_in_scope             raw 4500                NaN      NaN 0.017129 0.114144 0.383125          NaN        NaN
 clinc150  typesafe choice_in_scope     temperature 4500                NaN      NaN 0.015461 0.113601 0.380851     0.902830        NaN
 clinc150  typesafe choice_in_scope        isotonic 4500                NaN      NaN 0.010793 0.114437 0.368018          NaN        NaN
 clinc150  typesafe   fit_predicate             raw 5500                NaN      NaN 0.038635 0.091252 0.166326          NaN   0.976239
 clinc150  typesafe   fit_predicate     temperature 5500                NaN      NaN 0.020656 0.090258 0.152987     0.650455   0.976239
 clinc150  typesafe   fit_predicate        isotonic 5500                NaN      NaN 0.015848 0.088372 0.172670          NaN   0.971897
 clinc150 decisions            gate top_probability 5500              190.0 0.116315      NaN      NaN      NaN          NaN        NaN
 clinc150 decisions            gate      confidence 5500              190.0 0.116315      NaN      NaN      NaN          NaN        NaN
 clinc150 decisions            gate          margin 5500              190.0 0.115411      NaN      NaN      NaN          NaN        NaN
 clinc150 decisions choice_in_scope             raw 4486                NaN      NaN 0.027824 0.175225 0.515846          NaN        NaN
 clinc150 decisions choice_in_scope     temperature 4486                NaN      NaN 0.037177 0.174001 0.510832     0.862160        NaN
 clinc150 decisions choice_in_scope        isotonic 4486                NaN      NaN 0.012790 0.174305 0.498932          NaN        NaN
 clinc150 decisions   fit_predicate             raw 5500                NaN      NaN 0.107180 0.262442 0.631338          NaN   0.935343
 clinc150 decisions   fit_predicate     temperature 5500                NaN      NaN 0.020787 0.224302 0.356335     3.661319   0.935343
 clinc150 decisions   fit_predicate        isotonic 5500                NaN      NaN 0.023962 0.224459 0.357466          NaN   0.934484

H2 paired AURC differences (probability minus confidence):

  dataset    system    n  n_missing_signals  difference  ci_low  ci_high  h2_pass
banking77  typesafe 3080                  0         0.0     0.0      0.0    False
banking77 decisions 3080                  7         0.0     0.0      0.0    False
 clinc150  typesafe 5500                  0         0.0     0.0      0.0    False
 clinc150 decisions 5500                190         0.0     0.0      0.0    False

Vendor confidence is a strictly monotone function of top probability on all observed values, so the identical AURCs are by construction; H2 is not supported. Refusals and unavailable signals are assigned negative infinity, ranked last and counted as errors in both paired curves.

Banking77 and CLINC choice-only sensitivity threshold rule: for each S1 and metric, tau* = the smallest tau on the FULL calibration split whose S1 selective accuracy among served items (signal >= tau) is >= A2 - 0.01; if none qualifies, tau* = 1.0 (always escalate). Report coverage at tau*. Then apply tau* unchanged on test.

A2 is measured on a 500-item, proportionally stratified calibration subset per dataset (seed 0, including CLINC OOS); no test item is used to fit a threshold or calibrator. The choice question excludes OOS; a negative companion fit predicate produces the OOS decision. Choice probability metrics are restricted to in-scope items with valid returned probability vectors; S1 refusals escalate; a refusal in the served answer is incorrect. ECE uses 15 equal-mass bins. Option descriptions replace underscores with spaces. Public dataset contamination is possible. Each teacher answer is one sample; no teacher sampling variance was measured. Provider usage dashboards were not reconciled. Costs are usage-weighted list prices, not bills. The budget cap is soft and can be exceeded by up to one in-flight batch; failed HTTP attempts are assumed not billed. Test sweeps and non-Banking77 endpoints are exploratory. Confidence intervals are unadjusted; Holm correction across H1-H5 requires the other experiments. The original CLINC fit question referred to a list it could not see because Jev evaluates questions independently. That predicate is invalid: only its accompanying Choice answers may be reused. We reran the S1 predicates with the full intent list, and reran S2 with Choice and corrected predicate. The archived fit prompt did not include the true/false criteria in its contract instructions: Jev received the criteria separately, while OpenAI did not. The gpt-6-luna legacy Choice answers came from the same request as the invalid predicate. For CLINC, both thresholds are selected jointly on calibration to maximize served coverage subject to selective accuracy >= A2 - 0.01; ties choose smallest choice threshold then smallest fit threshold. The grid comprises observed calibration signal values, without interpolation; test cost uses the observed per-call costs. The choice-only sensitivity row turns the fit gate off and counts OOS items as incorrect whenever served by S1. Coverage is a cost proxy, not conditional teacher cost. Escalate if fit probability or choice signal is missing or below its selected threshold. The E2 risk curves rank by each choice signal alone. Per-item CSVs are gzip-compressed with mtime 0; risk curves and supervised sweeps are plain CSV shards. S1 CLINC cost and latency sum the Choice and new predicate calls. Rows marked legacy_bundled include the unusable old predicate's cost, so are conservative for a fresh choice-only deployment.

Task-wide cache-accounted list-price spend (including invalid first CLINC calls): {"openai": 29.145689, "typesafe": 1.640737}. This is not a provider billing reconciliation.
