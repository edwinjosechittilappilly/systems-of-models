"""Command-line entry point: ``som``."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from som import __version__, schemas


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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
