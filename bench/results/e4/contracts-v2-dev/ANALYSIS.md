# E4: contracts exercised

Envelopes in the response caches: 52964; valid against contract 2.0.0: 52964; invalid: 0.

| namespace | system | envelopes | valid | cost bases |
|---|---|---|---|---|
| demo-jev | s1.decision | 20 | 20 | list_price=20 |
| demo-terra | s2.reasoning | 20 | 20 | list_price=20 |
| e1_decisions_banking77 | s1.decision | 4620 | 4620 | list_price=4620 |
| e1_decisions_clinc150 | s1.decision | 8600 | 8600 | list_price=8600 |
| e1_decisions_clinc150_fit_v2 | s1.decision | 8254 | 8254 | list_price=8254 |
| e1_s2_banking77 | s2.reasoning | 3080 | 3080 | list_price=3080 |
| e1_s2_cal_banking77 | s2.reasoning | 500 | 500 | list_price=500 |
| e1_s2_cal_clinc150 | s2.reasoning | 500 | 500 | list_price=500 |
| e1_s2_clinc150 | s2.reasoning | 5500 | 5500 | list_price=5500 |
| e1_s2_clinc150_v2 | s2.reasoning | 50 | 50 | list_price=50 |
| e1_typesafe_banking77 | s1.decision | 4620 | 4620 | list_price=4620 |
| e1_typesafe_clinc150 | s1.decision | 8600 | 8600 | list_price=8600 |
| e1_typesafe_clinc150_fit_v2 | s1.decision | 8600 | 8600 | list_price=8600 |

Field matrix over 8 adapters x 8 fields: native 33, derived 23, unavailable 8 (field_matrix.csv; Anthropic and Gemini from fixtures only).

Round trip (share of informative native leaves recoverable from the envelope):

- TypeSafe /v1/systemone: 15/15 (1.0); dropped e.g. 
- OpenAI /v1/decisions: 23/23 (1.0); dropped e.g. 
- OpenAI /v1/responses: 6/20 (0.3); dropped e.g. access_programs.cyber; billing.payer; completed_at; created_at; image.context_compression; instructions; output[0].id; output[0].phase; prompt_cache_retention; service_tier; temperature; tool_choice
- OpenAI /v1/chat/completions: 7/10 (0.7); dropped e.g. choices[0].finish_reason; created; service_tier

Overhead (median microseconds per call, stub transports, this machine):

- gate, served by S1 (stub deciders): 27.7
- gate, escalated to S2 (stub deciders): 49.3
- envelope.to_dict(): 1.7
- envelope.validate() (s1-decision schema): 436.9
- OpenAI SDK responses.create, unwrapped (mock transport): 611.8
- OpenAI SDK responses.create, som.wrap (mock transport): 659.1

Threats: the field matrix is a reviewed reading of adapter code and provider docs, not a measurement. The
round trip matches values, so a coincidentally equal value would count as recovered; booleans, zeros and
protocol discriminators (type, role, status, object) are excluded for that reason, which also means they are
not checked. Overhead is machine-dependent and excludes network time, which dominates real calls by three
orders of magnitude.
