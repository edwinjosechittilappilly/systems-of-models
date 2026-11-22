# E3b analysis

## Discovery

| Domain | Method | Kind | TP | FP | FN | Precision (Wilson 95%) | Recall (Wilson 95%) |
|---|---|---|---:|---:|---:|---|---|
| retail | miner | all | 8 | 20 | 1 | 0.286 (0.15253996056669095, 0.4705928843329571) | 0.889 (0.565000294423344, 0.980109112361455) |
| retail | miner | branch | 7 | 6 | 1 | 0.538 (0.29143795714506016, 0.767939321904617) | 0.875 (0.5291118177871466, 0.9775825085499434) |
| retail | miner | tool_argument | 1 | 14 | 0 | 0.067 (0.011866895493268526, 0.2981652987378002) | 1.000 (0.2065493143772375, 1.0) |
| retail | miner | retrieval_choice | 0 | 0 | 0 | nan (nan, nan) | nan (nan, nan) |
| retail | accept_all | all | 9 | 44 | 0 | 0.170 (0.09199945379618979, 0.2922528028109605) | 1.000 (0.700854951580456, 0.9999999999999999) |
| retail | accept_branches | all | 8 | 7 | 1 | 0.533 (0.3011698002549841, 0.7519046463426262) | 0.889 (0.565000294423344, 0.980109112361455) |
| airline | miner | all | 7 | 24 | 4 | 0.226 (0.11395135561262495, 0.3981241838334204) | 0.636 (0.3538011745078489, 0.8483352890463243) |
| airline | miner | branch | 6 | 6 | 1 | 0.500 (0.2537815976337061, 0.7462184023662939) | 0.857 (0.48687217072568134, 0.9743203756552565) |
| airline | miner | tool_argument | 1 | 18 | 3 | 0.053 (0.009351994062300376, 0.2463873116689878) | 0.250 (0.04558726080970055, 0.699358157417598) |
| airline | miner | retrieval_choice | 0 | 0 | 0 | nan (nan, nan) | nan (nan, nan) |
| airline | accept_all | all | 11 | 39 | 0 | 0.220 (0.12753915970214422, 0.3524154958125367) | 1.000 (0.7411670330319684, 1.0) |
| airline | accept_branches | all | 7 | 7 | 4 | 0.500 (0.2679920245241364, 0.7320079754758636) | 0.636 (0.3538011745078489, 0.8483352890463243) |
| pooled | miner | all | 15 | 44 | 5 | 0.254 (0.16055977573236904, 0.3779614402892727) | 0.750 (0.531299122381256, 0.8881382985923343) |
| pooled | miner | branch | 13 | 12 | 2 | 0.520 (0.3349851695035679, 0.6996871404588703) | 0.867 (0.6211801716767765, 0.9626387408969347) |
| pooled | miner | tool_argument | 2 | 32 | 3 | 0.059 (0.016282655210122746, 0.19093606904280996) | 0.400 (0.117620774232648, 0.7692757187239869) |
| pooled | miner | retrieval_choice | 0 | 0 | 0 | nan (nan, nan) | nan (nan, nan) |
| pooled | accept_all | all | 20 | 83 | 0 | 0.194 (0.12936308845239128, 0.28097817143503434) | 1.000 (0.8388748419471808, 1.0) |
| pooled | accept_branches | all | 15 | 14 | 5 | 0.517 (0.3443102188199473, 0.6861390984731651) | 0.750 (0.531299122381256, 0.8881382985923343) |

On these tau2 traces the miner's recall comes predominantly from branch candidates; it does not beat the accept-all-branches baseline, which attains the same pooled recall with higher precision. Both baselines operate over the miner's emitted candidate universe, including rejected candidates.

## Miner revision history

All revisions follow frozen labels; revisions 2-4b occurred after results were observed. Revision 1 candidates are reconstructed from its mining log; revisions 2-4 from archived CSVs. Revision 3b numbers are from independent review; its per-candidate FP lists were not archived. Revision 4b fixes trace extraction without changing the miner.

