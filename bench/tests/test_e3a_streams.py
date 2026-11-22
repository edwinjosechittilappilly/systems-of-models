"""Offline specifications for E3a's source pools and policy shifts."""

import pandas as pd
import pytest

from bench.common.labels import BANKING77, CLINC150
from bench.tasks.policy import generate_policy
from bench.tasks.streams import (
    CLINC_BANKING_INTENTS,
    SEEDS,
    SHIFT_AT,
    TICKETS,
    build_streams,
    load_clinc_map,
    shifted_policy,
)


@pytest.fixture(scope="module")
def streams():
    banking = pd.DataFrame(
        {
            "text": [f"banking ticket {i}" for i in range(10003)],
            "intent": [BANKING77[i % len(BANKING77)] for i in range(10003)],
        }
    )
    clinc = pd.DataFrame(
        {
            "text": [f"clinc ticket {i}" for i in range(6000)],
            "intent": [CLINC150[i % len(CLINC150)] for i in range(6000)],
        }
    )
    return build_streams(banking, clinc)


def test_frozen_map_is_complete_and_distinguishes_new_intents():
    mapping = load_clinc_map()
    assert set(mapping) == set(CLINC150) - {"oos"}
    assert mapping["pin_change"] == "change_pin"
    assert mapping["weather"] is None


def test_disjoint_pools_and_exact_shift_severity(streams):
    pools = [f"seed_{seed}" for seed in SEEDS] + ["dev"]
    bank_sources = []
    clinc_sources = []
    for pool in pools:
        control = streams[f"{pool}_control"]
        start = SHIFT_AT if pool != "dev" else len(control) // 2
        if pool != "dev":
            assert len(control) == TICKETS
        bank_sources.append(set(control.source_index))
        assert len(bank_sources[-1]) == len(control)
        assert (control.entry_id == control.base_entry_id).all()
        assert (control.prompt_version == "original").all()
        for severity, expected in [(5, 60), (15, 180), (30, 360)]:
            shifted = streams[f"{pool}_restructure_{severity:02d}"]
            pd.testing.assert_frame_equal(shifted.iloc[:start], control.iloc[:start])
            changed = shifted.entry_id != shifted.base_entry_id
            assert changed.sum() == (expected if pool != "dev" else int((len(control) - start) * severity / 100 + 0.5))
            assert (shifted.loc[changed, "shift_kind"] == "restructure").all()
            assert (shifted.text.str.endswith(" [policy cohort revised]") == changed).all()
        clinc = streams[f"{pool}_clinc"]
        pd.testing.assert_frame_equal(clinc.iloc[:start], control.iloc[:start])
        post = clinc.iloc[start:]
        replaced = post[post.source == "clinc150"]
        assert len(replaced) == max(1, int((len(control) - start) * 0.20 + 0.5))
        assert set(replaced.intent) <= CLINC_BANKING_INTENTS
        assert (replaced.new_intent == replaced.entry_id.str.startswith("clinc::")).all()
        untouched = clinc.source == "banking77"
        pd.testing.assert_frame_equal(clinc.loc[untouched], control.loc[untouched])
        clinc_sources.append(set(replaced.source_index))
        assert len(clinc_sources[-1]) == len(replaced)
        visible = streams[f"{pool}_visible"]
        reference = streams[f"{pool}_restructure_15"]
        pd.testing.assert_frame_equal(visible.drop(columns="prompt_version"), reference.drop(columns="prompt_version"))
        assert (visible.prompt_version.iloc[:start] == "original").all()
        assert (visible.prompt_version.iloc[start:] == "visible_shift").all()
    for sources in (bank_sources, clinc_sources):
        assert sum(map(len, sources)) == len(set.union(*sources))


@pytest.mark.parametrize("granularity", [4, 12])
def test_shift_policy_contains_real_entries_without_mutating_base(streams, granularity):
    base = generate_policy(granularity)
    original = {entry["id"]: dict(entry) for entry in base}
    for condition in ("restructure_15", "clinc"):
        stream = streams[f"seed_{SEEDS[0]}_{condition}"]
        entries = shifted_policy(base, stream, granularity)
        by_id = {entry["id"]: entry for entry in entries}
        assert set(stream.entry_id) <= set(by_id)
        for entry_id in set(stream.entry_id):
            entry = by_id[entry_id]
            assert set(entry) == {"id", "title", "department", "priority", "identity_check"}
            if entry_id.startswith("split::"):
                parent = entry_id.removeprefix("split::")
                assert entry["department"] != original[parent]["department"]
                assert "policy cohort revised" in entry["title"].lower()
                assert entry["priority"] == original[parent]["priority"]
        assert {entry["id"]: entry for entry in base} == original


def test_stream_builder_is_reproducible_and_rejects_small_pools():
    banking = pd.DataFrame({"text": ["x"] * 7201, "intent": [BANKING77[0]] * 7201})
    clinc = pd.DataFrame({"text": ["y"] * 3700, "intent": ["balance"] * 3700})
    first = build_streams(banking, clinc)
    second = build_streams(banking, clinc)
    for name in first:
        pd.testing.assert_frame_equal(first[name], second[name])
    with pytest.raises(ValueError, match="development"):
        build_streams(banking.iloc[:7200], clinc)
    with pytest.raises(ValueError, match="CLINC"):
        build_streams(banking, clinc.iloc[:10])
