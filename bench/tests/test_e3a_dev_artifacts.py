import gzip
import json

import pytest

from bench.e3a import dev_artifacts


@pytest.fixture
def artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(dev_artifacts, "ROOT", tmp_path)
    monkeypatch.setattr(dev_artifacts, "SHARDS", tmp_path / "dev-compressed")
    return tmp_path


def test_pack_restore_preserves_multishard_csv_and_gzipped_trace(artifacts):
    originals = {
        "dev-tuning/discovery.csv": b"entry,value\n" + b"alpha,123\n" * 110_000,
        "dev-tuning-joint/dev_control/s4-traces.jsonl.gz": gzip.compress(b'{"trace": 1}\n', mtime=0),
    }
    for name, data in originals.items():
        path = artifacts / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    dev_artifacts.pack(list(originals))
    manifest = json.loads((artifacts / "dev-compressed/manifest.json").read_text())
    assert len(manifest["sources"]["dev-tuning/discovery.csv"]["shards"]) > 1
    for name in originals:
        (artifacts / name).unlink()

    dev_artifacts.restore()

    for name, data in originals.items():
        assert (artifacts / name).read_bytes() == data


def test_restore_refuses_to_overwrite_any_existing_source(artifacts):
    first = artifacts / "dev-tuning/a.csv"
    second = artifacts / "dev-tuning/b.csv"
    first.parent.mkdir(parents=True)
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    dev_artifacts.pack(["dev-tuning/a.csv", "dev-tuning/b.csv"])
    first.unlink()
    second.write_bytes(b"user data")

    with pytest.raises(FileExistsError):
        dev_artifacts.restore()

    assert not first.exists()
    assert second.read_bytes() == b"user data"


def test_restore_detects_corruption_and_removes_incomplete_output(artifacts):
    source = artifacts / "dev-tuning/discovery.csv"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"original data")
    dev_artifacts.pack(["dev-tuning/discovery.csv"])
    source.unlink()
    manifest = json.loads((artifacts / "dev-compressed/manifest.json").read_text())
    shard = manifest["sources"]["dev-tuning/discovery.csv"]["shards"][0]
    (artifacts / "dev-compressed" / shard).write_bytes(gzip.compress(b"corrupt data", mtime=0))

    with pytest.raises(ValueError, match="checksum mismatch"):
        dev_artifacts.restore()

    assert not source.exists()
