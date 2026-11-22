# Triage labels

The engineering skills speak in five triage roles. This table maps them to Beads labels in this repo.

| Role in mattpocock/skills | Beads label | Meaning |
|---|---|---|
| `needs-triage` | `needs-triage` | Maintainer needs to evaluate this issue |
| `needs-info` | `needs-info` | Waiting on the reporter for more information |
| `ready-for-agent` | `ready-for-agent` | Fully specified; an agent can take it with no human context |
| `ready-for-human` | `ready-for-human` | Needs a human to implement |
| `wontfix` | `wontfix` | Will not be actioned (also close the bead with a reason) |

Apply with `bd label add <id> <label>`. Combine with a `role:<name>` label to route `ready-for-agent` work to a
harness (`slipway roles`).
