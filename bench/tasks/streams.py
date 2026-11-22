"""Frozen E3a streams and their silent policy changes.

Run ``python -m bench.tasks.streams`` to regenerate the CSVs from the pinned
Banking77 and CLINC150 training data. Source indices refer to rows returned by
``bench.common.data.load``. Evaluation pools and the remaining development
pool are disjoint; development has the remaining rows rather than 2,400.

Each restructure splits a deterministic sample of post-shift tickets into a
new entry. A ``policy cohort revised`` ticket suffix identifies the split and
the new entry title names that cohort. Split entries have a different
department from their parent.
Only the frozen banking and credit-card CLINC intents below are eligible;
classes with no direct Banking77 counterpart have their own entry. The mapping
is frozen in clinc_map.json.
Neither gold entry IDs nor the changed policy are part of the agent prompt.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from bench.common import data
from bench.common.labels import BANKING77, CLINC150

STREAM_DIR = Path(__file__).with_name("streams")
MAP_PATH = Path(__file__).with_name("clinc_map.json")
SEEDS = (11, 23, 37)
POOL_SEED = 20261122
TICKETS = 2400
SHIFT_AT = 1200
SEVERITIES = (0.05, 0.15, 0.30)
CLINC_FRACTION = 0.20
CLINC_BANKING_INTENTS = frozenset(
    {
        "account_blocked",
        "report_lost_card",
        "freeze_account",
        "interest_rate",
        "bill_balance",
        "improve_credit_score",
        "balance",
        "exchange_rate",
        "credit_limit",
        "expiration_date",
        "routing",
        "card_declined",
        "rewards_balance",
        "bill_due",
        "transactions",
        "credit_score",
        "report_fraud",
        "spending_history",
        "damaged_card",
        "pin_change",
        "replacement_card_duration",
        "new_card",
        "direct_deposit",
        "credit_limit_change",
        "pay_bill",
        "order_checks",
        "apr",
        "transfer",
        "international_fees",
        "min_payment",
    }
)


def load_clinc_map() -> dict[str, str | None]:
    """Return the frozen complete map; null means a new CLINC intent."""
    mapping = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    if set(mapping) != set(CLINC150) - {"oos"} or any(
        value is not None and value not in BANKING77 for value in mapping.values()
    ):
        raise ValueError("invalid CLINC-to-Banking77 mapping")
    return mapping


def build_streams(banking: pd.DataFrame, clinc: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Build deterministic, paired conditions from disjoint source rows.

    Evaluation streams contain 2,400 tickets and change after the first 1,200.
    Development uses all remaining Banking77 rows, split halfway. CLINC rows
    are disjoint between pools and replace 20% of post-shift tickets, rounded
    half up with at least one replacement. This fixed mixture avoids exhausting
    the eligible banking/credit-card CLINC train pool. Restructure severity
    uses the same rounding without a minimum.
    """
    if len(banking) <= len(SEEDS) * TICKETS:
        raise ValueError("Banking77 train pool must leave rows for development")
    mapping = load_clinc_map()
    if not {"text", "intent"}.issubset(banking.columns) or not {"text", "intent"}.issubset(clinc.columns):
        raise ValueError("source frames need text and intent columns")
    if not set(banking["intent"]).issubset(BANKING77):
        raise ValueError("unknown Banking77 intent")
    if not set(clinc["intent"]).issubset(CLINC150):
        raise ValueError("unknown CLINC intent")

    bank_order = np.random.default_rng(POOL_SEED).permutation(len(banking))
    clinc_indices = np.flatnonzero(clinc["intent"].isin(CLINC_BANKING_INTENTS).to_numpy())
    clinc_order = np.random.default_rng(POOL_SEED + 1).permutation(clinc_indices)
    dev_size = len(banking) - len(SEEDS) * TICKETS
    dev_post = dev_size - dev_size // 2
    needed_clinc = len(SEEDS) * int(SHIFT_AT * CLINC_FRACTION + 0.5) + max(1, int(dev_post * CLINC_FRACTION + 0.5))
    if len(clinc_order) < needed_clinc:
        raise ValueError("CLINC train pool is too small for disjoint streams")

    result = {}
    clinc_offset = 0
    for pool, seed, indices in [
        *((f"seed_{seed}", seed, bank_order[i * TICKETS : (i + 1) * TICKETS]) for i, seed in enumerate(SEEDS)),
        ("dev", POOL_SEED, bank_order[len(SEEDS) * TICKETS :]),
    ]:
        indices = np.random.default_rng(seed).permutation(indices)
        start = SHIFT_AT if pool != "dev" else len(indices) // 2
        base = banking.iloc[indices][["text", "intent"]].reset_index(drop=True).copy()
        base.insert(0, "ticket", np.arange(len(base)))
        base["source"] = "banking77"
        base["source_index"] = indices
        base["base_entry_id"] = base["intent"]
        base["entry_id"] = base["intent"]
        base["shift_kind"] = "none"
        base["new_intent"] = False
        base["prompt_version"] = "original"
        result[f"{pool}_control"] = base.copy()

        post_count = len(base) - start
        order = np.random.default_rng(seed + 1).permutation(np.arange(start, len(base)))
        for severity in SEVERITIES:
            shifted = base.copy()
            count = int(post_count * severity + 0.5)
            chosen = order[:count]
            shifted.loc[chosen, "entry_id"] = "split::" + shifted.loc[chosen, "intent"]
            shifted.loc[chosen, "text"] = shifted.loc[chosen, "text"] + " [policy cohort revised]"
            shifted.loc[chosen, "shift_kind"] = "restructure"
            result[f"{pool}_restructure_{int(severity * 100):02d}"] = shifted
            if severity == 0.15:
                visible = shifted.copy()
                visible.loc[start:, "prompt_version"] = "visible_shift"
                result[f"{pool}_visible"] = visible

        clinc_count = max(1, int(post_count * CLINC_FRACTION + 0.5))
        chosen = np.random.default_rng(seed + 2).permutation(np.arange(start, len(base)))[:clinc_count]
        selected = clinc_order[clinc_offset : clinc_offset + clinc_count]
        clinc_offset += clinc_count
        shifted = base.iloc[chosen].copy()
        rows = clinc.iloc[selected].reset_index(drop=True)
        mapped = [mapping[intent] for intent in rows["intent"]]
        entry_ids = [
            target if target is not None else f"clinc::{intent}"
            for intent, target in zip(rows["intent"], mapped, strict=True)
        ]
        shifted["text"] = pd.array(rows["text"], dtype=base["text"].dtype)
        shifted["intent"] = pd.array(rows["intent"], dtype=base["intent"].dtype)
        shifted["source"] = "clinc150"
        shifted["source_index"] = selected
        shifted["base_entry_id"] = pd.array([target or "" for target in mapped], dtype=base["base_entry_id"].dtype)
        shifted["entry_id"] = pd.array(entry_ids, dtype=base["entry_id"].dtype)
        shifted["shift_kind"] = "clinc"
        shifted["new_intent"] = [target is None for target in mapped]
        remaining = base.loc[~base["ticket"].isin(chosen)]
        result[f"{pool}_clinc"] = pd.concat([remaining, shifted], ignore_index=True).sort_values(
            "ticket", ignore_index=True
        )
    return result