| Revision | Precision | Recall | False-positive candidates |
|---|---:|---:|---|
| 1 initial (a5a7697) | 0.283 | 0.750 | airline/book_reservation.flights, airline/book_reservation.payment_methods, airline/calculate.branch, airline/calculate.expression, airline/get_flight_status.branch, airline/get_flight_status.date, airline/get_flight_status.flight_number, airline/get_reservation_details.branch, airline/get_reservation_details.reservation_id, airline/get_user_details.branch, airline/search_direct_flight.branch, airline/search_direct_flight.date, airline/search_onestop_flight.branch, airline/search_onestop_flight.date, airline/update_reservation_baggages.payment_id, airline/update_reservation_flights.flights, airline/update_reservation_flights.payment_id, retail/calculate.branch, retail/calculate.expression, retail/exchange_delivered_order_items.item_ids, retail/exchange_delivered_order_items.new_item_ids, retail/exchange_delivered_order_items.order_id, retail/exchange_delivered_order_items.payment_method_id, retail/find_user_id_by_email.branch, retail/find_user_id_by_name_zip.branch, retail/get_order_details.branch, retail/get_order_details.order_id, retail/get_product_details.branch, retail/get_product_details.product_id, retail/get_user_details.branch, retail/get_user_details.user_id, retail/list_all_product_types.branch, retail/modify_pending_order_items.item_ids, retail/modify_pending_order_items.new_item_ids, retail/modify_pending_order_items.order_id, retail/modify_pending_order_items.payment_method_id, retail/return_delivered_order_items.item_ids, retail/return_delivered_order_items.payment_method_id |
| 2 reviewed (071a93d) | 0.556 | 0.750 | airline/calculate.branch, airline/get_flight_status.branch, airline/get_reservation_details.branch, airline/get_user_details.branch, airline/search_direct_flight.branch, airline/search_onestop_flight.branch, retail/calculate.branch, retail/find_user_id_by_email.branch, retail/find_user_id_by_name_zip.branch, retail/get_product_details.branch, retail/get_user_details.branch, retail/list_all_product_types.branch |
| 3 non-majority support (88268b5) | 0.288 | 0.750 | airline/book_reservation.flights, airline/book_reservation.passengers, airline/book_reservation.payment_methods, airline/calculate.branch, airline/calculate.expression, airline/get_flight_status.branch, airline/get_flight_status.date, airline/get_flight_status.flight_number, airline/get_reservation_details.branch, airline/get_reservation_details.reservation_id, airline/get_user_details.branch, airline/search_direct_flight.branch, airline/search_direct_flight.date, airline/search_onestop_flight.branch, airline/search_onestop_flight.date, airline/update_reservation_flights.flights, airline/update_reservation_flights.payment_id, retail/calculate.branch, retail/calculate.expression, retail/exchange_delivered_order_items.item_ids, retail/exchange_delivered_order_items.new_item_ids, retail/exchange_delivered_order_items.order_id, retail/exchange_delivered_order_items.payment_method_id, retail/find_user_id_by_email.branch, retail/find_user_id_by_name_zip.branch, retail/get_order_details.order_id, retail/get_product_details.branch, retail/get_product_details.product_id, retail/get_user_details.branch, retail/get_user_details.user_id, retail/list_all_product_types.branch, retail/modify_pending_order_items.item_ids, retail/modify_pending_order_items.new_item_ids, retail/modify_pending_order_items.order_id, retail/modify_pending_order_items.payment_method_id, retail/return_delivered_order_items.item_ids, retail/return_delivered_order_items.payment_method_id |
| 3b transcript input (3a1c51c; superseded during review) | 0.452 | 0.700 | not archived |
| 3b user-only input (3a1c51c; superseded during review) | 0.455 | 0.750 | not archived |
| 4 earlier-tool-result context (7d04a9e) | 0.304 | 0.700 | airline/book_reservation.flights, airline/book_reservation.passengers, airline/book_reservation.payment_methods, airline/calculate.branch, airline/calculate.expression, airline/get_flight_status.branch, airline/get_flight_status.date, airline/get_flight_status.flight_number, airline/get_reservation_details.branch, airline/get_reservation_details.reservation_id, airline/get_user_details.branch, airline/search_direct_flight.branch, airline/search_direct_flight.date, airline/search_onestop_flight.branch, airline/search_onestop_flight.date, airline/update_reservation_flights.flights, airline/update_reservation_flights.payment_id, retail/calculate.branch, retail/calculate.expression, retail/exchange_delivered_order_items.item_ids, retail/exchange_delivered_order_items.new_item_ids, retail/find_user_id_by_email.branch, retail/find_user_id_by_name_zip.branch, retail/get_order_details.order_id, retail/get_product_details.branch, retail/get_product_details.product_id, retail/get_user_details.branch, retail/list_all_product_types.branch, retail/modify_pending_order_items.item_ids, retail/modify_pending_order_items.new_item_ids, retail/return_delivered_order_items.item_ids, retail/return_delivered_order_items.payment_method_id |
| 4b user-turn input (7d04a9e + ac056dc) | 0.254 | 0.750 | airline/book_reservation.destination, airline/book_reservation.flights, airline/book_reservation.passengers, airline/book_reservation.payment_methods, airline/calculate.branch, airline/calculate.expression, airline/cancel_reservation.reservation_id, airline/get_flight_status.branch, airline/get_flight_status.date, airline/get_flight_status.flight_number, airline/get_reservation_details.branch, airline/get_reservation_details.reservation_id, airline/get_user_details.branch, airline/search_direct_flight.branch, airline/search_direct_flight.date, airline/search_direct_flight.destination, airline/search_direct_flight.origin, airline/search_onestop_flight.branch, airline/search_onestop_flight.date, airline/search_onestop_flight.destination, airline/update_reservation_baggages.nonfree_baggages, airline/update_reservation_flights.flights, airline/update_reservation_flights.payment_id, airline/update_reservation_flights.reservation_id, retail/calculate.branch, retail/calculate.expression, retail/cancel_pending_order.order_id, retail/exchange_delivered_order_items.item_ids, retail/exchange_delivered_order_items.new_item_ids, retail/exchange_delivered_order_items.order_id, retail/find_user_id_by_email.branch, retail/find_user_id_by_name_zip.branch, retail/get_order_details.order_id, retail/get_product_details.branch, retail/get_product_details.product_id, retail/get_user_details.branch, retail/list_all_product_types.branch, retail/modify_pending_order_address.address2, retail/modify_pending_order_address.order_id, retail/modify_pending_order_items.item_ids, retail/modify_pending_order_items.new_item_ids, retail/return_delivered_order_items.item_ids, retail/return_delivered_order_items.order_id, retail/return_delivered_order_items.payment_method_id |

