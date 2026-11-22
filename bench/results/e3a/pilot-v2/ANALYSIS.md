# E3a agent pilot: environment v2

100 Banking77 train tickets; seed 20261122; four departments.
Gold is the intent's frozen policy; joint accuracy requires correct department, priority, and identity decision.
Costs use provider-reported token usage and dated list prices, not provider billing.

Recommendation: GO with gpt-6.1-terra (meets both pilot thresholds).
- gpt-6.1-terra: n=100, joint accuracy=0.780 (95% Wilson 0.689-0.850), department=0.800, priority=0.930, identity=0.890, get_policy entry accuracy=0.760, search rate=1.000, cost/ticket=$0.002948; GO.

Limitations: public-data contamination, synthetic policy and account data, and a single teacher sample.
Entry-ID accuracy uses the last get_policy call before routing.
Identity accuracy counts verification of the ticket account before the first route.
The provider dashboard was not reconciled. Latencies are recorded original API round trips, not replay time.
