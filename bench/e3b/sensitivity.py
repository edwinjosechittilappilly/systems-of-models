"""Post-hoc held-out-label and transcript-ablation sensitivity analyses."""

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from typing import Any


def _accuracy(correct: int, n: int) -> dict[str, int | float]:
    return {"n": n, "correct": correct, "accuracy": correct / n if n else float("nan")}


def sensitivity(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Summarize held-out majorities, the ablation, and cancellation text echoes.

    Majorities are fitted to full-state held-out teacher labels per domain and
    candidate, with alphabetical tie-breaking. They are descriptive and are not
    an actual baseline. Matched majority accuracy uses exactly those ablation
    rows with a prediction, a teacher label, and a fitted decision majority;
    ablation teacher accuracy uses all ablation rows with both labels. Refusals
    and missing teacher labels are excluded, as in the main teacher metric.
    Empty denominators have NaN accuracy. Transcript entries are already
    bounded to messages preceding the decision by the extractor.
    """
    counts: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    ablated = []
    echoes = 0
    for row in rows:
        domain, candidate = row["domain"], row["candidate"]
        teacher = row["teacher"]
        if row["state_variant"] == "full":
            if teacher is not None:
                counts[(domain, candidate)][teacher] += 1
            if (
                domain == "retail"
                and candidate == "cancel_pending_order.reason"
                and isinstance(teacher, str)
                and teacher
                and any(
                    message.get("role") == "assistant"
                    and isinstance(message.get("content"), str)
                    and teacher in message["content"]
                    for message in row["state"]["transcript"]
                )
            ):
                echoes += 1
        elif row["state_variant"] == "user-and-tools-only" and row["prediction"] is not None and teacher is not None:
            ablated.append(row)

    majorities: dict[str, dict[str, str]] = {}
    for (domain, candidate), labels in sorted(counts.items()):
        majority = min(labels, key=lambda label: (-labels[label], label))
        majorities.setdefault(domain, {})[candidate] = majority

    teacher_correct = sum(row["prediction"] == row["teacher"] for row in ablated)
    matched = [row for row in ablated if row["candidate"] in majorities.get(row["domain"], {})]
    majority_correct = sum(majorities[row["domain"]][row["candidate"]] == row["teacher"] for row in matched)
    return {
        "held_out_majority": majorities,
        "matched_majority": _accuracy(majority_correct, len(matched)),
        "user_and_tools_only_teacher": _accuracy(teacher_correct, len(ablated)),
        "cancellation_reason_assistant_echo_count": echoes,
    }
