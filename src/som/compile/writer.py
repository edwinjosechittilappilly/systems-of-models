"""Draft typed questions from sampled observations and observed choice titles.

Sampling is reproducible, not a guarantee of question quality. The writer sees
no tool results or policies, only sample pairs, observed titles, and branch identity.
"""

from __future__ import annotations

import json
import random
from collections.abc import Callable, Mapping
from typing import Any

from som.questions import Choice, Option, Predicate, Question

from .mining import Candidate


def write_question(
    candidate: Candidate,
    writer: Callable[[dict[str, Any]], Mapping[str, str]],
    *,
    n_samples: int = 20,
    seed: int,
) -> tuple[Question, dict[str, Any]]:
    """Write a typed question from sampled pairs and observed choice titles.

    The callable receives ``samples`` and, for retrieval choices, ``choices``;
    branches additionally include ``tool`` and ``argument``. It returns a mapping
    containing ``name`` and ``instructions``, optionally branch descriptions.
    """
    if n_samples < 1 or not candidate.examples:
        raise ValueError("n_samples and the number of examples must be positive")
    selected = random.Random(seed).sample(candidate.examples, min(n_samples, len(candidate.examples)))
    samples = [
        {"input": example.input, "value": example.value, **({"title": example.title} if example.title else {})}
        for example in selected
    ]
    context: dict[str, Any] = {"samples": samples}
    titles: dict[str, str] = {}
    if candidate.kind == "retrieval_choice":
        for example in candidate.examples:
            if example.title:
                titles.setdefault(str(example.value), example.title)
        context["choices"] = [
            {"value": value, **({"title": titles[str(value)]} if str(value) in titles else {})}
            for value in candidate.values
        ]
    if candidate.kind == "branch":
        context.update(tool=candidate.tool, argument=candidate.argument)
    draft = writer(context)
    name, instructions = draft["name"], draft["instructions"]
    if not isinstance(name, str) or not name.strip() or not isinstance(instructions, str) or not instructions.strip():
        raise ValueError("writer must return a nonempty name and instructions")
    if candidate.kind == "branch":
        question: Question = Predicate(name, instructions, draft.get("true_means"), draft.get("false_means"))
    else:
        values = [str(value) for value in candidate.values]
        if len(values) != len(set(values)):
            raise ValueError("candidate values collide when converted to Choice strings")
        options = [Option(value, titles.get(value)) for value in values]
        question = Choice(name, instructions, options)
    return question, {
        "candidate": candidate.name,
        "kind": candidate.kind,
        "seed": seed,
        "n_samples": len(samples),
        "sample_trace_ids": [example.trace_id for example in selected],
        "writer": getattr(writer, "model", getattr(writer, "__qualname__", type(writer).__qualname__)),
    }


class OpenAIQuestionWriter:
    """Use Responses structured output to draft instructions from example pairs."""

    def __init__(self, model: str = "gpt-6.1-terra", client: Any = None) -> None:
        if client is None:
            try:
                from openai import OpenAI
            except ImportError as error:
                raise ImportError("install systems-of-models[openai]") from error
            client = OpenAI()
        self.model = model
        self.client = client

    def __call__(self, context: dict[str, Any]) -> Mapping[str, str]:
        response = self.client.responses.create(
            model=self.model,
            instructions=(
                "Draft a concise typed decision question that predicts the observed value from the input. "
                "Use titles only to interpret observed values. Do not invent policy rules. "
                "Return a name, instructions, and descriptions of true and false if appropriate."
            ),
            input=json.dumps(context, ensure_ascii=False),
            text={
                "format": {
                    "type": "json_schema",
                    "name": "question",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            key: {"type": "string"} for key in ("name", "instructions", "true_means", "false_means")
                        },
                        "required": ["name", "instructions", "true_means", "false_means"],
                    },
                }
            },
        )
        if not response.output_text:
            raise ValueError("question writer returned no structured output")
        draft = json.loads(response.output_text)
        if not isinstance(draft, dict):
            raise ValueError("question writer returned invalid structured output")
        return draft
