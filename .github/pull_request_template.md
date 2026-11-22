<!--
Title: Conventional Commits, `type(scope)!: subject`. Types: feat fix docs chore refactor test ci perf build revert style security.
Lower-case subject, no trailing period, at most 72 characters. Example: `feat(gate): add probability threshold policy`.
`scripts/ci/check_pr.py` checks that Summary, Changes and Verification have real content. Delete sections that do not apply.
-->

## Summary

<!-- 1-3 sentences: what changes for users of the package or the schemas, and why. -->

## Linked issue

<!-- Bead ID (`systems-of-models-…`) or `Closes #123`. Write `None` if there is none. -->

## Changes

<!-- One line per behaviour, grouped by area: schemas, core, adapters, bench, docs, CI. -->

## Verification

<!-- Every check you ran, with the command and its result. Mark checks you did not run as `skipped` with the reason. -->

| Check | Command | Result |
| --- | --- | --- |
| Lint, types | `make lint` | |
| Offline tests + schema examples | `make test` | |
| Live API tests | `make test-live` | |

## Risk and rollback

<!-- Contract changes: is the schema change additive (minor) or breaking (major)? Required when the title has `!`. -->

## Checklist

- [ ] Tests added or updated (or not needed, and why)
- [ ] Schema changes keep `som check-schemas` green and follow the semver rules in `schemas/README.md`
- [ ] Docs updated (README, `docs/`, `AGENTS.md`)
- [ ] No secrets, API keys or personal data in the diff, fixtures or results
