"""Corrected CLINC companion question: its own instructions carry the intent list."""

from __future__ import annotations

from bench.common.data import label_names
from bench.e1_e2.pilot import questions

import som


def clinc_fit(system):
    intents = [label.replace("_", " ") for label in label_names("clinc150") if label != "oos"]
    if system == "typesafe":
        instructions = {"question": "Does the request match any of these intents?", "intents": intents}
    else:
        instructions = "Does the request match any of these intents? " + "; ".join(intents)
    return som.Predicate(
        "fit",
        instructions,
        true_means="The request matches a listed intent.",
        false_means="The request does not match a listed intent.",
    )


def revised_questions(system):
    fit = clinc_fit(system)
    return [questions("clinc150")[0], fit] if system == "s2" else [fit]