## Revision 4b false positives by distractor category

- **Calculation expressions**: airline/calculate.expression, retail/calculate.expression
- **Identifiers and identifier lists**: airline/cancel_reservation.reservation_id, airline/get_reservation_details.reservation_id, airline/update_reservation_flights.payment_id, airline/update_reservation_flights.reservation_id, retail/cancel_pending_order.order_id, retail/exchange_delivered_order_items.item_ids, retail/exchange_delivered_order_items.new_item_ids, retail/exchange_delivered_order_items.order_id, retail/get_order_details.order_id, retail/get_product_details.product_id, retail/modify_pending_order_address.order_id, retail/modify_pending_order_items.item_ids, retail/modify_pending_order_items.new_item_ids, retail/return_delivered_order_items.item_ids, retail/return_delivered_order_items.order_id, retail/return_delivered_order_items.payment_method_id
- **Incidental lookup or calculation branches**: airline/calculate.branch, airline/get_flight_status.branch, airline/get_reservation_details.branch, airline/get_user_details.branch, airline/search_direct_flight.branch, airline/search_onestop_flight.branch, retail/calculate.branch, retail/find_user_id_by_email.branch, retail/find_user_id_by_name_zip.branch, retail/get_product_details.branch, retail/get_user_details.branch, retail/list_all_product_types.branch
- **Other supplied data or lists**: airline/book_reservation.destination, airline/book_reservation.flights, airline/book_reservation.passengers, airline/book_reservation.payment_methods, airline/get_flight_status.date, airline/get_flight_status.flight_number, airline/search_direct_flight.date, airline/search_direct_flight.destination, airline/search_direct_flight.origin, airline/search_onestop_flight.date, airline/search_onestop_flight.destination, airline/update_reservation_baggages.nonfree_baggages, airline/update_reservation_flights.flights, retail/modify_pending_order_address.address2

These are label-based categories, not proven causal explanations of miner failures.

## Revision 4b rejected candidates

