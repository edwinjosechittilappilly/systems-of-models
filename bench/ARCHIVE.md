# Archived experiment data

Everything an experiment produced is stored in one of three places:

| What | Where |
|---|---|
| Analyses, summary tables, manifests, figures, per-item results (compressed shards) | this repository, `bench/results/` |
| Paid provider responses (the record/replay caches), local embeddings and timing caches | GitHub release [`v0.1.0`](https://github.com/edwinjosechittilappilly/systems-of-models/releases/tag/v0.1.0) assets below |
| Downloaded public datasets (Banking77, CLINC150, pinned τ²-bench trajectories) | release asset `som-bench-data.tar.zst` |

## Release assets

| Asset | Contents | SHA-256 |
|---|---|---|
| `som-cache-e1.tar.zst` | `bench/cache/e1_*` (E1/E2: Jev, Decisions, gpt-6.1-terra, embeddings; includes the superseded first CLINC150 run) | `11673bdf839b5dc5b7cfbc8db2b39647b0e389d8c63a0b88acd4f7f2da821139` |
| `som-cache-e3a.tar.zst` | `bench/cache/e3a_*` (agent, Jev, embeddings, mining/surrogate timings, spend journal) | `ebffc57ecccb1ed1fb0f0631b32599ff8b1d417da5f7438fd54da3f0822bd918` |
| `som-cache-e3b.tar.zst` | `bench/cache/e3b_*` (Jev and question-writer calls) | `25fac08bd9994262e89fe028db30cf203fb7b9c5d15e9f961d8203faa43ff216` |
| `som-cache-demo.tar.zst` | `bench/cache/demo-*` | `063bfa42cf09469c375adbe0a5130a7cc8259126f62d8be456d17cc3a503bee0` |
| `som-bench-data.tar.zst` | `bench/data/` (downloaded datasets) | `4fd478f422169a3c1a39ae3bf015a50a823d14ad20f2eac5fdbe61b4910c4b3c` |
| `som-e3a-interim-results.tar.zst` | E3a outputs not tracked in git: development runs and the interrupted evaluation invocations (`evaluation`, `evaluation-resumed`, `evaluation-resumed-2`, incl. `budget_stop.json`) | `a0cbe7544cf79e214e728ac79e7d2a0f46eda6851c14d75b95eaf415ac33a1ac` |
| `eval-full.tar.gz` | complete final E3a evaluation directory (see `bench/results/e3a/ARTIFACTS.md`) | `0a469a864c2f6760e540338c066c2a3f3eb837ffc15f62bfbf5448d5f54e1e2d` |

`SHA256SUMS` in the release lists the `.tar.zst` checksums.

## Restore and replay offline

```sh
gh release download v0.1.0 -R edwinjosechittilappilly/systems-of-models -p 'som-*.tar.zst' -p SHA256SUMS
shasum -a 256 -c SHA256SUMS
for f in som-cache-*.tar.zst som-bench-data.tar.zst; do zstd -dc "$f" | tar -xf - -C bench; done
uv sync --all-groups
uv run --group bench python -m bench.e1_e2.run --mode replay   # likewise bench.e3b.run, bench.e3a.run, bench.e4.run
```

Replay mode never calls a provider; a missing response raises `CacheMiss` instead of spending money.
