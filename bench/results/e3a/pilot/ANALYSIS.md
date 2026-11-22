# E3a agent pilot

100 paired Banking77 train tickets; seed 20261122; four departments.
Gold is the intent's frozen policy; joint accuracy requires correct department, priority, and identity decision.
Costs use provider-reported token usage and dated list prices, not provider billing.

Recommendation: GO with gpt-6.1-terra (highest joint accuracy among eligible models).
- gpt-6-luna: n=100, joint accuracy=0.650 (95% Wilson 0.553-0.736), department=0.760, priority=0.910, identity=0.770, entry ID in note=0.650, search rate=1.000, cost/ticket=$0.000264; NO GO.
- gpt-6.1-terra: n=100, joint accuracy=0.800 (95% Wilson 0.711-0.867), department=0.850, priority=0.930, identity=0.890, entry ID in note=0.800, search rate=1.000, cost/ticket=$0.002441; GO.

Limitations: public-data contamination, synthetic policy and account data, and a single teacher sample.
Entry-ID accuracy counts whether the gold ID appears in the free-text note; it is a proxy, not a parsed decision.
Identity accuracy counts verification of the ticket account before the first route.
The provider dashboard was not reconciled. Latencies are recorded original API round trips, not replay time.

The first collection attempt failed on both models after one successful response each: a null SDK `async_` field was sent back to the API and rejected with HTTP 400. The cached successful responses were reused after fixing input serialization; the two failed requests returned no usage. That initial attempt recorded $0.000636 in successful-call usage-weighted spend, and the resumed collection recorded $0.269886. The replay itself incurred no new API calls. These estimates are not reconciled to billed charges.
