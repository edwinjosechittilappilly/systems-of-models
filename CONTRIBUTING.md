# Contributing

```bash
git clone https://github.com/edwinjosechittilappilly/systems-of-models && cd systems-of-models
make sync            # uv sync: package + dev tools in .venv
uvx pre-commit install
make check           # ruff, mypy, offline tests, schema examples
```

Live tests call real APIs and cost money: copy `.env.example` to `.env`, fill in the keys you have, then
`make test-live`.

## Workflow

- Work is tracked in Beads (`bd ready`, `bd update <id> --claim`); behaviour changes start as an OpenSpec change in
  `openspec/changes/`. See `AGENTS.md`.
- One pull request per change, titled with Conventional Commits (`feat(adapters): add gemini adapter`). The PR
  template's Summary, Changes and Verification sections are checked in CI.
- `main` is protected: changes land through pull requests with green CI.

## Contract changes

Files in `schemas/` are the contract. Follow the semver rules in `schemas/README.md`: additive optional fields are a
minor change, anything that can break an existing producer or consumer is a major change. Every schema change needs
an updated example in `schemas/examples/` and must keep `som check-schemas` green.

## Adapters

An adapter maps one provider response to the envelope without inventing data: a field the provider does not return
is either derived by a documented rule (for example latency from a client timer) or left out, never filled with a
guess. Add a recorded, secret-free fixture under `tests/fixtures/` and mark tests that call the network with
`@pytest.mark.live`.
