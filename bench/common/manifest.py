"""Run manifests: what was run, with which code, models, prices and data, and what it cost.

Every runner writes ``bench/results/<experiment>/<run_id>/manifest.json`` next to its CSVs. The paper cites run IDs.
"""

from __future__ import annotations

import json
import platform
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import som

RESULTS_DIR = Path(__file__).resolve().parents[1] / "results"


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


@dataclass
class Manifest:
    experiment: str
    run_id: str
    config: dict[str, Any]
    started_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    finished_at: str | None = None
    git_sha: str = field(default_factory=lambda: _git("rev-parse", "HEAD"))
    git_dirty: bool = field(default_factory=lambda: bool(_git("status", "--porcelain")))
    som_version: str = som.__version__
    contract_version: str = som.CONTRACT_VERSION
    python: str = platform.python_version()
    models: dict[str, str] = field(default_factory=dict)
    """Role -> model ID actually returned by the provider."""
    data: dict[str, str] = field(default_factory=dict)
    """File name -> SHA-256."""
    counts: dict[str, int] = field(default_factory=dict)
    cost_usd: dict[str, float] = field(default_factory=dict)
    """Cost line -> usage-weighted USD for the whole run, including replayed calls."""
    new_spend_usd: dict[str, float] = field(default_factory=dict)
    """Provider -> USD actually spent by this process (cache misses only)."""
    cache: dict[str, dict[str, int]] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def directory(self) -> Path:
        return RESULTS_DIR / self.experiment / self.run_id

    def write(self, directory: Path | None = None) -> Path:
        self.finished_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        directory = self.directory if directory is None else directory
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "manifest.json"
        path.write_text(json.dumps(asdict(self), indent=2, sort_keys=True, default=str) + "\n")
        return path
