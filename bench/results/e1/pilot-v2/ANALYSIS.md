# Corrected CLINC pilot

The original companion predicate could not see the separate Choice's options. The revised predicate includes the full mechanically humanised in-scope list in its own instructions. These 50 first test items contain no OOS cases and are not representative.

   system  calls  input_tokens  output_tokens  cost_per_call  latency_p50_ms  latency_p95_ms
decisions     50        614.56           0.00       0.000061        174.4240       833.42945
       s2     50       2646.56          16.34       0.001752       1224.7015      1553.16510
 typesafe     50       1099.94          20.00       0.000046         89.4055       129.70010

Projected total task spend: {"openai": 29.0570786, "typesafe": 1.641033328}. List-price costs; soft cap, up to one in-flight batch of overshoot.
