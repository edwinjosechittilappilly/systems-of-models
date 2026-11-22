import json
from types import SimpleNamespace

import som
from bench.e4 import run


def _decisions_envelope() -> dict:
    good = json.loads((run.FIXTURES / "openai_decisions.json").read_text())
    team = som.Choice("team", "Which team?", {"billing": "charges", "cards": "cards", "fraud": "fraud"})
    fake = SimpleNamespace(decisions=SimpleNamespace(create=lambda **_: good))
    return som.OpenAIDecisions(client=fake).decide("x", [team]).envelope.to_dict()


def _validate(tmp_path, monkeypatch, envelopes):
    lines = [json.dumps({"response": {"envelope": envelope}}) for envelope in envelopes]
    (tmp_path / "ns.jsonl").write_text("\n".join(lines) + "\n")
    monkeypatch.setattr(run, "CACHE_DIR", tmp_path)
    return run.validate_envelopes()


def test_validation_counts_an_envelope_that_breaks_the_contract(tmp_path, monkeypatch):
    envelope = _decisions_envelope()
    broken = {**envelope, "cost": {**envelope["cost"], "basis": "billed"}}
    [row] = _validate(tmp_path, monkeypatch, [envelope, broken])
    assert (row["envelopes"], row["valid"], row["invalid"]) == (2, 1, 1)
    assert "billed" in row["first_error"]


def test_a_proposed_system_envelope_is_validated_as_a_bare_envelope(tmp_path, monkeypatch):
    proposed = {**_decisions_envelope(), "system": "x.proposed_tier"}
    [row] = _validate(tmp_path, monkeypatch, [proposed])
    assert (row["system"], row["valid"], row["invalid"]) == ("x.proposed_tier", 1, 0)


def test_round_trip_keeps_every_decisions_field_and_the_responses_answer():
    rows = {row["adapter"]: row for row in run.round_trip()}
    assert rows["OpenAI /v1/decisions"]["recovered_share"] == 1.0
    assert "output[0].content[0].text" not in rows["OpenAI /v1/responses"]["dropped_examples"]
