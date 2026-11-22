# E3b analysis

## Discovery

- retail: 7 TP, 15 FP, 2 FN; precision 0.318 (Wilson (0.16360593181356248, 0.5268140225895723)), recall 0.778 (Wilson (0.452588969106989, 0.9367748928821532)).
- airline: 7 TP, 17 FP, 4 FN; precision 0.292 (Wilson (0.14914648196960875, 0.49167693664496626)), recall 0.636 (Wilson (0.3538011745078489, 0.8483352890463243)).
- pooled: 14 TP, 32 FP, 6 FN; precision 0.304 (Wilson (0.19079840802767242, 0.44805646448407643)), recall 0.700 (Wilson (0.4810271816464765, 0.8545227551323956)).

## Miner revision history

All revisions follow frozen labels; revisions 2-4 occurred after results were observed. Revision 1 candidates are reconstructed from its mining log; revisions 2 and 3 from archived CSVs.

| Revision | Precision | Recall | False-positive candidates |
|---|---:|---:|---|
| 1 initial | 0.283 | 0.750 | airline/book_reservation.flights, airline/book_reservation.payment_methods, airline/calculate.branch, airline/calculate.expression, airline/get_flight_status.branch, airline/get_flight_status.date, airline/get_flight_status.flight_number, airline/get_reservation_details.branch, airline/get_reservation_details.reservation_id, airline/get_user_details.branch, airline/search_direct_flight.branch, airline/search_direct_flight.date, airline/search_onestop_flight.branch, airline/search_onestop_flight.date, airline/update_reservation_baggages.payment_id, airline/update_reservation_flights.flights, airline/update_reservation_flights.payment_id, retail/calculate.branch, retail/calculate.expression, retail/exchange_delivered_order_items.item_ids, retail/exchange_delivered_order_items.new_item_ids, retail/exchange_delivered_order_items.order_id, retail/exchange_delivered_order_items.payment_method_id, retail/find_user_id_by_email.branch, retail/find_user_id_by_name_zip.branch, retail/get_order_details.branch, retail/get_order_details.order_id, retail/get_product_details.branch, retail/get_product_details.product_id, retail/get_user_details.branch, retail/get_user_details.user_id, retail/list_all_product_types.branch, retail/modify_pending_order_items.item_ids, retail/modify_pending_order_items.new_item_ids, retail/modify_pending_order_items.order_id, retail/modify_pending_order_items.payment_method_id, retail/return_delivered_order_items.item_ids, retail/return_delivered_order_items.payment_method_id |
| 2 reviewed | 0.556 | 0.750 | airline/calculate.branch, airline/get_flight_status.branch, airline/get_reservation_details.branch, airline/get_user_details.branch, airline/search_direct_flight.branch, airline/search_onestop_flight.branch, retail/calculate.branch, retail/find_user_id_by_email.branch, retail/find_user_id_by_name_zip.branch, retail/get_product_details.branch, retail/get_user_details.branch, retail/list_all_product_types.branch |
| 3 non-majority support | 0.288 | 0.750 | airline/book_reservation.flights, airline/book_reservation.passengers, airline/book_reservation.payment_methods, airline/calculate.branch, airline/calculate.expression, airline/get_flight_status.branch, airline/get_flight_status.date, airline/get_flight_status.flight_number, airline/get_reservation_details.branch, airline/get_reservation_details.reservation_id, airline/get_user_details.branch, airline/search_direct_flight.branch, airline/search_direct_flight.date, airline/search_onestop_flight.branch, airline/search_onestop_flight.date, airline/update_reservation_flights.flights, airline/update_reservation_flights.payment_id, retail/calculate.branch, retail/calculate.expression, retail/exchange_delivered_order_items.item_ids, retail/exchange_delivered_order_items.new_item_ids, retail/exchange_delivered_order_items.order_id, retail/exchange_delivered_order_items.payment_method_id, retail/find_user_id_by_email.branch, retail/find_user_id_by_name_zip.branch, retail/get_order_details.order_id, retail/get_product_details.branch, retail/get_product_details.product_id, retail/get_user_details.branch, retail/get_user_details.user_id, retail/list_all_product_types.branch, retail/modify_pending_order_items.item_ids, retail/modify_pending_order_items.new_item_ids, retail/modify_pending_order_items.order_id, retail/modify_pending_order_items.payment_method_id, retail/return_delivered_order_items.item_ids, retail/return_delivered_order_items.payment_method_id |
| 4 earlier-tool-result context | 0.304 | 0.700 | airline/book_reservation.flights, airline/book_reservation.passengers, airline/book_reservation.payment_methods, airline/calculate.branch, airline/calculate.expression, airline/get_flight_status.branch, airline/get_flight_status.date, airline/get_flight_status.flight_number, airline/get_reservation_details.branch, airline/get_reservation_details.reservation_id, airline/get_user_details.branch, airline/search_direct_flight.branch, airline/search_direct_flight.date, airline/search_onestop_flight.branch, airline/search_onestop_flight.date, airline/update_reservation_flights.flights, airline/update_reservation_flights.payment_id, retail/calculate.branch, retail/calculate.expression, retail/exchange_delivered_order_items.item_ids, retail/exchange_delivered_order_items.new_item_ids, retail/find_user_id_by_email.branch, retail/find_user_id_by_name_zip.branch, retail/get_order_details.order_id, retail/get_product_details.branch, retail/get_product_details.product_id, retail/get_user_details.branch, retail/list_all_product_types.branch, retail/modify_pending_order_items.item_ids, retail/modify_pending_order_items.new_item_ids, retail/return_delivered_order_items.item_ids, retail/return_delivered_order_items.payment_method_id |

