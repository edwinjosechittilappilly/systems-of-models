# E3a agent pilot: environment v2

100 Banking77 train tickets; seed 20261122; four departments.
Gold is the intent's frozen policy; joint accuracy requires correct department, priority, and identity decision.
Costs use provider-reported token usage and dated list prices, not provider billing.

Recommendation: NO GO; the model does not meet both thresholds.
- gpt-6-luna: n=100, joint accuracy=0.680 (95% Wilson 0.583-0.763), department=0.750, priority=0.890, identity=0.830, get_policy entry accuracy=0.650, search rate=1.000, cost/ticket=$0.000295; NO GO.

Limitations: public-data contamination, synthetic policy and account data, and a single teacher sample.
Entry-ID accuracy uses the last get_policy call before routing.
Identity accuracy counts verification of the ticket account before the first route.
The provider dashboard was not reconciled. Latencies are recorded original API round trips, not replay time.