| Domain / candidate | Kind | Support | Rejection reason | Determinant |
|---|---|---:|---|---|
| retail/get_order_details.branch | branch | 5 | rare |  |
| retail/modify_pending_order_payment.branch | branch | 4 | rare |  |
| retail/exchange_delivered_order_items.payment_method_id | tool_argument | 130 | copied_from_context |  |
| retail/find_user_id_by_email.email | tool_argument | 104 | copied_from_context |  |
| retail/find_user_id_by_name_zip.first_name | tool_argument | 325 | copied_from_context |  |
| retail/find_user_id_by_name_zip.last_name | tool_argument | 321 | copied_from_context |  |
| retail/find_user_id_by_name_zip.zip | tool_argument | 349 | copied_from_context |  |
| retail/get_user_details.user_id | tool_argument | 440 | copied_from_context |  |
| retail/modify_pending_order_address.address1 | tool_argument | 66 | copied_from_context |  |
| retail/modify_pending_order_address.city | tool_argument | 56 | copied_from_context |  |
| retail/modify_pending_order_address.country | tool_argument | 0 | copied_from_context |  |
| retail/modify_pending_order_address.state | tool_argument | 54 | copied_from_context |  |
| retail/modify_pending_order_address.zip | tool_argument | 66 | copied_from_context |  |
| retail/modify_pending_order_items.order_id | tool_argument | 151 | copied_from_context |  |
| retail/modify_pending_order_items.payment_method_id | tool_argument | 151 | copied_from_context |  |
| retail/modify_pending_order_payment.order_id | tool_argument | 0 | copied_from_context |  |
| retail/modify_pending_order_payment.payment_method_id | tool_argument | 0 | copied_from_context |  |
| retail/modify_user_address.address1 | tool_argument | 38 | functional_dependency | modify_pending_order_address.address2 |
| retail/modify_user_address.address2 | tool_argument | 38 | functional_dependency | modify_pending_order_address.address2 |
| retail/modify_user_address.city | tool_argument | 38 | copied_from_context |  |
| retail/modify_user_address.country | tool_argument | 0 | copied_from_context |  |
| retail/modify_user_address.state | tool_argument | 31 | functional_dependency | modify_pending_order_address.address2 |
| retail/modify_user_address.user_id | tool_argument | 38 | copied_from_context |  |
| retail/modify_user_address.zip | tool_argument | 38 | copied_from_context |  |
| retail/transfer_to_human_agents.summary | tool_argument | 16 | free_text |  |
| airline/list_all_airports.branch | branch | 1 | rare |  |
| airline/update_reservation_passengers.branch | branch | 9 | rare |  |
| airline/book_reservation.cabin | tool_argument | 12 | copied_from_context |  |
| airline/book_reservation.insurance | tool_argument | 0 | copied_from_context |  |
| airline/book_reservation.nonfree_baggages | tool_argument | 1 | copied_from_context |  |
| airline/book_reservation.origin | tool_argument | 8 | copied_from_context |  |
| airline/book_reservation.total_baggages | tool_argument | 12 | copied_from_context |  |
| airline/book_reservation.user_id | tool_argument | 21 | copied_from_context |  |
| airline/get_user_details.user_id | tool_argument | 140 | copied_from_context |  |
| airline/search_onestop_flight.origin | tool_argument | 37 | functional_dependency | search_direct_flight.origin |
| airline/send_certificate.amount | tool_argument | 7 | rare |  |
| airline/send_certificate.user_id | tool_argument | 8 | copied_from_context |  |
| airline/transfer_to_human_agents.summary | tool_argument | 34 | free_text |  |
| airline/update_reservation_baggages.payment_id | tool_argument | 18 | functional_dependency | get_reservation_details.reservation_id |
| airline/update_reservation_baggages.reservation_id | tool_argument | 16 | copied_from_context |  |
| airline/update_reservation_baggages.total_baggages | tool_argument | 11 | copied_from_context |  |
| airline/update_reservation_flights.cabin | tool_argument | 17 | copied_from_context |  |
| airline/update_reservation_passengers.passengers | tool_argument | 5 | copied_from_context |  |
| airline/update_reservation_passengers.reservation_id | tool_argument | 5 | copied_from_context |  |

## Labelled judgement candidate outcomes

