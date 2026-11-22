# E1 Banking77 pilot

50 paired test items; first 50 in dataset order, not a random or stratified sample. Option descriptions replace underscores with spaces.

  dataset    system  calls  input_tokens_mean  output_tokens_mean  cost_mean  latency_p50_ms  latency_p95_ms
banking77 decisions     50             986.14                0.00   0.000099        170.9235        297.8632
banking77        s2     50            1313.22               17.46   0.001401       1218.0115       2021.6798
banking77  typesafe     50            1686.50              827.20   0.000071         93.0310        129.7663

Projected Banking77 full list-price spend (including the 500-item S2 calibration subset): {"openai": 5.4694582800000004, "typesafe": 0.32724846}. Projection extrapolates these unrepresentative pilot calls and is not a spending guarantee. Costs are usage-weighted list prices, not provider bills. The cap is soft: calls are charged on completion, so up to one in-flight batch may exceed it. Failed HTTP attempts are assumed not billed.