## Revision 4 false positives by distractor category

- **Calculation expressions**: airline/calculate.expression, retail/calculate.expression
- **Identifiers and identifier lists**: airline/get_reservation_details.reservation_id, airline/update_reservation_flights.payment_id, retail/exchange_delivered_order_items.item_ids, retail/exchange_delivered_order_items.new_item_ids, retail/get_order_details.order_id, retail/get_product_details.product_id, retail/modify_pending_order_items.item_ids, retail/modify_pending_order_items.new_item_ids, retail/return_delivered_order_items.item_ids, retail/return_delivered_order_items.payment_method_id
- **Incidental lookup or calculation branches**: airline/calculate.branch, airline/get_flight_status.branch, airline/get_reservation_details.branch, airline/get_user_details.branch, airline/search_direct_flight.branch, airline/search_onestop_flight.branch, retail/calculate.branch, retail/find_user_id_by_email.branch, retail/find_user_id_by_name_zip.branch, retail/get_product_details.branch, retail/get_user_details.branch, retail/list_all_product_types.branch
- **Other supplied data or lists**: airline/book_reservation.flights, airline/book_reservation.passengers, airline/book_reservation.payment_methods, airline/get_flight_status.date, airline/get_flight_status.flight_number, airline/search_direct_flight.date, airline/search_onestop_flight.date, airline/update_reservation_flights.flights

These are label-based categories, not proven causal explanations of miner failures.

## Revision 4 rejected candidates

| Domain / candidate | Kind | Support | Rejection reason | Determinant |
|---|---|---:|---|---|
| retail/get_order_details.branch | branch | 5 | rare |  |
| retail/modify_pending_order_payment.branch | branch | 4 | rare |  |
| retail/cancel_pending_order.order_id | tool_argument | 106 | copied_from_context |  |
| retail/cancel_pending_order.reason | tool_argument | 24 | copied_from_context |  |
| retail/exchange_delivered_order_items.order_id | tool_argument | 130 | copied_from_context |  |
| retail/exchange_delivered_order_items.payment_method_id | tool_argument | 130 | copied_from_context |  |
| retail/find_user_id_by_email.email | tool_argument | 104 | copied_from_context |  |
| retail/find_user_id_by_name_zip.first_name | tool_argument | 325 | copied_from_context |  |
| retail/find_user_id_by_name_zip.last_name | tool_argument | 321 | copied_from_context |  |
| retail/find_user_id_by_name_zip.zip | tool_argument | 349 | copied_from_context |  |
| retail/get_user_details.user_id | tool_argument | 440 | copied_from_context |  |
| retail/modify_pending_order_address.address1 | tool_argument | 66 | copied_from_context |  |
| retail/modify_pending_order_address.address2 | tool_argument | 66 | copied_from_context |  |
| retail/modify_pending_order_address.city | tool_argument | 56 | copied_from_context |  |
| retail/modify_pending_order_address.country | tool_argument | 0 | copied_from_context |  |
| retail/modify_pending_order_address.order_id | tool_argument | 71 | copied_from_context |  |
| retail/modify_pending_order_address.state | tool_argument | 54 | copied_from_context |  |
| retail/modify_pending_order_address.zip | tool_argument | 66 | copied_from_context |  |
| retail/modify_pending_order_items.order_id | tool_argument | 151 | copied_from_context |  |
| retail/modify_pending_order_items.payment_method_id | tool_argument | 151 | copied_from_context |  |
| retail/modify_pending_order_payment.order_id | tool_argument | 0 | copied_from_context |  |
| retail/modify_pending_order_payment.payment_method_id | tool_argument | 0 | copied_from_context |  |
| retail/modify_user_address.address1 | tool_argument | 38 | copied_from_context |  |
| retail/modify_user_address.address2 | tool_argument | 38 | copied_from_context |  |
| retail/modify_user_address.city | tool_argument | 38 | copied_from_context |  |
| retail/modify_user_address.country | tool_argument | 0 | copied_from_context |  |
| retail/modify_user_address.state | tool_argument | 31 | copied_from_context |  |
| retail/modify_user_address.user_id | tool_argument | 38 | copied_from_context |  |
| retail/modify_user_address.zip | tool_argument | 38 | copied_from_context |  |
| retail/return_delivered_order_items.order_id | tool_argument | 158 | copied_from_context |  |
| retail/transfer_to_human_agents.summary | tool_argument | 16 | free_text |  |
| airline/list_all_airports.branch | branch | 1 | rare |  |
| airline/update_reservation_passengers.branch | branch | 9 | rare |  |
| airline/book_reservation.cabin | tool_argument | 12 | copied_from_context |  |
| airline/book_reservation.destination | tool_argument | 16 | copied_from_context |  |
| airline/book_reservation.insurance | tool_argument | 0 | copied_from_context |  |
| airline/book_reservation.nonfree_baggages | tool_argument | 1 | copied_from_context |  |
| airline/book_reservation.origin | tool_argument | 8 | copied_from_context |  |
| airline/book_reservation.total_baggages | tool_argument | 12 | copied_from_context |  |
| airline/book_reservation.user_id | tool_argument | 21 | copied_from_context |  |
| airline/cancel_reservation.reservation_id | tool_argument | 65 | copied_from_context |  |
| airline/get_user_details.user_id | tool_argument | 140 | copied_from_context |  |
| airline/search_direct_flight.destination | tool_argument | 230 | copied_from_context |  |
| airline/search_direct_flight.origin | tool_argument | 198 | copied_from_context |  |
| airline/search_onestop_flight.destination | tool_argument | 39 | copied_from_context |  |
| airline/search_onestop_flight.origin | tool_argument | 37 | copied_from_context |  |
| airline/send_certificate.amount | tool_argument | 7 | copied_from_context |  |
| airline/send_certificate.user_id | tool_argument | 8 | copied_from_context |  |
| airline/transfer_to_human_agents.summary | tool_argument | 34 | free_text |  |
| airline/update_reservation_baggages.nonfree_baggages | tool_argument | 12 | copied_from_context |  |
| airline/update_reservation_baggages.payment_id | tool_argument | 18 | functional_dependency | get_reservation_details.reservation_id |
| airline/update_reservation_baggages.reservation_id | tool_argument | 16 | copied_from_context |  |
| airline/update_reservation_baggages.total_baggages | tool_argument | 11 | copied_from_context |  |
| airline/update_reservation_flights.cabin | tool_argument | 17 | copied_from_context |  |
| airline/update_reservation_flights.reservation_id | tool_argument | 71 | copied_from_context |  |
| airline/update_reservation_passengers.passengers | tool_argument | 5 | copied_from_context |  |
| airline/update_reservation_passengers.reservation_id | tool_argument | 5 | copied_from_context |  |

