from types import SimpleNamespace

from bench.e3a.variance import teacher_variance


class Teacher:
    def __init__(self, entry):
        self.route = {"department": "cards", "priority": "normal"}
        self.verified = False
        self.events = [{"tool": "get_policy", "entry_id": entry}, {"tool": "route_ticket"}]
        self.envelope = SimpleNamespace(cost=SimpleNamespace(amount=0.01), latency_ms=20)


class Providers:
    def teacher(self, text, account_id, kb, *, instructions, sample):
        return Teacher(f"{text}-{sample}")


def test_three_independent_samples_have_one_paired_choice_and_cost_two_unused_draws():
    items = [
        {
            "index": i,
            "text": str(i),
            "ticket": {"account_id": str(i)},
            "kb": None,
            "gold": {"id": str(i % 2), "department": "cards", "priority": "normal", "identity_check": False},
            "teacher": Teacher(f"{i}-0"),
            "prompt_version": "original",
        }
        for i in range(6)
    ]
    rows, overhead = teacher_variance(items, Providers(), size=4, seed=9, workers=2)
    assert len(rows) == 12
    assert sum(row["used"] for row in rows) == 4
    assert abs(overhead - 0.08) < 1e-9
    for item in items:
        selected = [row for row in rows if row["ticket_index"] == item["index"] and row["used"]]
        if selected:
            assert item["teacher"].events[0]["entry_id"] == selected[0]["entry_id"]
