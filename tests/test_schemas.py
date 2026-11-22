import copy
import json

import pytest

from som import schemas
from som.cli import main


def test_every_bundled_example_matches_its_schema():
    results = schemas.check_examples()
    assert results, "no examples found"
    assert [name for name, error in results if error] == []


def test_envelope_requires_basis_when_confidence_is_a_number():
    example = schemas._schema_dir() / "examples" / "envelope.example.json"
    envelope = json.loads(example.read_text("utf-8"))
    broken = copy.deepcopy(envelope)
    broken["confidence"] = 0.9
    broken.pop("confidence_basis", None)
    with pytest.raises(schemas.ValidationError):
        schemas.validate(broken, "envelope")


def test_unknown_schema_name_is_rejected():
    with pytest.raises(KeyError):
        schemas.load("s9-telepathy")


def test_cli_validate_reports_invalid_file(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"id": "x"}))
    assert main(["validate", str(bad), "--schema", "envelope"]) == 1
    assert "required property" in capsys.readouterr().err
