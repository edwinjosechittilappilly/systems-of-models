"""Published, deterministic E3a policy generation and frozen-policy loading."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from bench.common.labels import BANKING77

SEED = "e3a-policy-v1"
GRANULARITIES = (4, 12)


def _digest(purpose: str, intent: str) -> bytes:
    return hashlib.sha256(f"{SEED}:{purpose}:{intent}".encode()).digest()


def generate_policy(granularity: int) -> list[dict]:
    """Generate one entry per Banking77 intent using the documented seeded partition."""
    if granularity not in GRANULARITIES:
        raise ValueError("granularity must be 4 or 12")
    order = sorted(BANKING77, key=lambda intent: (_digest("partition", intent), intent))
    departments = {intent: f"department_{rank % granularity:02d}" for rank, intent in enumerate(order)}
    entries = []
    for intent in BANKING77:
        rules = _digest("rules", intent)
        entries.append(
            {
                "id": intent,
                "title": intent.replace("_", " ").replace("?", "").title(),
                "department": departments[intent],
                "priority": "high" if rules[0] < 64 else "normal",
                "identity_check": rules[1] < 128,
            }
        )
    return entries


def load_policy(granularity: int) -> list[dict]:
    """Read the pre-generated policy; experiment runs never regenerate it."""
    if granularity not in GRANULARITIES:
        raise ValueError("granularity must be 4 or 12")
    path = Path(__file__).with_name(f"banking_policy_{granularity}.json")
    return json.loads(path.read_text(encoding="utf-8"))
