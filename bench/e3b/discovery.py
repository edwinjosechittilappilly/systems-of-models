"""Candidate-level discovery results and simple acceptance baselines."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from bench.e3b.metrics import discovery_metrics, wilson

_DOMAINS = ("retail", "airline", "pooled")
_KINDS = ("all", "branch", "tool_argument", "retrieval_choice")


def _identity(row: Mapping[str, Any]) -> tuple[Any, Any, Any]:
    return row["domain"], row["kind"], row["name"]


def discovery_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Summarize miner discovery and acceptance baselines by domain and kind.

    Input rows contain domain, kind, name, accepted and judgement. Candidate
    identities are (domain, kind, name); repeated identities count once in each
    relevant predicted or judgement set. The returned rows contain domain,
    method, kind, candidates, tp, fp, fn, precision, recall, precision_ci and
    recall_ci. Undefined ratios and intervals are NaN. All domain/kind groups
    are emitted even when empty; baselines are reported only for kind ``all``.
    """
    rows = list(rows)
    result = []
    for domain in _DOMAINS:
        domain_rows = [row for row in rows if domain == "pooled" or row["domain"] == domain]
        for method, kinds in (("miner", _KINDS), ("accept_all", ("all",)), ("accept_branches", ("all",))):
            for kind in kinds:
                group = [row for row in domain_rows if kind == "all" or row["kind"] == kind]
                candidates = {_identity(row) for row in group}
                gold = {_identity(row) for row in group if row["judgement"]}
                predicted = {
                    _identity(row)
                    for row in group
                    if method == "accept_all"
                    or (method == "accept_branches" and row["kind"] == "branch")
                    or (method == "miner" and row["accepted"])
                }
                metrics = discovery_metrics(predicted, gold)
                tp, fp, fn = metrics["tp"], metrics["fp"], metrics["fn"]
                result.append(
                    {
                        "domain": domain,
                        "method": method,
                        "kind": kind,
                        "candidates": len(candidates),
                        **metrics,
                        "precision_ci": wilson(tp, tp + fp),
                        "recall_ci": wilson(tp, tp + fn),
                    }
                )
    return result
