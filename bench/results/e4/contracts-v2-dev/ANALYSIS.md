# E4: contracts exercised

Envelopes in the response caches: 45368; valid against contract 2.0.0: 45368; invalid: 0.

| namespace | system | envelopes | valid | cost bases |
|---|---|---|---|---|
| demo-jev | s1.decision | 20 | 20 | list_price=20 |
| demo-terra | s2.reasoning | 20 | 20 | list_price=20 |
| e1_decisions_banking77 | s1.decision | 4620 | 4620 | list_price=4620 |
| e1_decisions_clinc150 | s1.decision | 8600 | 8600 | list_price=8600 |
| e1_decisions_clinc150_fit_v2 | s1.decision | 658 | 658 | list_price=658 |
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

- TypeSafe /v1/systemone: 17/18 (0.944); dropped e.g. answers.fits.type
- OpenAI /v1/decisions: 26/26 (1.0); dropped e.g. 
- OpenAI /v1/responses: 13/28 (0.464); dropped e.g. access_programs.cyber; billing.payer; completed_at; created_at; image.context_compression; instructions; object; output[0].id; output[0].phase; prompt_cache_retention; service_tier; temperature
- OpenAI /v1/chat/completions: 8/12 (0.667); dropped e.g. choices[0].finish_reason; created; object; service_tier

Overhead (median microseconds per call, stub transports, this machine):

- gate, served by S1 (stub deciders): 27.8
- gate, escalated to S2 (stub deciders): 46.3
- envelope.to_dict(): 1.7
- envelope.validate() (s1-decision schema): 434.5
- OpenAI SDK responses.create, unwrapped (mock transport): 614.6
- OpenAI SDK responses.create, som.wrap (mock transport): 684.6

Threats: the field matrix is a reviewed reading of adapter code and provider docs, not a measurement; the
round-trip check matches values, so a coincidental equal value counts as recovered; overhead is
machine-dependent and excludes network time, which dominates real calls by three orders of magnitude.