Revision 4 rejection reasons are shown alongside 4b; `accepted` means no rejection.

| Domain / candidate | Revision 4 | Revision 4b | Support |
|---|---|---|---:|
| retail/cancel_pending_order.branch | accepted | accepted | 90 |
| retail/exchange_delivered_order_items.branch | accepted | accepted | 120 |
| retail/modify_pending_order_address.branch | accepted | accepted | 66 |
| retail/modify_pending_order_items.branch | accepted | accepted | 143 |
| retail/modify_user_address.branch | accepted | accepted | 40 |
| retail/return_delivered_order_items.branch | accepted | accepted | 128 |
| retail/transfer_to_human_agents.branch | accepted | accepted | 17 |
| retail/cancel_pending_order.reason | copied_from_context | accepted | 24 |
| retail/modify_pending_order_payment.branch | rare | rare | 4 |
| airline/book_reservation.branch | accepted | accepted | 24 |
| airline/cancel_reservation.branch | accepted | accepted | 48 |
| airline/send_certificate.branch | accepted | accepted | 11 |
| airline/transfer_to_human_agents.branch | accepted | accepted | 35 |
| airline/update_reservation_baggages.branch | accepted | accepted | 19 |
| airline/update_reservation_flights.branch | accepted | accepted | 55 |
| airline/book_reservation.flight_type | accepted | accepted | 12 |
| airline/update_reservation_passengers.branch | rare | rare | 9 |
| airline/book_reservation.cabin | copied_from_context | copied_from_context | 12 |
| airline/book_reservation.insurance | copied_from_context | copied_from_context | 0 |
| airline/update_reservation_flights.cabin | copied_from_context | copied_from_context | 17 |

## Evaluation

- airline/book_reservation.flight_type (full state): n=119; teacher accuracy 1.000 (Wilson (0.9687283197580606, 1.0), task-bootstrap (1.0, 1.0)); gold accuracy 1.000 (n=103, Wilson (0.964045241771352, 1.0), task-bootstrap (1.0, 1.0)); majority teacher 0.395; AURC 0.000 (task-bootstrap (0.0, 0.0)); calibrated coverage 0.8739495798319328, served error 0.0.
- airline/book_reservation.flight_type (held-out-majority sensitivity state): n=119; teacher accuracy 0.605 (Wilson (0.5152490035352084, 0.6882653493551403), task-bootstrap (0.23175101902173914, 0.9183732795443759)); gold accuracy 0.641 (n=103, Wilson (0.5446011395690534, 0.7268290741335602), task-bootstrap (0.22110745614035088, 0.9902935959671396)); majority teacher nan; AURC nan (task-bootstrap (nan, nan)); calibrated coverage None, served error None.
- airline/book_reservation.flight_type (user-and-tools-only state): n=119; teacher accuracy 1.000 (Wilson (0.9687283197580606, 1.0), task-bootstrap (1.0, 1.0)); gold accuracy 1.000 (n=103, Wilson (0.964045241771352, 1.0), task-bootstrap (1.0, 1.0)); majority teacher 0.395; AURC 0.000 (task-bootstrap (0.0, 0.0)); calibrated coverage 0.773109243697479, served error 0.0.
- retail/cancel_pending_order.reason (full state): n=316; teacher accuracy 0.959 (Wilson (0.9308963457270263, 0.975802870407354), task-bootstrap (0.8958288043478261, 1.0)); gold accuracy 0.973 (n=255, Wilson (0.944431452164825, 0.98664041359431), task-bootstrap (0.9212876043039087, 1.0)); majority teacher 0.750; AURC 0.003 (task-bootstrap (0.0, 0.014227732363409459)); calibrated coverage 0.9683544303797469, served error 0.026143790849673203.
- retail/cancel_pending_order.reason (held-out-majority sensitivity state): n=316; teacher accuracy 0.750 (Wilson (0.6994475433595245, 0.794547201982655), task-bootstrap (0.5686198392400438, 0.9104022657450077)); gold accuracy 0.769 (n=255, Wilson (0.7131121095689552, 0.8161694074808437), task-bootstrap (0.5475285171102662, 0.9555637254901961)); majority teacher nan; AURC nan (task-bootstrap (nan, nan)); calibrated coverage None, served error None.
- retail/cancel_pending_order.reason (user-and-tools-only state): n=316; teacher accuracy 0.946 (Wilson (0.9155433184757538, 0.9661435054894023), task-bootstrap (0.8743783371472159, 0.9969230769230769)); gold accuracy 0.973 (n=255, Wilson (0.944431452164825, 0.98664041359431), task-bootstrap (0.9212876043039087, 1.0)); majority teacher 0.750; AURC 0.004 (task-bootstrap (0.00011595429240439212, 0.02095908834926149)); calibrated coverage 0.9936708860759493, served error 0.050955414012738856.
- pooled/all (full state): n=435; teacher accuracy 0.970 (Wilson (0.9495461582509453, 0.982453295718405), task-bootstrap (0.9215140075820858, 1.0)); gold accuracy 0.980 (n=358, Wilson (0.9601956937304009, 0.9904969138031786), task-bootstrap (0.9442721920519718, 1.0)); majority teacher 0.653; AURC 0.001 (task-bootstrap (0.0, 0.007515276021030582)); calibrated coverage 0.9425287356321839, served error 0.01951219512195122.
- pooled/all (held-out-majority sensitivity state): n=435; teacher accuracy 0.710 (Wilson (0.6660241931081206, 0.7509828975432025), task-bootstrap (0.5414624747403544, 0.8555635624538063)); gold accuracy 0.732 (n=358, Wilson (0.6836710236216856, 0.7750934323392857), task-bootstrap (0.5283346323214216, 0.9097387173396675)); majority teacher nan; AURC nan (task-bootstrap (nan, nan)); calibrated coverage None, served error None.
- pooled/all (user-and-tools-only state): n=435; teacher accuracy 0.961 (Wilson (0.9383104843486995, 0.9754591514501011), task-bootstrap (0.9030469345414514, 0.997849577737782)); gold accuracy 0.980 (n=358, Wilson (0.9601956937304009, 0.9904969138031786), task-bootstrap (0.9442721920519718, 1.0)); majority teacher 0.653; AURC 0.002 (task-bootstrap (4.587119015237452e-05, 0.010960762415538353)); calibrated coverage 0.9333333333333333, served error 0.03940886699507389.
Held-out-majority rows are sensitivity analyses fitted on the evaluation labels, not deployable baselines. The writer-side majority is fitted on training traces.

