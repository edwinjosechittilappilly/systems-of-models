import gzip
import json

from bench.e3a.run import compare_replay


def test_replay_comparison_excludes_only_measured_timing_and_reports_provenance(tmp_path):
    original, replay = tmp_path / "original", tmp_path / "replay"
    original.mkdir()
    replay.mkdir()
    for directory, latency, timestamp, mode in ((original, "10", 100, "record"), (replay, "20", 200, "replay")):
        (directory / "tickets.csv").write_text(
            f"ticket_index,route,cost_usd,latency_ms,local_cpu_seconds\n1,billing,0.5,{latency},1\n"
        )
        (directory / "s5-records.jsonl").write_text(
            json.dumps({"created_at": timestamp, "latency_ms": latency, "decision": "promote"}) + "\n"
        )
        (directory / "manifest.json").write_text(json.dumps({"mode": mode}) + "\n")
        with (
            (directory / "s4-traces.jsonl.gz").open("wb") as raw,
            gzip.GzipFile(fileobj=raw, mode="wb", mtime=timestamp) as stream,
        ):
            stream.write(b'{"route":"billing"}\n')

    report = compare_replay(original, replay)
    assert report["deterministic_identical"]
    assert not report["deterministic"]["tickets.csv"]["byte_identical"]
    assert report["deterministic"]["tickets.csv"]["excluded_timing_fields"] == ["latency_ms", "local_cpu_seconds"]
    assert report["deterministic"]["s5-records.jsonl"]["excluded_timing_fields"] == ["created_at", "latency_ms"]
    assert not report["deterministic"]["s4-traces.jsonl.gz"]["byte_identical"]
    assert '"record"' in report["observed_metadata"]["manifest.json"]["diff"]
    assert json.loads((original / "manifest.json").read_text())["mode"] == "record"


def test_replay_comparison_detects_changes_and_missing_artifacts(tmp_path):
    original, replay = tmp_path / "original", tmp_path / "replay"
    original.mkdir()
    replay.mkdir()
    (original / "h3.csv").write_text("arm,cost_usd\na,1\n")
    (replay / "h3.csv").write_text("arm,cost_usd\na,2\n")
    (original / "h4.csv").write_text("arm,decision\na,yes\n")

    report = compare_replay(original, replay)
    assert not report["deterministic_identical"]
    assert "-a,1\n+a,2\n" in report["deterministic"]["h3.csv"]["diff"]
    assert report["deterministic"]["h4.csv"]["status"] == "missing_replay"


def test_empty_directories_do_not_prove_reproducibility(tmp_path):
    original, replay = tmp_path / "original", tmp_path / "replay"
    original.mkdir()
    replay.mkdir()
    assert not compare_replay(original, replay)["deterministic_identical"]
