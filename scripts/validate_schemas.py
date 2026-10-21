"""Validate every schema against JSON Schema 2020-12 and every example against its schema.

Usage: uv run --with jsonschema python scripts/validate_schemas.py   (from the repository root)
"""
import glob
import json
import os
import sys

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

schemas = {os.path.basename(f).split(".schema")[0]: json.load(open(f)) for f in glob.glob("schemas/*.schema.json")}
registry = Registry().with_resources([(s["$id"], Resource.from_contents(s)) for s in schemas.values()])
failed = 0
for s in schemas.values():
    Draft202012Validator.check_schema(s)
for path in sorted(glob.glob("schemas/examples/*.json")):
    name = os.path.basename(path).split(".")[0]
    errors = list(Draft202012Validator(schemas[name], registry=registry).iter_errors(json.load(open(path))))
    print(("FAIL " if errors else "ok   ") + path + (f": {errors[0].message}" if errors else ""))
    failed += bool(errors)
sys.exit(1 if failed else 0)