Flight-type teacher-label distributions: {'writer_training': {'one_way': 9, 'round_trip': 12}, 'calibration': {'one_way': 8}, 'held_out': {'one_way': 72, 'round_trip': 47}}. Its eight calibration occurrences are all one_way, so the threshold was fitted on one class; the writer-side majority is round_trip whereas the held-out majority is one_way (60.5% of held-out instances).

Pooled user-and-tools-only teacher agreement: {'n': 435, 'correct': 418, 'accuracy': 0.960919540229885}. Cancellation-reason states with the teacher value verbatim in prior assistant text: 246/316.

Independent review reported identical miner outcomes for all 103 candidates when only pre-call user turns were used in its check. The published run still uses the user-turn input described below.


## Written questions

| Decision | Instructions | Options | Inspection |
|---|---|---|---|
| retail/cancel_pending_order.branch | Does the user say they lost an ordered item and ask for its tracking number? (true means: The user reports a lost ordered item and requests its tracking number.; false means: The user does not make both statements.) | true / false | Off target: asks about a lost item and tracking |
| retail/exchange_delivered_order_items.branch | Does the user want to exchange or change items from a received or recently purchased order? Distinguish this from requests only to return, cancel, or modify a pending order. (true means: The user requests an exchange or changes to purchased items, possibly alongside a return.; false means: The user does not request an exchange or changes to purchased items, or the request concerns a pending order.) | true / false | Not flagged; unvalidated |
| retail/modify_pending_order_address.branch | Does the user request an order address check or correction, or a change involving a jigsaw puzzle order? (true means: The request involves an order address or a jigsaw puzzle order change.; false means: The request involves neither an order address nor a jigsaw puzzle order change.) | true / false | Off target: includes a jigsaw-puzzle request |
| retail/modify_pending_order_items.branch | Will the assistant use modify_pending_order_items in response to the user's request? Consider whether the request involves changing items in an order that may still be pending. (true means: The assistant uses modify_pending_order_items.; false means: The assistant does not use modify_pending_order_items.) | true / false | Not flagged; unvalidated |
| retail/modify_user_address.branch | Does the user request a change or correction to their account address? (true means: The user wants their account address updated or corrected.; false means: The user does not request a change to their account address.) | true / false | Not flagged; unvalidated |
| retail/return_delivered_order_items.branch | Does the user ask to return items from an order, suggesting use of the return_delivered_order_items tool? Distinguish returns from exchanges, cancellations, and unspecified changes. (true means: The request is likely to involve returning ordered items.; false means: The request does not clearly involve returning ordered items.) | true / false | Not flagged; unvalidated |
| retail/transfer_to_human_agents.branch | Determine whether the user's request calls for a transfer to a human support agent. (true means: Transfer to a human agent is called for.; false means: Transfer to a human agent is not called for.) | true / false | Not flagged; unvalidated |
| retail/cancel_pending_order.reason | Identify the reason for the requested cancellation from the conversation. Use the customer's stated or confirmed reason; if none is stated, predict based on context. | no longer needed, ordered by mistake | Not flagged; unvalidated |
| airline/book_reservation.branch | Does the user request a new flight booking in connection with an existing reservation or a specific flight they previously took? (true means: The user wants a new booking and also references an existing reservation or a specific prior flight to match.; false means: The user does not request such a new booking.) | true / false | Not flagged; unvalidated |
| airline/cancel_reservation.branch | Does the user request cancellation of a recently booked flight, cancellation of multiple reservations, or passenger removal alongside a specified new flight search? (true means: The request matches one of these cancellation or passenger-removal scenarios.; false means: The request does not match these scenarios.) | true / false | Not flagged; unvalidated |
| airline/send_certificate.branch | Does the user either want to discuss frustration about a previous delayed flight, or ask to book a flight from San Francisco to New York for three people? (true means: The request matches one of those scenarios.; false means: The request does not match either scenario.) | true / false | Overfits: describes a specific route and passenger count |
| airline/transfer_to_human_agents.branch | Does the user's request suggest a need for transfer to a human agent rather than routine reservation assistance? Consider requests for compensation after a disruption, urgent exceptional circumstances, or help resolving an unclear booking problem. Routine booking and reservation changes generally do not indicate a transfer. (true means: The request suggests a human agent transfer.; false means: The request appears suitable for routine assistance without a human transfer.) | true / false | Not flagged; unvalidated |
| airline/update_reservation_baggages.branch | Does the user request changes to upcoming round-trip flights without specifying the changes? (true means: The user makes an unspecified request to change upcoming round-trip flights.; false means: The user does not make that request.) | true / false | Off target: asks about changing flights |
| airline/update_reservation_flights.branch | Does the user want to change the flights or cabin class on an existing reservation? Distinguish this from canceling, booking a new flight, changing passenger details, or an unspecified reservation change. (true means: The user requests a change to existing flights or their cabin class.; false means: The user does not request a specific change to existing flights or their cabin class.) | true / false | Not flagged; unvalidated |
| airline/book_reservation.flight_type | Classify the flight itinerary relevant to the current request as "round_trip" if it includes outbound and return travel, or "one_way" if it travels in one direction without a return. Connecting flights do not by themselves make a trip round-trip. | one_way, round_trip | Not flagged; unvalidated |

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
- Mining trace input now contains only user-turn text, not assistant text. It still concatenates all user turns, including turns after a candidate tool call; this remaining future-user exposure can affect copied-value detection and is not a predecision-prefix guarantee.
- The cancel_pending_order.branch draft asks about a tracking number, apparently off target.
- The modify_pending_order_address.branch draft asks about jigsaw returns, apparently off target.
- All rewards included; reward filtering would bias results. Published trajectories use a user simulator, not real customers. Teacher choices and gold actions can be ambiguous; missing/conflicting gold is not scored.
- Episode-wide branches lack a defensible decision boundary and are not evaluated. Confirmation and multiclass action choices are not miner candidates; candidate-universe recall does not measure them.
- Repeated trials and shared tasks limit independence. Model transfer is not task generalization; public data contamination is possible. Wilson intervals assume independent observations; task-cluster bootstrap intervals account for repeated task observations.
