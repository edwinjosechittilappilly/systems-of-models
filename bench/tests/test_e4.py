import json
from types import SimpleNamespace

import som
from bench.e4 import run


def test_validation_counts_an_envelope_that_breaks_the_contract(tmp_path, monkeypatch):
    good = json.loads((run.FIXTURES / "openai_decisions.json").read_text())
    team = som.Choice("team", "Which team?", {"billing": "charges", "cards": "cards", "fraud": "fraud"})
    fake = SimpleNamespace(decisions=SimpleNamespace(create=lambda **_: good))
    envelope = som.OpenAIDecisions(client=fake).decide("x", [team]).envelope.to_dict()
    broken = {**envelope, "cost": {**envelope["cost"], "basis": "billed"}}
    lines = [json.dumps({"response": {"envelope": envelope}}), json.dumps({"response": {"envelope": broken}})]
    (tmp_path / "ns.jsonl").write_text("\n".join(lines) + "\n")
    monkeypatch.setattr(run, "CACHE_DIR", tmp_path)
    [row] = run.validate_envelopes()
    assert (row["envelopes"], row["valid"], row["invalid"]) == (2, 1, 1)
    assert "billed" in row["first_error"]


def test_round_trip_keeps_every_decisions_field_and_the_responses_answer():
    rows = {row["adapter"]: row for row in run.round_trip()}
    assert rows["OpenAI /v1/decisions"]["recovered_share"] == 1.0
    assert "output[0].content[0].text" not in rows["OpenAI /v1/responses"]["dropped_examples"]
