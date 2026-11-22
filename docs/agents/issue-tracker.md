# Issue tracker: Beads

Issues, specs and tickets for this repo live in Beads (`bd`), a dependency-aware tracker stored in `.beads/`. Use the
`bd` CLI. Add `--json` whenever you need to parse output.

## Conventions

- **Create an issue**: `bd create "Title" -t task -p 2 -d "body" -l label1,label2`. Types: `task`, `feature`, `bug`,
  `epic`, `decision`, `spike`, `chore`. For multi-line bodies use `--body-file -` with a heredoc. Acceptance
  criteria go in `--acceptance "…"`.
- **Spec / PRD**: an epic (`-t epic`) whose description is the spec. Tickets are its children (`--parent <epic-id>`).
- **Blocking edges**: `--deps blocked-by:<id>` when creating, or `bd dep add <blocked-id> <blocker-id>` later.
- **Read an issue**: `bd show <id>` (`--json` to parse) and `bd comments <id>`.
- **List issues**: `bd list --status open --json`; `bd ready` for unblocked work; `bd blocked` for stuck work.
  Filter by label with `-l <label>`.
- **Comment**: `bd comment <id> "text"`. Append to notes: `bd note <id> "text"`.
- **Labels**: `bd label add <id> <label>` / `bd label remove <id> <label>`.
- **Claim / close**: `bd update <id> --claim`; `bd close <id> --reason "…"`.
- **Routing**: add `role:<name>` (explore, plan, implement, review, issues, pr, docs, design) so
  `slipway run --bead <id>` sends the ticket to the right harness and model.

## Public record

Beads is the agents' working memory; GitHub Issues and PRs stay the public record. Mirror selected beads with
`bd github push <ids>` and pull external reports with `bd github pull` (set `github.owner` and `github.repo` with
`bd config set`). Put bead ids in PR descriptions.

## When a skill says "publish to the issue tracker"

Create beads with `bd create`. For a set of tickets, create the epic first, then children in dependency order so
`Blocked by` can reference real ids.

## When a skill says "fetch the relevant ticket"

Run `bd show <id>` and `bd comments <id>`.
