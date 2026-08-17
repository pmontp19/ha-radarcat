# Project agent memory

This file is the project's committed home for project-intrinsic agent knowledge: build, test,
release, architecture, and sharp-edge notes that should travel with the code.

## State of the repository

Scaffold only. Boilerplate (CI, release-please, HACS metadata, licence, lint config) is copied
and adapted from the sibling repos below. No `docs/` design contract and no
`custom_components/radarcat` code beyond `manifest.json` exist yet.

## Sibling repositories

Three prior Home Assistant integrations by the same author, for Catalan public data sources,
set the quality bar and the process for this one — read them before inventing a different
shape:

- `../ha-avisoscat` and `../ha-bomberscat`: finished, released examples (diagnostics, blueprint,
  quality_scale.yaml, full test suite). Copy their conventions for anything this file doesn't
  cover yet.
- `../ha-cecat`: newest conventions (this file's own structure, the evidence-marking discipline
  below), but the repo itself is mid-implementation — do not copy its *state*, only its *process*.

The source project for the actual radar logic is `../radarcat`: a macOS menu-bar app that
already fetches, composites and crops the same Meteocat radar tiles this integration serves,
and already reverse-engineered the tile grids, the two zoom levels, the y-axis direction of
each, and the meteo.cat attribution-badge exclusion. Port that knowledge (`../radarcat/CLAUDE.md`,
`RadarAPI.swift`, `RadarCompositor.swift`, `RadarGrid.swift`, `RainDetector.swift`), do not
re-derive it from scratch.

## Language

Documents in **Catalan** (matching the sibling repositories). Code, identifiers, comments, commit
messages, event names and this file in **English**. User-facing strings go through
`_attr_translation_key` + `translations/{ca,es,en}.json`, Catalan as the reference language.

Never use the em dash (`—`) anywhere, including documentation.

## Evidence discipline

This is the rule that makes the docs trustworthy, and it is not optional:

- Every claim about the data source is marked ✅ verified live, 🗄️ verified on an archived
  capture, 📄 documented by the official source, 🔶 inference, or ❓ unverified. Keep the marks
  when editing.
- `docs/captures/` holds only **observed** data. Synthetic test data goes in `tests/fixtures/`
  with a `_SYNTHETIC` suffix and a `_comment` key saying so. Never blur the two.
- Test fixtures must be real captured responses (or real downloaded tiles, trimmed), not
  invented, except the marked synthetic ones.

## Read-only research etiquette

The source is Meteocat's public radar widget (`static-m.meteo.cat/ginys/mapaRadar` and its
tile/metadata endpoints), not a documented, versioned API. Read-only requests only, spaced out,
never authenticated, never aggressive. `../radarcat/CLAUDE.md` already documents the tile grids;
verify against a real request before trusting a formula, but do not hammer the endpoint to do it.

## Maintaining this file

Keep this file for knowledge useful to almost every future agent session in this project.
Do not repeat what the codebase already shows; point to the authoritative file or command instead.
Prefer rewriting or pruning existing entries over appending new ones.
When updating this file, preserve this bar for all agents and keep entries concise.
