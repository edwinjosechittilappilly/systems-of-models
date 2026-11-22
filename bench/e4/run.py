"""E4: the contracts exercised by real runs.

1. Validation: every envelope recorded in the response caches (E1/E2/E3/demo) is validated against its system's
   schema at the package's contract version.
2. Field matrix: for each adapter, which envelope fields the provider returns natively, which the adapter derives
   by a documented rule, and which are unavailable.
3. Round trip: for each recorded provider response, the share of its leaf fields whose values are recoverable from
   the envelope (the rest is what the contract drops).
4. Overhead: wall-clock microseconds the gate and ``wrap`` add per call, measured with stub transports.

Usage: ``uv run --group bench python -m bench.e4.run`` (offline; reads caches and fixtures, makes no API calls).
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
from collections import Counter, defaultdict
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx

import som
from bench.common.manifest import Manifest
from som import schemas
from som.testing import FunctionDecider

CACHE_DIR = Path(__file__).resolve().parents[1] / "cache"
FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures"
SCHEMA_FOR_SYSTEM = {
    "s1.decision": "s1-decision",
    "s2.reasoning": "s2-reasoning",
    "s3.search": "s3-search",
    "s4.agentic": "s4-agentic",
    "s5.self_evolving": "s5-self-evolving",
}

# Adapter x envelope field: N = native in the provider response, D = derived by a documented rule, U = unavailable.
# Evidence cites the provider field or the rule. Reviewed against the adapters in src/som/adapters on 2026-11-22.
FIELD_MATRIX: list[dict[str, str]] = []
_FIELDS = ("id", "confidence", "cost.amount", "cost.usage", "latency_ms", "trace_ref", "implementation.model", "body")
_ADAPTERS: dict[str, dict[str, tuple[str, str]]] = {
    "TypeSafe /v1/systemone": {
        "id": ("D", "no response id; generated resp_<hex>"),
        "confidence": ("N", "per-answer probabilities (noul / choice / score)"),
        "cost.amount": ("D", "usage.input_tokens x dated rate card (list_price)"),
        "cost.usage": ("N", "usage.input_tokens, usage.output_tokens"),
        "latency_ms": ("D", "client monotonic timer"),
        "trace_ref": ("D", "W3C ids from the active span or generated"),
        "implementation.model": ("N", "model (versioned id behind the alias)"),
        "body": ("N", "answers keyed by question name"),
    },
    "OpenAI /v1/decisions": {
        "id": ("D", "no response id in the recorded response; generated"),
        "confidence": ("N", "answers[].probability / probabilities"),
        "cost.amount": ("D", "usage x dated rate card (input only)"),
        "cost.usage": ("N", "usage incl. input_tokens_details.cached_tokens"),
        "latency_ms": ("D", "client monotonic timer"),
        "trace_ref": ("D", "W3C ids from the active span or generated"),
        "implementation.model": ("N", "model"),
        "body": ("N", "answers[] (predicate / choice / score / refusal)"),
    },
    "OpenAI /v1/responses": {
        "id": ("N", "id"),
        "confidence": ("U", "no calibrated probability for structured output; envelope confidence is null"),
        "cost.amount": ("D", "usage x dated rate card incl. cached rate"),
        "cost.usage": ("N", "usage incl. reasoning_tokens, cached_tokens"),
        "latency_ms": ("D", "client monotonic timer"),
        "trace_ref": ("D", "W3C ids from the active span or generated"),
        "implementation.model": ("N", "model"),
        "body": ("N", "output_text parsed against the strict answer schema"),
    },
    "OpenAI /v1/chat/completions": {
        "id": ("N", "id"),
        "confidence": ("U", "logprobs not requested; envelope confidence is null"),
        "cost.amount": ("D", "usage x dated rate card"),
        "cost.usage": ("N", "prompt/completion tokens incl. details"),
        "latency_ms": ("D", "client monotonic timer"),
        "trace_ref": ("D", "W3C ids from the active span or generated"),
        "implementation.model": ("N", "model"),
        "body": ("N", "choices[0].message.content parsed; refusal / finish_reason mapped"),
    },
    "OpenRouter (chat-compatible)": {
        "id": ("N", "id"),
        "confidence": ("U", "upstream-dependent; not requested"),
        "cost.amount": ("N", "usage.cost (credits = USD), basis provider_reported"),
        "cost.usage": ("N", "usage"),
        "latency_ms": ("D", "client monotonic timer"),
        "trace_ref": ("D", "W3C ids from the active span or generated"),
        "implementation.model": ("N", "model (routed upstream)"),
        "body": ("N", "structured output parsed"),
    },
    "Ollama / vLLM (chat-compatible)": {
        "id": ("N", "id"),
        "confidence": ("U", "Ollama documents no logprobs on its OpenAI layer"),
        "cost.amount": ("D", "0 API charge, basis local_measured; compute not metered"),
        "cost.usage": ("N", "usage"),
        "latency_ms": ("D", "client monotonic timer"),
        "trace_ref": ("D", "W3C ids from the active span or generated"),
        "implementation.model": ("N", "model tag"),
        "body": ("N", "structured output parsed"),
    },
    "Anthropic Messages (fixtures only)": {
        "id": ("N", "id"),
        "confidence": ("U", "no logprobs in Messages"),
        "cost.amount": ("U", "no built-in price; unknown unless a rate card is passed"),
        "cost.usage": ("N", "usage incl. cache read / creation"),
        "latency_ms": ("D", "client monotonic timer"),
        "trace_ref": ("D", "W3C ids from the active span or generated"),
        "implementation.model": ("N", "model"),
        "body": ("N", "forced tool_use input"),
    },
    "Gemini generateContent (fixtures only)": {
        "id": ("N", "responseId"),
        "confidence": ("U", "avgLogprobs is token-level, not answer probability; not used"),
        "cost.amount": ("U", "no built-in price; unknown unless a rate card is passed"),
        "cost.usage": ("N", "usageMetadata incl. thoughts and cached tokens"),
        "latency_ms": ("D", "client monotonic timer"),
        "trace_ref": ("D", "W3C ids from the active span or generated"),
        "implementation.model": ("N", "modelVersion"),
        "body": ("N", "response JSON parsed against the answer schema"),
    },
}
for _adapter, _fields in _ADAPTERS.items():
    for _field in _FIELDS:
        _status, _evidence = _fields[_field]
        FIELD_MATRIX.append({"adapter": _adapter, "field": _field, "status": _status, "evidence": _evidence})


def cached_envelopes() -> Iterator[tuple[str, dict[str, Any]]]:
    for path in sorted(CACHE_DIR.glob("*.jsonl")):
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                response = json.loads(line).get("response")
                if isinstance(response, dict) and isinstance(response.get("envelope"), dict):
                    yield path.stem, response["envelope"]


def validate_envelopes() -> list[dict[str, Any]]:
    counts: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    first_error: dict[tuple[str, str], str] = {}
    for namespace, envelope in cached_envelopes():
        system = envelope.get("system", "?")
        key = (namespace, system)
        errors = list(schemas.validator(SCHEMA_FOR_SYSTEM.get(system, "envelope")).iter_errors({"response": envelope}))
        counts[key]["valid" if not errors else "invalid"] += 1
        counts[key][f"basis:{envelope.get('cost', {}).get('basis')}"] += 1
        if errors and key not in first_error:
            first_error[key] = errors[0].message
    rows = []
    for (namespace, system), counter in sorted(counts.items()):
        rows.append(
            {
                "namespace": namespace,
                "system": system,
                "envelopes": counter["valid"] + counter["invalid"],
                "valid": counter["valid"],
                "invalid": counter["invalid"],
                "bases": ";".join(f"{k[6:]}={v}" for k, v in sorted(counter.items()) if k.startswith("basis:")),
                "first_error": first_error.get((namespace, system), ""),
            }
        )
    return rows


def _leaves(value: Any, prefix: str = "") -> Iterator[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _leaves(item, f"{prefix}.{key}" if prefix else str(key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _leaves(item, f"{prefix}[{index}]")
    else:
        yield prefix, value


def round_trip() -> list[dict[str, Any]]:
    """Share of a provider response's informative leaves whose value appears in the adapter's envelope."""
    from types import SimpleNamespace

    question_team = som.Choice(
        "team",
        "Which team should handle this ticket?",
        {"billing": "charges, refunds, invoices", "cards": "lost, stolen or declined cards", "fraud": "unauthorised"},
    )
    fits = som.Predicate("fits", "Is this ticket about a bank account or card?")
    urgency = som.Score("urgency", "How urgent is this ticket?", ["can wait", "this week", "today"])
    questions = [question_team, fits, urgency]
    text = "I see two charges for the same coffee on my statement, can you refund one?"
    rows = []

    typesafe = json.loads((FIXTURES / "typesafe_systemone.json").read_text())["response"]
    client = httpx.Client(transport=httpx.MockTransport(lambda _r: httpx.Response(200, json=typesafe)))
    cases = [("TypeSafe /v1/systemone", typesafe, som.TypeSafe(api_key="x", client=client).decide(text, questions))]
    decisions = json.loads((FIXTURES / "openai_decisions.json").read_text())
    fake = SimpleNamespace(decisions=SimpleNamespace(create=lambda **_: decisions))
    cases.append(("OpenAI /v1/decisions", decisions, som.OpenAIDecisions(client=fake).decide(text, questions)))
    responses = json.loads((FIXTURES / "openai_responses.json").read_text())
    fake = SimpleNamespace(responses=SimpleNamespace(create=lambda **_: responses))
    cases.append(("OpenAI /v1/responses", responses, som.OpenAIResponses(client=fake).decide(text, questions)))
    chat = json.loads((FIXTURES / "openai_chat.json").read_text())
    fake = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_: chat)))
    cases.append(
        ("OpenAI /v1/chat/completions", chat, som.OpenAIChat("gpt-6-luna", client=fake).decide("x", [question_team]))
    )

    for adapter, native, decision in cases:
        envelope_values = {json.dumps(v, sort_keys=True) for _, v in _leaves(decision.envelope.to_dict())}
        informative = [
            (path, value)
            for path, value in _leaves(native)
            if value not in (None, "", [], {}, 0, False)
            and not path.startswith(("tools", "text.", "reasoning.", "metadata"))
        ]
        kept = [path for path, value in informative if json.dumps(value, sort_keys=True) in envelope_values]
        dropped = sorted({path for path, _ in informative} - set(kept))
        rows.append(
            {
                "adapter": adapter,
                "native_leaves": len(informative),
                "recovered": len(kept),
                "recovered_share": round(len(kept) / len(informative), 3) if informative else None,
                "dropped_examples": "; ".join(dropped[:12]),
            }
        )
    return rows


def _median_us(samples: list[float]) -> float:
    return round(statistics.median(samples) * 1e6, 1)


def overhead(iterations: int) -> list[dict[str, Any]]:
    team = som.Choice("team", "Which team?", ["billing", "cards"])
    sure = FunctionDecider(lambda _i, q: som.ChoiceAnswer(q.name, "cards", {"billing": 0.05, "cards": 0.95}, 0.9))
    unsure = FunctionDecider(lambda _i, q: som.ChoiceAnswer(q.name, "cards", {"billing": 0.45, "cards": 0.55}, 0.1))
    s2 = FunctionDecider(lambda _i, q: som.ChoiceAnswer(q.name, "cards"), system="s2.reasoning")
    rows = []

    def timed(label: str, fn: Any) -> None:
        for _ in range(50):
            fn()
        samples = []
        for _ in range(iterations):
            started = time.perf_counter()
            fn()
            samples.append(time.perf_counter() - started)
        rows.append({"measurement": label, "median_us": _median_us(samples), "iterations": iterations})

    served = som.Gate(sure, s2, team)
    escalated = som.Gate(unsure, s2, team)
    timed("gate, served by S1 (stub deciders)", lambda: served("x"))
    timed("gate, escalated to S2 (stub deciders)", lambda: escalated("x"))
    envelope = served("x").s1.envelope
    timed("envelope.to_dict()", envelope.to_dict)
    timed("envelope.validate() (s1-decision schema)", envelope.validate)

    import openai

    body = json.loads((FIXTURES / "openai_responses.json").read_text())
    transport = httpx.MockTransport(lambda _r: httpx.Response(200, json=body))
    native = openai.OpenAI(api_key="unused", http_client=httpx.Client(transport=transport))
    wrapped = som.wrap(native)
    timed(
        "OpenAI SDK responses.create, unwrapped (mock transport)",
        lambda: native.responses.create(model="gpt-6.1-terra", input="x"),
    )
    timed(
        "OpenAI SDK responses.create, som.wrap (mock transport)",
        lambda: wrapped.responses.create(model="gpt-6.1-terra", input="x"),
    )
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default="contracts-v2")
    parser.add_argument("--iterations", type=int, default=2000)
    args = parser.parse_args()
    manifest = Manifest(experiment="e4", run_id=args.run_id, config={"iterations": args.iterations})
    out = manifest.directory
    out.mkdir(parents=True, exist_ok=True)

    validation = validate_envelopes()
    _write_csv(out / "validation.csv", validation)
    _write_csv(out / "field_matrix.csv", FIELD_MATRIX)
    trips = round_trip()
    _write_csv(out / "roundtrip.csv", trips)
    costs = overhead(args.iterations)
    _write_csv(out / "overhead.csv", costs)

    total = sum(r["envelopes"] for r in validation)
    valid = sum(r["valid"] for r in validation)
    manifest.counts = {"envelopes": total, "valid": valid, "invalid": total - valid}
    manifest.write()
    matrix = Counter((row["status"]) for row in FIELD_MATRIX)
    lines = [
        "# E4: contracts exercised",
        "",
        f"Envelopes in the response caches: {total}; valid against contract {som.CONTRACT_VERSION}: {valid}; "
        f"invalid: {total - valid}.",
        "",
        "| namespace | system | envelopes | valid | cost bases |",
        "|---|---|---|---|---|",
        *[f"| {r['namespace']} | {r['system']} | {r['envelopes']} | {r['valid']} | {r['bases']} |" for r in validation],
        "",
        f"Field matrix over {len(_ADAPTERS)} adapters x {len(_FIELDS)} fields: native {matrix['N']}, derived "
        f"{matrix['D']}, unavailable {matrix['U']} (field_matrix.csv; Anthropic and Gemini from fixtures only).",
        "",
        "Round trip (share of informative native leaves recoverable from the envelope):",
        "",
        *[
            f"- {r['adapter']}: {r['recovered']}/{r['native_leaves']} ({r['recovered_share']}); dropped e.g. "
            f"{r['dropped_examples']}"
            for r in trips
        ],
        "",
        "Overhead (median microseconds per call, stub transports, this machine):",
        "",
        *[f"- {r['measurement']}: {r['median_us']}" for r in costs],
        "",
        "Threats: the field matrix is a reviewed reading of adapter code and provider docs, not a measurement; the",
        "round-trip check matches values, so a coincidental equal value counts as recovered; overhead is",
        "machine-dependent and excludes network time, which dominates real calls by three orders of magnitude.",
    ]
    (out / "ANALYSIS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
