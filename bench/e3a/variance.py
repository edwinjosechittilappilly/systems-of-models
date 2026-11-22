"""Stratified independent teacher draws for paired E3a evaluation."""

from __future__ import annotations

import random
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from bench.e3a.agent import instructions_for
from bench.e3a.providers import E3aProviders


def teacher_variance(
    items: list[dict[str, Any]], providers: E3aProviders, *, seed: int, size: int = 300, workers: int = 8
) -> tuple[list[dict[str, Any]], float]:
    """Record k=3 draws on a deterministic stratified subset and use one paired draw per ticket.

    The same sampled draw serves as the always-agent and all arm references for
    a ticket. Gold identifies strata only; the agent receives the ticket text.
    Return individual draws and the cost of the two draws not used for serving.
    """
    if size < 1 or workers < 1:
        raise ValueError("size and workers must be positive")
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        groups[str(item["gold"]["id"])].append(item)
    rng = random.Random(seed)
    for group in groups.values():
        rng.shuffle(group)
    chosen = []
    keys = sorted(groups)
    while keys and len(chosen) < size:
        for key in keys:
            if groups[key] and len(chosen) < size:
                chosen.append(groups[key].pop())
        keys = [key for key in keys if groups[key]]
    draws = [(item, sample) for item in chosen for sample in (1, 2)]

    def call(pair: tuple[dict[str, Any], int]) -> tuple[int, int, Any]:
        item, sample = pair
        result = providers.teacher(
            item["text"],
            item["ticket"]["account_id"],
            item["kb"],
            instructions=instructions_for(item["prompt_version"]),
            sample=sample,
        )
        return item["index"], sample, result

    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = {(index, sample): result for index, sample, result in executor.map(call, draws)}
    rows = []
    overhead = 0.0
    for item in chosen:
        samples = [item["teacher"], results[(item["index"], 1)], results[(item["index"], 2)]]
        used = rng.randrange(3)
        gold = item["gold"]
        for sample, result in enumerate(samples):
            cost = result.envelope.cost.amount
            if cost is None:
                raise ValueError("teacher sample has unknown cost")
            route = result.route or {}
            selected = None
            for event in result.events:
                if event["tool"] == "route_ticket":
                    break
                if event["tool"] == "get_policy":
                    selected = event["entry_id"]
            rows.append(
                {
                    "ticket_index": item["index"],
                    "sample": sample,
                    "used": sample == used,
                    "entry_id": selected,
                    "verified": result.verified,
                    "department": route.get("department"),
                    "priority": route.get("priority"),
                    "gold_entry": gold["id"],
                    "gold_joint_correct": route.get("department") == gold["department"]
                    and route.get("priority") == gold["priority"]
                    and result.verified == gold["identity_check"],
                    "cost_usd": cost,
                    "latency_ms": result.envelope.latency_ms,
                }
            )
            if sample != used:
                overhead += cost
        item["teacher"] = samples[used]
    return rows, overhead