## Evaluation

- airline/book_reservation.flight_type (full state): n=119; teacher accuracy 1.000 (Wilson (0.9687283197580606, 1.0), task-bootstrap (1.0, 1.0)); gold accuracy 1.000 (n=103, Wilson (0.964045241771352, 1.0), task-bootstrap (1.0, 1.0)); majority teacher 0.395; AURC 0.000 (task-bootstrap (0.0, 0.0)); calibrated coverage 0.8739495798319328, served error 0.0.
- airline/book_reservation.flight_type (user-and-tools-only state): n=119; teacher accuracy 1.000 (Wilson (0.9687283197580606, 1.0), task-bootstrap (1.0, 1.0)); gold accuracy 1.000 (n=103, Wilson (0.964045241771352, 1.0), task-bootstrap (1.0, 1.0)); majority teacher 0.395; AURC 0.000 (task-bootstrap (0.0, 0.0)); calibrated coverage 0.773109243697479, served error 0.0.
- pooled/all (full state): n=119; teacher accuracy 1.000 (Wilson (0.9687283197580606, 1.0), task-bootstrap (1.0, 1.0)); gold accuracy 1.000 (n=103, Wilson (0.964045241771352, 1.0), task-bootstrap (1.0, 1.0)); majority teacher 0.395; AURC 0.000 (task-bootstrap (0.0, 0.0)); calibrated coverage 0.8739495798319328, served error 0.0.

## Written questions

| Decision | Instructions | Options |
|---|---|---|
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
- Three miner revisions followed the initial observed results, so this is not a fully pre-registered implementation. Revision 4 counts non-majority observations as support, checks values against the input and uniquely pointed-to earlier tool results, and follows retrieved IDs only via `id`, `*_id`, or `*_ids` arguments. Labels and protocol remained frozen.
- Offline replay requires the pinned τ²-bench data files to have been downloaded into bench/data; the recorded provider-call cache is archived beside these results.
- The preceding assistant text can already communicate the tool argument before the call. These scores measure recovery at the tool-call boundary, not anticipation before the agent decided.
- The cancel_pending_order.branch draft asks about a tracking number, apparently off target.
- The modify_pending_order_address.branch draft asks about jigsaw returns, apparently off target.
- All rewards included; reward filtering would bias results. Published trajectories use a user simulator, not real customers. Teacher choices and gold actions can be ambiguous; missing/conflicting gold is not scored.
- Episode-wide branches lack a defensible decision boundary and are not evaluated. Confirmation and multiclass action choices are not miner candidates; candidate-universe recall does not measure them.
- Repeated trials and shared tasks limit independence. Model transfer is not task generalization; public data contamination is possible. Wilson intervals assume independent observations; task-cluster bootstrap intervals account for repeated task observations.
