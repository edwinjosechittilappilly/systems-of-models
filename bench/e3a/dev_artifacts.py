"""Pack and restore oversized E3a development artifacts without changing their bytes.

From the repository root, restore the tracked shards to their original paths with::

    python -m bench.e3a.dev_artifacts restore

Existing files are never overwritten. The manifest records the ordered gzip byte
shards and SHA-256 of each original file; already-gzipped traces are preserved as
original gzip bytes. To regenerate shards, pass the original paths relative to
bench/results/e3a to `python -m bench.e3a.dev_artifacts pack PATH ...`.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "results" / "e3a"
SHARDS = ROOT / "dev-compressed"
CHUNK_SIZE = 512_000


def pack(paths: list[str]) -> None:
    SHARDS.mkdir(parents=True, exist_ok=True)
    manifest_path = SHARDS / "manifest.json"
    if manifest_path.exists():
        raise FileExistsError(manifest_path)
    sources = {}
    for name in sorted(paths):
        relative = Path(name)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative.parts[0] not in {"dev-tuning", "dev-tuning-joint"}
        ):
            raise ValueError(f"not a development artifact: {name}")
        source = ROOT / relative
        digest = hashlib.sha256()
        size = 0
        parts = []
        with source.open("rb") as stream:
            for index in range(1, 1_000_000):
                chunk = stream.read(CHUNK_SIZE)
                if not chunk:
                    break
                digest.update(chunk)
                size += len(chunk)
                shard = SHARDS / relative.parent / f"{relative.name}.part-{index:04d}.gz"
                shard.parent.mkdir(parents=True, exist_ok=True)
                with shard.open("xb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as out:
                    out.write(chunk)
                parts.append(shard.relative_to(SHARDS).as_posix())
        sources[name] = {"bytes": size, "sha256": digest.hexdigest(), "shards": parts}
    manifest = {
        "format": "gzip byte shards",
        "chunk_bytes": CHUNK_SIZE,
        "gzip_mtime": 0,
        "reconstruction": "Decompress and concatenate each source's shards in order.",
        "sources": sources,
    }
    with manifest_path.open("x", encoding="utf-8") as out:
        json.dump(manifest, out, indent=2)
        out.write("\n")


def restore() -> None:
    manifest = json.loads((SHARDS / "manifest.json").read_text(encoding="utf-8"))
    for name in manifest["sources"]:
        target = ROOT / name
        if target.exists():
            raise FileExistsError(f"refusing to overwrite {target}")
    for name, info in manifest["sources"].items():
        target = ROOT / name
        target.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        size = 0
        out = target.open("xb")
        try:
            with out:
                for shard in info["shards"]:
                    with gzip.open(SHARDS / shard, "rb") as stream:
                        while chunk := stream.read(CHUNK_SIZE):
                            out.write(chunk)
                            digest.update(chunk)
                            size += len(chunk)
            if size != info["bytes"] or digest.hexdigest() != info["sha256"]:
                raise ValueError(f"checksum mismatch restoring {name}")
        except Exception:
            target.unlink(missing_ok=True)
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("restore")
    pack_parser = commands.add_parser("pack")
    pack_parser.add_argument("paths", nargs="+")
    args = parser.parse_args()
    if args.command == "pack":
        pack(args.paths)
    else:
        restore()


if __name__ == "__main__":
    main()
