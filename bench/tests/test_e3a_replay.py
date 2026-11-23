import gzip
import json
import sys
from types import SimpleNamespace

import pandas as pd
import pytest

from bench.e3a import run
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


@pytest.mark.parametrize("output", ["evaluation", "evaluation/child", "."])
def test_resume_rejects_original_directory_and_overlaps(tmp_path, monkeypatch, output):
    monkeypatch.setattr(run, "ROOT", tmp_path)
    original = tmp_path / "results" / "e3a" / "evaluation"
    original.mkdir(parents=True)
    marker = original / "budget_stop.json"
    marker.write_text("original")
    target = original.parent if output == "." else original.parent / output
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run",
            "--resume-eval",
            "--streams",
            "eval",
            "--mode",
            "record",
            "--allow-eval",
            "--output-dir",
            str(target),
        ],
    )
    with pytest.raises(SystemExit):
        run.main()
    assert marker.read_text() == "original"


def test_resume_reconstructs_first_two_before_live_work(tmp_path, monkeypatch):
    from bench.e3a import baselines, lifecycle_runner

    monkeypatch.setattr(run, "ROOT", tmp_path)
    original = tmp_path / "results" / "e3a" / "evaluation"
    original.mkdir(parents=True)
    tasks = tmp_path / "tasks"
    (tasks / "streams").mkdir(parents=True)
    for filename in ("banking_policy_4.json", "banking_policy_12.json", "clinc_map.json"):
        (tasks / filename).write_text("{}")
    for name in run.EVAL_STREAMS:
        (tasks / "streams" / f"{name}.csv").write_text("value\n1\n")
    for name in run.RESUMED_STREAMS:
        (original / name).mkdir()
        (original / name / "trace").write_text(name)
        (original / f"{name}_summary.csv").write_text("original summary\n")
    (original / "seed_11_control_teacher_variance.csv").write_text("original variance\n")

    class Cache:
        def __init__(self, *args, mode, **kwargs):
            self.mode = mode
            self.hits = self.misses = 0

    class Providers:
        def __init__(self, mode, budget):
            self.agent_cache = Cache(mode=mode)
            self.s1 = SimpleNamespace(cache=Cache(mode=mode))
            self.writer = SimpleNamespace(cache=Cache(mode=mode))

    class Embedder:
        def __init__(self, cache):
            self.cache = cache
            self.timing_cache = Cache(mode=cache.mode)

    class Budget:
        def __init__(self, caps, initial):
            assert caps == {"openai": 75.0, "typesafe": 8.00}
            self.spent = {"openai": 20.0, "typesafe": 2.0}

    class Stop(Exception):
        pass

    modes = []

    def collect(items, providers, *, workers):
        modes.append(
            (items[0]["index"], providers.agent_cache.mode, providers.s1.cache.mode, providers.writer.cache.mode)
        )
        if len(modes) == 3:
            raise Stop
        return []

    teacher = SimpleNamespace(route=None, verified=False, events=[])
    monkeypatch.setattr(run, "JsonCache", Cache)
    monkeypatch.setattr(run, "CachedEmbedder", Embedder)
    monkeypatch.setattr(run, "E3aProviders", Providers)
    monkeypatch.setattr(run, "JournaledBudget", Budget)
    monkeypatch.setattr(run, "previous_openai_spend", lambda: 20.0)
    monkeypatch.setattr(run, "items_for_stream", lambda frame, phase_limit: ([{"index": 0, "teacher": teacher}], 1))
    monkeypatch.setattr(run, "collect", collect)
    monkeypatch.setattr(run, "teacher_variance", lambda *args, **kwargs: ([], 1.0))
    monkeypatch.setattr(run, "always_agent", lambda *args: [])
    monkeypatch.setattr(run, "_verify_reconstructed_primary", lambda *args: None)
    monkeypatch.setattr(baselines, "run_baseline", lambda *args, **kwargs: [])

    def lifecycle(items, providers, settings):
        assert settings["embedder"].cache.mode == "replay"
        assert settings["embedder"].timing_cache.mode == "replay"
        assert settings["timing_cache"].mode == "replay"
        return {arm: [{"ticket_index": 0, "training_available_labels": 1}] for arm in lifecycle_runner.FACTORIAL}

    monkeypatch.setattr(lifecycle_runner, "run_lifecycle", lifecycle)
    output = tmp_path / "resumed"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run",
            "--resume-eval",
            "--streams",
            "eval",
            "--mode",
            "record",
            "--allow-eval",
            "--output-dir",
            str(output),
        ],
    )
    with pytest.raises(Stop):
        run.main()
    assert modes == [(0, "replay", "replay", "replay")] * 2 + [(0, "record", "record", "record")]
    for name in run.RESUMED_STREAMS:
        assert (output / f"{name}_summary.csv").read_text() == "original summary\n"
        assert (output / name / "trace").read_text() == name
    assert (output / "seed_11_control_teacher_variance.csv").read_text() == "original variance\n"


def test_reconstructed_primary_requires_all_arms_and_identical_non_timing_data(tmp_path):
    table = pd.DataFrame([{"arm": "a", "ticket_index": 1, "cost_usd": 0.5, "latency_ms": 20, "local_cpu_seconds": 2}])
    path = tmp_path / "seed_11_control_a.csv"
    path.write_text("arm,ticket_index,cost_usd,latency_ms,local_cpu_seconds\na,1,0.5,10,1\n")
    run._verify_reconstructed_primary(table, tmp_path, "seed_11_control", {"a"})

    with pytest.raises(RuntimeError, match="primary arms differ"):
        run._verify_reconstructed_primary(table, tmp_path, "seed_11_control", {"a", "b"})
    table.loc[0, "cost_usd"] = 0.6
    with pytest.raises(RuntimeError, match="primary arm a differs"):
        run._verify_reconstructed_primary(table, tmp_path, "seed_11_control", {"a"})
    path.unlink()
    with pytest.raises(RuntimeError, match="missing original primary artifact"):
        run._verify_reconstructed_primary(table, tmp_path, "seed_11_control", {"a"})
