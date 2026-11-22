"""Supervised embedding + logistic regression ceiling, trained without calibration or test labels."""

from __future__ import annotations

import hashlib
import time

import httpx
import numpy as np
import sklearn
from bench.common.cache import JsonCache
from bench.e1_e2.collect import splits
from sklearn.linear_model import LogisticRegression
from threadpoolctl import threadpool_limits


def embeddings(texts, *, mode, dataset, batch_size=32):
    """Cache local embedding batches; replay never contacts Ollama."""
    cache = JsonCache(f"e1_embeddings_{dataset}", mode=mode)
    vectors, wall_seconds = [], 0.0
    with httpx.Client(timeout=180.0) as client:
        for start in range(0, len(texts), batch_size):
            batch = list(texts[start : start + batch_size])
            payload = {"model": "embeddinggemma", "input": batch}

            def call(payload=payload):
                started = time.monotonic()
                response = client.post("http://localhost:11434/api/embed", json=payload)
                response.raise_for_status()
                body = response.json()
                return {
                    "embeddings": body["embeddings"],
                    "model": body["model"],
                    "wall_seconds": time.monotonic() - started,
                }

            result = cache.get_or_call(payload, call)
            if result["model"] not in {"embeddinggemma", "embeddinggemma:latest"}:
                raise RuntimeError(f"Unexpected embedding model: {result['model']}")
            vectors.extend(result["embeddings"])
            wall_seconds += result["wall_seconds"]
    return np.asarray(vectors, dtype=float), wall_seconds


def fit_predict(dataset, *, mode):
    train, cal, test = splits(dataset)
    texts = list(train.text) + list(cal.text) + list(test.text)
    vectors, elapsed = embeddings(texts, mode=mode, dataset=dataset)
    n_train, n_cal = len(train), len(cal)
    cache = JsonCache(f"e1_supervised_{dataset}", mode=mode)
    key = {
        "vectors_sha256": hashlib.sha256(memoryview(vectors).cast("B")).hexdigest(),
        "train_labels": list(train.intent),
        "n_train": n_train,
        "n_cal": n_cal,
        "sklearn": sklearn.__version__,
        "numpy": np.__version__,
        "max_iter": 2000,
        "seed": 0,
        "threads": 4,
    }

    def fit():
        started_wall, started_cpu = time.monotonic(), time.process_time()
        with threadpool_limits(limits=4):
            clf = LogisticRegression(max_iter=2000, random_state=0)
            clf.fit(vectors[:n_train], train.intent)
            calibration = clf.predict_proba(vectors[n_train : n_train + n_cal])
            evaluation = clf.predict_proba(vectors[n_train + n_cal :])
        return {
            "classes": clf.classes_.tolist(),
            "calibration": calibration.tolist(),
            "test": evaluation.tolist(),
            "fit_predict_wall_seconds": time.monotonic() - started_wall,
            "fit_predict_cpu_seconds": time.process_time() - started_cpu,
        }

    result = cache.get_or_call(key, fit)
    return (
        np.asarray(result["classes"]),
        np.asarray(result["calibration"]),
        np.asarray(result["test"]),
        {
            "embedding_wall_seconds": elapsed,
            "classifier_wall_seconds": result["fit_predict_wall_seconds"],
            "classifier_cpu_seconds": result["fit_predict_cpu_seconds"],
            "local_compute_cost_usd": None,
        },
    )