def shifted_policy(base_entries: list[dict], stream: pd.DataFrame, granularity: int) -> list[dict]:
    """Return a KB snapshot with all post-shift entries, without changing the prompt.

    Split entries route to the next department in the frozen partition and
    inherit their parent's priority and identity rule. Novel CLINC entries use
    SHA-256 of their ID to choose a department, priority and identity rule. The
    resulting snapshot is installed only at the shift boundary.
    """
    if granularity not in (4, 12):
        raise ValueError("granularity must be 4 or 12")
    entries = [dict(entry) for entry in base_entries]
    by_id = {entry["id"]: entry for entry in entries}
    if len(by_id) != len(entries):
        raise ValueError("duplicate policy entry ID")
    for entry_id in sorted(set(stream["entry_id"])):
        if entry_id in by_id:
            continue
        if entry_id.startswith("split::"):
            parent = entry_id.removeprefix("split::")
            if parent not in by_id:
                raise ValueError(f"missing parent policy entry: {parent}")
            entry = dict(by_id[parent])
            department = entry["department"]
            number = int(department.removeprefix("department_"))
            entry.update(
                id=entry_id,
                title=f"{entry['title']} - Policy Cohort Revised",
                department=f"department_{(number + 1) % granularity:02d}",
            )
        elif entry_id.startswith("clinc::"):
            intent = entry_id.removeprefix("clinc::")
            if intent not in load_clinc_map() or load_clinc_map()[intent] is not None:
                raise ValueError(f"not a novel CLINC intent: {intent}")
            digest = hashlib.sha256(f"e3a-clinc-v1:{intent}".encode()).digest()
            entry = {
                "id": entry_id,
                "title": intent.replace("_", " ").title(),
                "department": f"department_{digest[0] % granularity:02d}",
                "priority": "high" if digest[1] < 64 else "normal",
                "identity_check": digest[2] < 128,
            }
        else:
            raise ValueError(f"unknown governing policy entry: {entry_id}")
        entries.append(entry)
        by_id[entry_id] = entry
    return entries


def write_streams(directory: Path = STREAM_DIR) -> None:
    """Regenerate the checked-in CSVs using checksum-verified training data."""
    streams = build_streams(data.load("banking77", "train"), data.load("clinc150", "train"))
    directory.mkdir(parents=True, exist_ok=True)
    for name, frame in streams.items():
        frame.to_csv(directory / f"{name}.csv", index=False, lineterminator="\n")


if __name__ == "__main__":
    write_streams()
