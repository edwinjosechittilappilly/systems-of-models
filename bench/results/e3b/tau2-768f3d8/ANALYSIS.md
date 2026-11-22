# E3b analysis

## Discovery

- retail: 8 TP, 6 FP, 1 FN; precision 0.571 (Wilson (0.3259064457965075, 0.7861920109552587)), recall 0.889 (Wilson (0.565000294423344, 0.980109112361455)).
- airline: 7 TP, 6 FP, 4 FN; precision 0.538 (Wilson (0.29143795714506016, 0.767939321904617)), recall 0.636 (Wilson (0.3538011745078489, 0.8483352890463243)).
- pooled: 15 TP, 12 FP, 5 FN; precision 0.556 (Wilson (0.3731302451322448, 0.72414141822977)), recall 0.750 (Wilson (0.531299122381256, 0.8881382985923343)).

## Evaluation

- airline/book_reservation.flight_type (full state): n=119; teacher accuracy 1.000 (Wilson (0.9687283197580606, 1.0), task-bootstrap (1.0, 1.0)); gold accuracy 1.000 (n=103, Wilson (0.964045241771352, 1.0), task-bootstrap (1.0, 1.0)); majority teacher 0.395; AURC 0.000 (task-bootstrap (0.0, 0.0)); calibrated coverage 0.8739495798319328, served error 0.0.
- airline/book_reservation.flight_type (user-and-tools-only state): n=119; teacher accuracy 1.000 (Wilson (0.9687283197580606, 1.0), task-bootstrap (1.0, 1.0)); gold accuracy 1.000 (n=103, Wilson (0.964045241771352, 1.0), task-bootstrap (1.0, 1.0)); majority teacher 0.395; AURC 0.000 (task-bootstrap (0.0, 0.0)); calibrated coverage 0.773109243697479, served error 0.0.
- retail/cancel_pending_order.reason (full state): n=316; teacher accuracy 0.959 (Wilson (0.9308963457270263, 0.975802870407354), task-bootstrap (0.8958288043478261, 1.0)); gold accuracy 0.973 (n=255, Wilson (0.944431452164825, 0.98664041359431), task-bootstrap (0.9212876043039087, 1.0)); majority teacher 0.750; AURC 0.003 (task-bootstrap (0.0, 0.014227732363409459)); calibrated coverage 0.9683544303797469, served error 0.026143790849673203.
- retail/cancel_pending_order.reason (user-and-tools-only state): n=316; teacher accuracy 0.946 (Wilson (0.9155433184757538, 0.9661435054894023), task-bootstrap (0.8743783371472159, 0.9969230769230769)); gold accuracy 0.973 (n=255, Wilson (0.944431452164825, 0.98664041359431), task-bootstrap (0.9212876043039087, 1.0)); majority teacher 0.750; AURC 0.004 (task-bootstrap (0.00011595429240439212, 0.02095908834926149)); calibrated coverage 0.9936708860759493, served error 0.050955414012738856.
- pooled/all (full state): n=435; teacher accuracy 0.970 (Wilson (0.9495461582509453, 0.982453295718405), task-bootstrap (0.9215140075820858, 1.0)); gold accuracy 0.980 (n=358, Wilson (0.9601956937304009, 0.9904969138031786), task-bootstrap (0.9442721920519718, 1.0)); majority teacher 0.653; AURC 0.001 (task-bootstrap (0.0, 0.007515276021030582)); calibrated coverage 0.9425287356321839, served error 0.01951219512195122.

## Written questions

| Decision | Instructions | Options |
|---|---|---|
| retail/cancel_pending_order.reason | Identify the reason for the requested cancellation from the conversation. Use the customer's stated or confirmed reason; if none is stated, predict based on context. | no longer needed, ordered by mistake |
| airline/book_reservation.flight_type | Classify the flight itinerary relevant to the current request as "round_trip" if it includes outbound and return travel, or "one_way" if it travels in one direction without a return. Connecting flights do not by themselves make a trip round-trip. | one_way, round_trip |

The user-and-tools-only state is a post-hoc ablation: assistant transcript messages are removed from the same bounded prefix, tool results are unchanged, and the same calibration tasks and error rule are used to select a new threshold for that state.

## Failures and limitations

- Held-out API failures/refusals: {}; these are not scored as correct.
- retail/cancel_pending_order.branch: episode-wide branch has no defensible decision boundary; not evaluated
- retail/exchange_delivered_order_items.branch: episode-wide branch has no defensible decision boundary; not evaluated
- retail/modify_pending_order_address.branch: episode-wide branch has no defensible decision boundary; not evaluated
- retail/modify_pending_order_items.branch: episode-wide branch has no defensible decision boundary; not evaluated
- retail/modify_user_address.branch: episode-wide branch has no defensible decision boundary; not evaluated
- retail/return_delivered_order_items.branch: episode-wide branch has no defensible decision boundary; not evaluated
- retail/transfer_to_human_agents.branch: episode-wide branch has no defensible decision boundary; not evaluated
- airline/book_reservation.branch: episode-wide branch has no defensible decision boundary; not evaluated
- airline/cancel_reservation.branch: episode-wide branch has no defensible decision boundary; not evaluated
- airline/send_certificate.branch: episode-wide branch has no defensible decision boundary; not evaluated
- airline/transfer_to_human_agents.branch: episode-wide branch has no defensible decision boundary; not evaluated
- airline/update_reservation_baggages.branch: episode-wide branch has no defensible decision boundary; not evaluated
- airline/update_reservation_flights.branch: episode-wide branch has no defensible decision boundary; not evaluated
- After the first results were observed, an independent compiler review corrected the miner; this run uses the corrected compiler and is not a fully pre-registered implementation. The initial miner yielded 15 TP, 38 FP and 5 FN (precision 0.283, recall 0.750); the labels and protocol remained frozen.
- Offline replay requires the pinned τ²-bench data files to have been downloaded into bench/data; the recorded provider-call cache is archived beside these results.
- The preceding assistant text can already communicate the tool argument before the call. These scores measure recovery at the tool-call boundary, not anticipation before the agent decided.
- The cancel_pending_order.branch draft asks about a tracking number, apparently off target.
- The modify_pending_order_address.branch draft asks about jigsaw returns, apparently off target.
- All rewards included; reward filtering would bias results. Published trajectories use a user simulator, not real customers. Teacher choices and gold actions can be ambiguous; missing/conflicting gold is not scored.
- Episode-wide branches lack a defensible decision boundary and are not evaluated. Confirmation and multiclass action choices are not miner candidates; candidate-universe recall does not measure them.
- Repeated trials and shared tasks limit independence. Model transfer is not task generalization; public data contamination is possible. Wilson intervals assume independent observations; task-cluster bootstrap intervals account for repeated task observations.
