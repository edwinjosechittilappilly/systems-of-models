# E4: contracts exercised

Envelopes in the response caches: 135955; valid against contract 2.1.0: 83820; invalid: 52135.

| namespace | system | envelopes | valid | cost bases | median latency (ms) | median cost (USD) |
|---|---|---|---|---|---|---|
| demo-jev | s1.decision | 20 | 20 | list_price=20 | 84.4 | 7.394e-05 |
| demo-terra | s2.reasoning | 20 | 20 | list_price=20 | 1255.5 | 0.001056 |
| e1_decisions_banking77 | s1.decision | 4620 | 4620 | list_price=4620 | 167.4 | 9.84e-05 |
| e1_decisions_clinc150 | s1.decision | 8600 | 8600 | list_price=8600 | 185.1 | 0.0001494 |
| e1_decisions_clinc150_fit_v2 | s1.decision | 8600 | 8600 | list_price=8600 | 167.2 | 6.13e-05 |
| e1_s2_banking77 | s2.reasoning | 3080 | 3080 | list_price=3080 | 1209.3 | 0.001389 |
| e1_s2_cal_banking77 | s2.reasoning | 500 | 500 | list_price=500 | 1258.3 | 0.00139 |
| e1_s2_cal_clinc150 | s2.reasoning | 500 | 500 | list_price=500 | 1333.3 | 0.00184 |
| e1_s2_cal_clinc150_v2 | s2.reasoning | 500 | 500 | list_price=500 | 1335.2 | 0.00173545 |
| e1_s2_clinc150 | s2.reasoning | 5500 | 5500 | list_price=5500 | 1259.9 | 0.001841 |
| e1_s2_clinc150_v2 | s2.reasoning | 5500 | 5500 | list_price=5500 | 1226.3 | 0.00173745 |
| e1_typesafe_banking77 | s1.decision | 4620 | 4620 | list_price=4620 | 89.5 | 7.077e-05 |
| e1_typesafe_clinc150 | s1.decision | 8600 | 8600 | list_price=8600 | 98.1 | 0.00010655 |
| e1_typesafe_clinc150_fit_v2 | s1.decision | 8600 | 8600 | list_price=8600 | 86.4 | 4.616e-05 |
| e3a_s1_jev | s1.decision | 76695 | 24560 | list_price=76695 | 92.9 | 7.388e-05 |

Field matrix over 8 adapters x 8 fields: native 33, derived 23, unavailable 8 (field_matrix.csv; Anthropic and Gemini from fixtures only).

Round trip (share of informative native leaves recoverable from the envelope):

- TypeSafe /v1/systemone: 15/15 (1.0); nothing dropped
- OpenAI /v1/decisions: 23/23 (1.0); nothing dropped
- OpenAI /v1/responses: 6/20 (0.3); dropped e.g. access_programs.cyber; billing.payer; completed_at; created_at; image.context_compression; instructions; output[0].id; output[0].phase; prompt_cache_retention; service_tier; temperature; tool_choice
- OpenAI /v1/chat/completions: 7/10 (0.7); dropped e.g. choices[0].finish_reason; created; service_tier

Overhead (median microseconds per call, stub transports, this machine):

- gate, served by S1 (stub deciders): 27.5
- gate, escalated to S2 (stub deciders): 46.0
- envelope.to_dict(): 1.7
- envelope.validate() (s1-decision schema): 425.3
- OpenAI SDK responses.create, unwrapped (mock transport): 587.4
- OpenAI SDK responses.create, som.wrap (mock transport): 631.6

Threats: the field matrix is a reviewed reading of adapter code and provider docs, not a measurement. The
round trip matches values, so a coincidentally equal value would count as recovered; booleans, zeros and
protocol discriminators (type, role, status, object) are excluded for that reason, which also means they are
not checked. Overhead is machine-dependent and excludes network time, which dominates real calls by three
orders of magnitude.
