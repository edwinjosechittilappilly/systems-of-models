"""Datasets: download once from the Hugging Face parquet export, verify a checksum, load as DataFrames.

Banking77 (PolyAI, CC BY 4.0) and CLINC150 (`clinc/clinc_oos`, config `plus`, CC BY 3.0). Files land in
``bench/data/`` (gitignored). ``bench/data/CHECKSUMS.json`` pins the SHA-256 of each file on first download, a later
download with a different digest is an error, and every run manifest copies the digests it used.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import httpx
import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
_HF = "https://huggingface.co/api/datasets/{repo}/parquet/{config}/{split}/0.parquet"

SOURCES = {
    ("banking77", "train"): ("PolyAI/banking77", "default", "train"),
    ("banking77", "test"): ("PolyAI/banking77", "default", "test"),
    ("clinc150", "train"): ("clinc/clinc_oos", "plus", "train"),
    ("clinc150", "validation"): ("clinc/clinc_oos", "plus", "validation"),
    ("clinc150", "test"): ("clinc/clinc_oos", "plus", "test"),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch(dataset: str, split: str) -> Path:
    repo, config, hf_split = SOURCES[(dataset, split)]
    path = DATA_DIR / f"{dataset}-{split}.parquet"
    if not path.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with httpx.stream("GET", _HF.format(repo=repo, config=config, split=hf_split), follow_redirects=True) as r:
            r.raise_for_status()
            with path.open("wb") as handle:
                for chunk in r.iter_bytes():
                    handle.write(chunk)
    checksums_path = DATA_DIR / "CHECKSUMS.json"
    checksums = json.loads(checksums_path.read_text()) if checksums_path.exists() else {}
    digest = _sha256(path)
    if path.name in checksums and checksums[path.name] != digest:
        raise RuntimeError(f"{path.name}: checksum changed ({checksums[path.name][:12]} -> {digest[:12]})")
    checksums[path.name] = digest
    checksums_path.write_text(json.dumps(checksums, indent=2, sort_keys=True) + "\n")
    return path


def label_names(dataset: str) -> list[str]:
    """Class names in label-index order, from the dataset cards' ClassLabel features."""
    from bench.common import labels

    return list(labels.BANKING77 if dataset == "banking77" else labels.CLINC150)


def load(dataset: str, split: str) -> pd.DataFrame:
    """Columns: ``text``, ``label`` (int), ``intent`` (name). CLINC's out-of-scope class is ``oos``."""
    frame = pd.read_parquet(fetch(dataset, split))
    if "intent" in frame.columns and "label" not in frame.columns:
        frame = frame.rename(columns={"intent": "label"})
    names = label_names(dataset)
    frame = frame[["text", "label"]].copy()
    frame["intent"] = [names[i] for i in frame["label"]]
    return frame.reset_index(drop=True)


def stratified(frame: pd.DataFrame, per_class: int, *, seed: int, column: str = "intent") -> pd.DataFrame:
    """Up to ``per_class`` rows per class, sampled without replacement with a fixed seed."""
    parts = [
        group.sample(n=min(per_class, len(group)), random_state=seed) for _, group in frame.groupby(column, sort=True)
    ]
    return pd.concat(parts).sample(frac=1.0, random_state=seed).reset_index(drop=True)
