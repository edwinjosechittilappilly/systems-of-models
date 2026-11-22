"""Load the bundled JSON Schemas and validate instances against them.

The schemas in the repository's ``schemas/`` directory are the source of truth. Wheels ship a copy under
``som/_schemas``; an editable install from a source checkout reads the repository directory directly.
"""

from __future__ import annotations

import json
import sys
from functools import cache
from importlib import resources
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    from importlib.resources.abc import Traversable
else:
    from importlib.abc import Traversable

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource

__all__ = ["SCHEMA_NAMES", "ValidationError", "check_examples", "load", "validate", "validator"]

SCHEMA_NAMES = (
    "envelope",
    "escalation",
    "s1-decision",
    "s2-reasoning",
    "s3-search",
    "s4-agentic",
    "s5-self-evolving",
    "meta-layer",
    "swarm-trace",
)


def _schema_dir() -> Traversable:
    packaged = resources.files("som") / "_schemas"
    if packaged.is_dir():
        return packaged
    return Path(__file__).resolve().parents[2] / "schemas"


def load(name: str) -> dict[str, Any]:
    """Return the parsed schema called ``name`` (for example ``"s1-decision"``)."""
    if name not in SCHEMA_NAMES:
        raise KeyError(f"unknown schema {name!r}; expected one of {', '.join(SCHEMA_NAMES)}")
    return _load_all()[name]


@cache
def _load_all() -> dict[str, dict[str, Any]]:
    root = _schema_dir()
    return {name: json.loads((root / f"{name}.schema.json").read_text("utf-8")) for name in SCHEMA_NAMES}


@cache
def _registry() -> Registry:
    return Registry().with_resources((schema["$id"], Resource.from_contents(schema)) for schema in _load_all().values())


@cache
def validator(name: str) -> Draft202012Validator:
    """Return a cached validator for schema ``name`` that resolves ``$ref``s offline."""
    return Draft202012Validator(load(name), registry=_registry())


def validate(instance: Any, name: str) -> None:
    """Raise :class:`ValidationError` (the most relevant error) if ``instance`` does not match ``name``."""
    validator(name).validate(instance)


def check_examples() -> list[tuple[str, str | None]]:
    """Check every schema against the 2020-12 meta-schema and every bundled example against its schema.

    Returns ``(example file name, first error message or None)`` pairs.
    """
    for schema in _load_all().values():
        Draft202012Validator.check_schema(schema)
    results: list[tuple[str, str | None]] = []
    examples = _schema_dir() / "examples"
    for entry in sorted(examples.iterdir(), key=lambda e: e.name):
        if not entry.name.endswith(".json"):
            continue
        schema_name = entry.name.split(".")[0]
        errors = list(validator(schema_name).iter_errors(json.loads(entry.read_text("utf-8"))))
        results.append((entry.name, errors[0].message if errors else None))
    return results
