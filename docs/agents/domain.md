# Domain docs

How agents should read this repo's domain documentation before exploring the code.

## Read first

- `GLOSSARY.md` (or `CONTEXT.md` in older repos) at the root, or `GLOSSARY-MAP.md` if it exists: it points at one
  glossary per context.
- `docs/adr/`: decisions that touch the area you are about to change.
- `docs/design/` and `docs/one-pagers/`: the current design and the decision it serves.
- `openspec/specs/`: the agreed behaviour; `openspec/changes/`: behaviour in flight.

If a file does not exist, carry on. `grill-with-docs` and `domain-modeling` create them when terms or decisions get
resolved.

## Layout

Single context (default):

```text
/
├── GLOSSARY.md
├── docs/
│   ├── adr/            0001-….md
│   ├── design/         <feature>.md
│   ├── one-pagers/     <feature>.md
│   └── diagrams/       <name>.json → <name>.svg / .drawio
└── openspec/
```

## Use the glossary's words

Name things in issues, tests and code the way `GLOSSARY.md` does. If you need a word that is not there, either you
are inventing language the project does not use, or there is a real gap to record with `domain-modeling`.

## Flag ADR conflicts

If your change contradicts an ADR, say so explicitly and propose a superseding ADR instead of silently diverging.
