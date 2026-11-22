"""Construct auditable compilation records against the bundled contracts.

State hashes are SHA-256 over UTF-8 JSON with sorted keys, compact separators,
non-ASCII characters preserved, and non-finite numbers rejected.  A null state
means the component did not exist; JSON null can still be recorded inside a
state value.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any, Literal

from som import schemas


def state_ref(value: Any) -> dict[str, Any]:
    """Pin an inline JSON-compatible state to its deterministic content hash."""
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    # Round-trip so that the returned state cannot be changed by mutating the input.
    return {
        "value": json.loads(encoded),
        "content_hash": "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
    }


def _patch_versions(from_version: str, to_version: str) -> None:
    pattern = r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    before, after = re.fullmatch(pattern, from_version), re.fullmatch(pattern, to_version)
    if before is None or after is None:
        raise ValueError("patch versions must be release versions in major.minor.patch form")
    old = tuple(map(int, before.groups()))
    new = tuple(map(int, after.groups()))
    if new != (old[0], old[1], old[2] + 1):
        raise ValueError("to_version must be the next patch version")


def s5_record(
    *,
    envelope: dict[str, Any],
    modification_id: str,
    target_ref: str,
    operation: Literal["add", "replace", "remove", "tune"],
    before: Any | None,
    after: Any | None,
    evaluation: dict[str, Any],
    rollback: dict[str, Any],
    status: Literal["proposed", "shadow", "applied", "rejected", "rolled_back"],
    system: str,
    from_version: str,
    to_version: str,
    bump: Literal["none", "patch"] = "patch",
    rationale: str | None = None,
    derived_from: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return a validated S5 response wrapper for a compiled-decision change.

    The caller supplies actual evaluation, rollback and envelope measurements;
    no evidence or operational outcome is inferred. Promotion and demotion can
    be represented by add, replace or remove and their respective state snapshots.
    """
    if bump == "patch":
        _patch_versions(from_version, to_version)
    elif bump == "none":
        if from_version != to_version:
            raise ValueError("a record without a version bump must retain the version")
    else:
        raise ValueError("S5 permits only none or patch version effects")
    if before is None and after is None:
        raise ValueError("at least one component state is required")
    modification: dict[str, Any] = {
        "id": modification_id,
        "scope": "compiled_decision",
        "target_ref": target_ref,
        "operation": operation,
        "before": None if before is None else state_ref(before),
        "after": None if after is None else state_ref(after),
        "evaluation": copy.deepcopy(evaluation),
        "rollback": copy.deepcopy(rollback),
        "status": status,
    }
    if rationale is not None:
        modification["rationale"] = rationale
    if derived_from is not None:
        modification["derived_from"] = copy.deepcopy(derived_from)
    response = copy.deepcopy(envelope)
    response["body"] = {
        "modifications": [modification],
        "version_effect": {"system": system, "from": from_version, "to": to_version, "bump": bump},
    }
    record = {"response": response}
    schemas.validate(record, "s5-self-evolving")
    return record


def version_bump_record(
    *,
    record_id: str,
    created_at: str,
    author: dict[str, Any],
    status: str,
    evidence: dict[str, Any],
    system: str,
    from_version: str,
    to_version: str,
    description: str,
    change_kind: Literal["model_improved", "capability_distilled", "calibration_improved", "bug_fix", "rollback"],
    s5_response_ids: list[str],
) -> dict[str, Any]:
    """Return a validated meta-layer patch record linked to its S5 evidence."""
    _patch_versions(from_version, to_version)
    record = {
        "record_type": "version_bump",
        "id": record_id,
        "created_at": created_at,
        "author": copy.deepcopy(author),
        "status": status,
        "evidence": copy.deepcopy(evidence),
        "system": system,
        "from_version": from_version,
        "to_version": to_version,
        "bump": "patch",
        "changes": [{"kind": change_kind, "description": description, "breaking": False}],
        "provenance": {"s5_response_ids": list(s5_response_ids)},
    }
    schemas.validate(record, "meta-layer")
    return record


def agent_step(
    *,
    index: int,
    action: dict[str, Any],
    observation: dict[str, Any] | None = None,
    reasoning_summary: str | None = None,
    span_id: str | None = None,
    latency_ms: float | None = None,
) -> dict[str, Any]:
    """Return an S4 step validated against the S4 step definition."""
    step: dict[str, Any] = {"index": index, "action": copy.deepcopy(action)}
    if observation is not None:
        step["observation"] = copy.deepcopy(observation)
    if reasoning_summary is not None:
        step["reasoning_summary"] = reasoning_summary
    if span_id is not None:
        step["span_id"] = span_id
    if latency_ms is not None:
        step["latency_ms"] = latency_ms
    schema_id = schemas.load("s4-agentic")["$id"]
    schemas.validator("s4-agentic").evolve(schema={"$ref": f"{schema_id}#/$defs/step"}).validate(step)
    return step
