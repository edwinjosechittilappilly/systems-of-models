# E3b analysis

## Discovery

- retail: 8 TP, 20 FP, 1 FN; precision 0.286 (Wilson (0.15253996056669095, 0.4705928843329571)), recall 0.889 (Wilson (0.565000294423344, 0.980109112361455)).
- airline: 7 TP, 17 FP, 4 FN; precision 0.292 (Wilson (0.14914648196960875, 0.49167693664496626)), recall 0.636 (Wilson (0.3538011745078489, 0.8483352890463243)).
- pooled: 15 TP, 37 FP, 5 FN; precision 0.288 (Wilson (0.18329960414709912, 0.4227278803668425)), recall 0.750 (Wilson (0.531299122381256, 0.8881382985923343)).

## Evaluation

- airline/book_reservation.cabin (full state): n=119; teacher accuracy 1.000 (Wilson (0.9687283197580606, 1.0), task-bootstrap (1.0, 1.0)); gold accuracy 1.000 (n=103, Wilson (0.964045241771352, 1.0), task-bootstrap (1.0, 1.0)); majority teacher 0.681; AURC 0.000 (task-bootstrap (0.0, 0.0)); calibrated coverage 1.0, served error 0.0.
- airline/book_reservation.cabin (user-and-tools-only state): n=119; teacher accuracy 0.992 (Wilson (0.9539321145669225, 0.9985150569599105), task-bootstrap (0.9781420765027322, 1.0)); gold accuracy 0.990 (n=103, Wilson (0.9470418081674632, 0.99828410852095), task-bootstrap (0.9749947478991596, 1.0)); majority teacher 0.681; AURC 0.000 (task-bootstrap (0.0, 0.0014658237173659973)); calibrated coverage 0.9159663865546218, served error 0.0.
- retail/cancel_pending_order.reason (full state): n=316; teacher accuracy 0.959 (Wilson (0.9308963457270263, 0.975802870407354), task-bootstrap (0.8958288043478261, 1.0)); gold accuracy 0.973 (n=255, Wilson (0.944431452164825, 0.98664041359431), task-bootstrap (0.9212876043039087, 1.0)); majority teacher 0.750; AURC 0.003 (task-bootstrap (0.0, 0.014227732363409459)); calibrated coverage 0.9683544303797469, served error 0.026143790849673203.
- retail/cancel_pending_order.reason (user-and-tools-only state): n=316; teacher accuracy 0.946 (Wilson (0.9155433184757538, 0.9661435054894023), task-bootstrap (0.8743783371472159, 0.9969230769230769)); gold accuracy 0.973 (n=255, Wilson (0.944431452164825, 0.98664041359431), task-bootstrap (0.9212876043039087, 1.0)); majority teacher 0.750; AURC 0.004 (task-bootstrap (0.00011595429240439212, 0.02095908834926149)); calibrated coverage 0.9936708860759493, served error 0.050955414012738856.
- pooled/all (full state): n=435; teacher accuracy 0.970 (Wilson (0.9495461582509453, 0.982453295718405), task-bootstrap (0.9215140075820858, 1.0)); gold accuracy 0.980 (n=358, Wilson (0.9601956937304009, 0.9904969138031786), task-bootstrap (0.9442721920519718, 1.0)); majority teacher 0.731; AURC 0.001 (task-bootstrap (0.0, 0.007486727115827548)); calibrated coverage 0.9770114942528736, served error 0.018823529411764704.

## Written questions

| Decision | Instructions | Options |
|---|---|---|
| retail/cancel_pending_order.reason | Identify the reason for the requested cancellation from the conversation. Use the customer's stated or confirmed reason; if none is stated, predict based on context. | no longer needed, ordered by mistake |
| airline/book_reservation.cabin | What cabin class is specified for the flight booking or reservation change the user wants to proceed with? Return one of: basic_economy, economy, or business. Use the selected itinerary’s class, not the class of an earlier reservation. | economy, basic_economy, business |

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
- The miner was revised twice after initial results were observed, so this is not a fully pre-registered implementation. The initial miner yielded 15 TP, 38 FP and 5 FN (precision 0.283, recall 0.750); the first independently reviewed miner yielded 15 TP, 12 FP and 5 FN (precision 0.556, recall 0.750). This run uses the final reviewer-approved miner; its P/R is reported above. Labels and protocol remained frozen.
- Offline replay requires the pinned τ²-bench data files to have been downloaded into bench/data; the recorded provider-call cache is archived beside these results.
- The preceding assistant text can already communicate the tool argument before the call. These scores measure recovery at the tool-call boundary, not anticipation before the agent decided.
- The cancel_pending_order.branch draft asks about a tracking number, apparently off target.
- The modify_pending_order_address.branch draft asks about jigsaw returns, apparently off target.
- All rewards included; reward filtering would bias results. Published trajectories use a user simulator, not real customers. Teacher choices and gold actions can be ambiguous; missing/conflicting gold is not scored.
- Episode-wide branches lack a defensible decision boundary and are not evaluated. Confirmation and multiclass action choices are not miner candidates; candidate-universe recall does not measure them.
- Repeated trials and shared tasks limit independence. Model transfer is not task generalization; public data contamination is possible. Wilson intervals assume independent observations; task-cluster bootstrap intervals account for repeated task observations.
