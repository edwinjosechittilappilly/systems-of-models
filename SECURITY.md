# Security policy

## Supported versions

Fixes go to `main` and the latest release on PyPI. Older releases are not patched.

## Reporting a vulnerability

Do not open a public issue or pull request. Use GitHub's private reporting: **Security** tab → **Report a
vulnerability**, with the affected version or commit, reproduction steps and expected impact. You will get an
acknowledgement within 3 business days; fixes for high-severity issues target 30 days.

## What this package touches

- **API keys.** Adapters read provider keys from the environment or from the client object you pass in. The package
  never writes keys to traces, envelopes, caches or logs. Keep keys in `.env` (gitignored) or a secret manager.
- **Traces and caches.** Envelopes and OpenTelemetry spans record metadata (model, tokens, cost, latency, decision).
  Prompt and response content is recorded only when you opt in, and the bench response cache (`bench/cache/`) stays
  local and gitignored. Treat both as sensitive if your inputs are.
- **Compiled decisions.** The compile loop writes new System 1 questions from your traces. Review them before use in
  high-stakes flows; promotion and demotion thresholds are policy you own.
- **CI.** Secrets are scanned with gitleaks on every commit and pull request; actions are pinned to commit SHAs.
