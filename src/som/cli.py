"""Command-line entry point: ``som``."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections.abc import Sequence
from importlib.resources import files
from pathlib import Path

from som import __version__, schemas
from som.gate import breakeven_rate
from som.integrations.mcp import configured_decider, create_server
from som.questions import Choice


def _cmd_check_schemas(_: argparse.Namespace) -> int:
    failed = 0
    for name, error in schemas.check_examples():
        print(("FAIL " if error else "ok   ") + name + (f": {error}" if error else ""))
        failed += error is not None
    return 1 if failed else 0


def _cmd_validate(args: argparse.Namespace) -> int:
    instance = json.loads(Path(args.file).read_text("utf-8"))
    errors = list(schemas.validator(args.schema).iter_errors(instance))
    for error in errors:
        location = "/".join(str(p) for p in error.absolute_path) or "<root>"
        print(f"{args.file}: {location}: {error.message}", file=sys.stderr)
    if not errors:
        print(f"{args.file}: valid {args.schema}")
    return 1 if errors else 0


def _nonnegative(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise argparse.ArgumentTypeError("must be a finite non-negative number")
    return number


def _rate(value: str) -> float:
    number = _nonnegative(value)
    if number > 1:
        raise argparse.ArgumentTypeError("must be between 0 and 1")
    return number


def _cmd_breakeven(args: argparse.Namespace) -> int:
    if args.c2 == 0 or (args.escalated_c2 is not None and args.escalated_c2 == 0):
        raise ValueError("System 2 costs must be positive")
    list_rate = breakeven_rate(args.c1, args.c2)
    escalated = args.c2 if args.escalated_c2 is None else args.escalated_c2
    weighted_rate = (args.c2 - args.c1 - args.overhead) / escalated
    print(f"List-price break-even escalation rate: {list_rate:.2%}")
    print(f"Usage-weighted break-even escalation rate: {weighted_rate:.2%}")
    if args.escalation_rate is not None:
        cost = args.c1 + args.overhead + args.escalation_rate * escalated
        print(f"Expected cost/request: ${cost:.8f}")
        print(f"Savings versus S2-only: {(1 - cost / args.c2):.2%}")
    return 0


def _cmd_ask(args: argparse.Namespace) -> int:
    name, separator, values = args.choice.partition("=")
    options = values.split(",")
    if not separator or not name or any(not option for option in options):
        raise ValueError("--choice must be name=option1,option2,...")
    question = Choice(name, f"Which {name} best fits the input?", options)
    decision = configured_decider(args.s1).decide(args.text, [question])
    print(json.dumps(decision.envelope.to_dict(), ensure_ascii=False))
    return 0


def _cmd_demo(_: argparse.Namespace) -> int:
    """Replay the first 20 PolyAI/Banking77 test utterances (CC BY 4.0).

    The paired Jev 1.14.0 and GPT-6.1-Terra calls were recorded through bench.common.cache. S2 was also called
    when S1 served, to measure the paired baseline; costs are model list-price estimates, not provider invoices.
    Dataset: https://huggingface.co/datasets/PolyAI/banking77
    """
    data = files("som").joinpath("demo").joinpath("gate.jsonl")
    try:
        lines = data.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        print("Demo recordings are unavailable; real provider recordings are required.", file=sys.stderr)
        return 1
    print("served_by  gate_cost  s2_cost  latency_ms  savings")
    for line in lines:
        if not line.strip():
            continue
        row = json.loads(line)
        savings = 1 - row["gate_cost"] / row["s2_cost"]
        print(
            f"{row['served_by']:9}  ${row['gate_cost']:.6f}  ${row['s2_cost']:.6f}  "
            f"{row['latency_ms']:10.1f}  {savings:7.1%}"
        )
    return 0


def _cmd_mcp_serve(args: argparse.Namespace) -> int:
    create_server(configured_decider(args.s1)).run()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="som", description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check-schemas", help="validate the bundled schemas and their examples")
    check.set_defaults(func=_cmd_check_schemas)

    validate = sub.add_parser("validate", help="validate a JSON file against one contract")
    validate.add_argument("file")
    validate.add_argument("--schema", required=True, choices=schemas.SCHEMA_NAMES)
    validate.set_defaults(func=_cmd_validate)

    breakeven = sub.add_parser("breakeven", help="calculate gate break-even and savings")
    breakeven.add_argument("--c1", required=True, type=_nonnegative, help="mean S1 cost per request in USD")
    breakeven.add_argument("--c2", required=True, type=_nonnegative, help="mean S2-only cost per request in USD")
    breakeven.add_argument("--escalated-c2", type=_nonnegative, help="mean S2 cost conditional on escalation")
    breakeven.add_argument("--overhead", type=_nonnegative, default=0.0, help="overhead per request in USD")
    breakeven.add_argument("--escalation-rate", type=_rate, help="observed or assumed fraction escalated")
    breakeven.set_defaults(func=_cmd_breakeven)

    ask = sub.add_parser("ask", help="ask one typed choice question")
    ask.add_argument("text")
    ask.add_argument("--choice", required=True, help="question name and options, e.g. team=billing,cards,fraud")
    ask.add_argument("--s1", default=os.environ.get("SOM_S1", "typesafe:jev-1.14.0"), help="provider:model")
    ask.set_defaults(func=_cmd_ask)

    demo = sub.add_parser("demo", help="replay recorded gate decisions offline")
    demo.set_defaults(func=_cmd_demo)

    mcp = sub.add_parser("mcp-serve", help="serve typed decisions over MCP stdio")
    mcp.add_argument("--s1", default=os.environ.get("SOM_S1", "typesafe:jev-1.14.0"), help="provider:model")
    mcp.set_defaults(func=_cmd_mcp_serve)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
