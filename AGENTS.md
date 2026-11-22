# systems-of-models

Python package `systems-of-models` (import `som`, CLI `som`) plus the JSON Schema contracts from the paper
"Beyond System 2". The schemas in `schemas/` are the source of truth; the wheel ships a copy as `som/_schemas`.

## Commands

| Task | Command |
|---|---|
| Install package + dev tools | `make sync` |
| Lint, format check, types | `make lint` |
| Offline tests + schema examples | `make test` |
| Everything CI runs (minus hygiene/build) | `make check` |
| Hooks incl. gitleaks | `make hygiene` |
| Tests that call paid APIs (keys in `.env`) | `make test-live` |
| Build sdist + wheel | `make build` |

## Rules

- Credentials live only in `.env` (gitignored, template `.env.example`) and GitHub repository secrets. Never print,
  log, cache or commit a key; never put one in a fixture.
- A schema change is a contract change: follow the semver rules in `schemas/README.md`, update the matching example,
  keep `som check-schemas` green.
- Adapters never invent data. A field a provider does not return is derived by a documented rule or omitted.
- Tests that hit the network are marked `@pytest.mark.live`; the default test run is offline and free.
- Every change lands as a pull request (Conventional Commit title, template filled in). Never push to `main`.

<!-- slipway:begin slipway-project sha256=e1c4418b7d5b3fb2 -->
## Delivery workflow (Slipway)

- **Tasks** live in Beads (`bd`). Start a session with `bd prime`. `bd ready` lists unblocked work; claim with
  `bd update <id> --claim`. Close code-changing beads after their PR merges, citing it; close decisions, spikes and
  research on acceptance, and parents after their children. Humans see the board with `slipway ui`.
- **Behaviour changes** start as an OpenSpec change in `openspec/changes/` (`openspec-propose`, then
  `openspec-apply-change`, then `openspec-archive-change`). Turn an approved change into beads with the
  `spec-to-beads` skill.
- **Documents**: executive one-pagers in `docs/one-pagers/`, design docs in `docs/design/`, decisions in
  `docs/adr/`, diagrams in `docs/diagrams/` (edit the `.json` spec and regenerate; never hand-edit the SVG).
- **Issue tracker for the engineering skills**: `docs/agents/issue-tracker.md` (Beads); labels in
  `docs/agents/triage-labels.md`; domain docs layout in `docs/agents/domain.md`.
- **Roles**: label beads `role:explore|plan|implement|review|issues|pr|docs|design`; `slipway run --bead <id>` hands
  one to the harness and model mapped to that role (`slipway roles` shows the map).
<!-- slipway:end slipway-project -->
