"""Deterministic E3a discovery and paired per-stream outcome metrics.

Each stream must have one always_agent row per ticket and exactly one row per
arm and ticket. A missing shift_at denotes a no-shift stream. Coverage means
served without the agent, including audited compiled decisions. Recovery is the
start of the first 200-ticket post-shift run satisfying both rolling criteria;
it is only reported once the whole run is observed. Amortization is the first
strictly positive cumulative saving, or the first break-even after the arm has
incurred a cumulative deficit. Both compare all booked costs to always_agent.
"""

from __future__ import annotations

import pandas as pd


_TRUTH = {("retrieval_choice", "search_policy"), ("branch", "verify_identity")}


def discovery_rows(report):
    """Return all candidate rows, including rejections, with frozen truth labels."""
    return [
        {**row, "is_true": (row["kind"], row["tool"]) in _TRUTH}
        for row in report.to_rows()
    ]


def discovery_summary(report):
    """Score accepted decisions against both frozen truths, including absent ones.

    Precision is undefined (None) when nothing was accepted; recall uses the
    fixed two-decision ground truth, not only candidates the miner happened to see.
    """
    rows = discovery_rows(report)
    found = {(row["kind"], row["tool"]) for row in rows if row["accepted"] and row["is_true"]}
    accepted = sum(bool(row["accepted"]) for row in rows)
    return {
        "discovery_precision": len(found) / accepted if accepted else None,
        "discovery_recall": len(found) / len(_TRUTH),
        "discovery_true_positives": len(found),
        "discovery_accepted": accepted,
        "discovery_rejected": len(rows) - accepted,
        "ambiguous_retrieval_count": report.ambiguous_retrieval_count,
    }


def summarize_streams(tickets: pd.DataFrame) -> pd.DataFrame:
    """Return one CSV-ready summary row per stream and arm.

    Detection delays count ticket-index differences and audited tickets from
    shift through the first demotion (inclusive), respectively. A shifted arm
    with no post-shift demotion is a detection miss. False alarms count every
    pre-shift demotion, or every demotion when there is no shift. Amortization
    and recovery ticket fields are absolute indices; their delay/horizon fields
    are differences from the shift and first ticket, respectively. Undefined
    quantities are None (and become empty cells on CSV export).
    """
    required = {"ticket_index", "shift_at", "arm", "stream", "gold_joint_correct",
                "teacher_agreement", "served_by", "cost_usd", "demoted", "audited", "promoted"}
    missing = required - set(tickets.columns)
    if missing:
        raise ValueError(f"Missing ticket columns: {sorted(missing)}")
    if tickets.duplicated(["stream", "arm", "ticket_index"]).any():
        raise ValueError("Duplicate stream/arm/ticket_index")
    rows = []
    for stream, stream_data in tickets.groupby("stream", sort=True, dropna=False):
        shifts = stream_data["shift_at"].dropna().unique()
        if len(shifts) > 1 or (len(shifts) and stream_data["shift_at"].isna().any()):
            raise ValueError(f"Inconsistent shift_at for stream {stream!r}")
        shift = shifts[0] if len(shifts) else None
        reference = stream_data[stream_data["arm"] == "always_agent"].sort_values("ticket_index").set_index("ticket_index")
        if reference.empty:
            raise ValueError(f"Missing always_agent for stream {stream!r}")
        for arm, data in stream_data.groupby("arm", sort=True, dropna=False):
            data = data.sort_values("ticket_index").set_index("ticket_index")
            if not data.index.equals(reference.index):
                raise ValueError(f"Ticket indices differ from always_agent for {stream!r}/{arm!r}")
            idx = data.index
            post = idx >= shift if shift is not None else pd.Series(False, index=idx).to_numpy()
            demoted = data["demoted"].fillna(False).astype(bool)
            audited = data["audited"].fillna(False).astype(bool)
            detections = data.index[post & demoted.to_numpy()]
            detection = detections[0] if len(detections) else None
            false_alarms = int((demoted.to_numpy() & ~post).sum())
            coverage = data["served_by"].ne("agent").astype(float)
            accuracy = data["gold_joint_correct"].astype(float)
            baseline_accuracy = reference["gold_joint_correct"].astype(float)
            rolling_ok = (accuracy.rolling(100, min_periods=100).mean() >=
                          baseline_accuracy.rolling(100, min_periods=100).mean() - 0.02)
            coverage_ok = coverage.rolling(100, min_periods=100).mean() >= 0.5
            good = rolling_ok & coverage_ok & post
            runs = good.rolling(200, min_periods=200).sum()
            ends = [i for i, value in enumerate(runs) if value == 200 and
                    idx[i] - idx[i - 199] == 199]
            recovery = idx[ends[0] - 199] if ends else None
            savings = (reference["cost_usd"].astype(float) - data["cost_usd"].astype(float)).cumsum()
            deficit_seen = False
            amortization = None
            for ticket, saving in savings.items():
                deficit_seen = deficit_seen or saving < 0
                if saving > 0 or (deficit_seen and saving >= 0):
                    amortization = ticket
                    break
            rows.append({
                "stream": stream, "arm": arm, "tickets": len(data), "shift_at": shift,
                "joint_accuracy": accuracy.mean(),
                "teacher_agreement": data["teacher_agreement"].mean(),
                "coverage": coverage.mean(), "total_cost_usd": data["cost_usd"].sum(),
                "cost_per_ticket_usd": data["cost_usd"].mean(),
                "cumulative_excess_error": (baseline_accuracy - accuracy).sum(),
                "postshift_cumulative_excess_error": (baseline_accuracy - accuracy)[post].sum() if shift is not None else None,
                "promotions": int(data["promoted"].fillna(False).astype(bool).sum()),
                "demotions": int(demoted.sum()), "audits": int(audited.sum()),
                "false_demotions": false_alarms,
                "detection_ticket": detection,
                "detection_delay_tickets": detection - shift if detection is not None else None,
                "detection_delay_audits": int(audited[(idx >= shift) & (idx <= detection)].sum()) if detection is not None else None,
                "detection_miss": detection is None if shift is not None else None,
                "recovery_ticket": recovery,
                "recovery_delay_tickets": recovery - shift if recovery is not None else None,
                "amortization_ticket": amortization,
                "amortization_horizon_tickets": amortization - idx[0] if amortization is not None else None,
            })
    return pd.DataFrame(rows)
