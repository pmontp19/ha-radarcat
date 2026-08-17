# Project agent memory

This file is the project's committed home for project-intrinsic agent knowledge: build, test,
release, architecture, and sharp-edge notes that should travel with the code.

## State of the repository

Design docs (`docs/01` to `05`) are done and reviewed. T1 Foundation is landed and reviewed
clean: `const.py` (the binding contract every later module imports), `strings.json` +
`translations/{ca,es,en}.json`, `tests/conftest.py`, real captured fixtures under
`tests/fixtures/` (two tiles + the metadata JSON, all md5-verified copies of
`docs/captures/`), `tests/test_const.py`. T2 (`api.py` + `compositor.py`, the unit with real
geometric risk) is next, solo before T3/T4 fan out against its reviewed contract (see
`docs/05-implementation-plan.md` "Onades").

**Adjudicated deviation**: T1 wrote `strings.json`/translations with their *final* content
(title, `cannot_connect` error text, entity name) instead of the empty skeleton
`05-implementation-plan.md` originally asked for. Accepted, not reverted: `03-feature-spec.md`
§3 and `04-architecture.md` §8 already fully determine that wording (single `cannot_connect`
error, zero config fields), so there was no real ambiguity left for T4 to resolve. T4 still
owns re-verifying the two shared keys (`error.cannot_connect`, `entity.image.radar`) actually
match what `config_flow.py`/`image.py` end up using, not just leaving this file untouched.

T2 (`api.py`/`compositor.py`) is landed and reviewed clean, geometry independently re-derived
by hand against `../radarcat/Sources/RadarCat/RadarCompositor.swift` twice (once per worker,
once per reviewer) and cross-checked against a real frame from the actual running Swift app
(`docs/captures/golden_reference_swift_dark_2026-08-17T14-27CEST.png`, produced via
`Scripts/package_app.sh debug` there, not `compile_and_run.sh` which only builds release and
never triggers the `#if DEBUG` PNG dump). `docs/captures/base_tile_z8_x129_y159_south.png`/
`_y161_north.png` are two more real fixtures (mountain vs. sea+badge, same x, different y) used
specifically to anchor `test_compositor.py`'s geometry tests to independently-checkable real
geography instead of only a formula agreeing with itself.

**Deferred, accepted gap**: no real Meteocat radar tile with visible rain echo exists as a
fixture (the one radar tile captured, `radar_tile_z7_x65_y80_no_echo.png`, happened to have
none at capture time). The 2x-scale radar anchor is therefore only column-position-checked, not
content-checked, in `test_compositor.py`. Not fabricating one (evidence discipline). Capture a
real echo tile opportunistically next time it's actually raining over the sampled tile, rather
than chasing it now.

T3 (`coordinator.py`+`__init__.py`) and T4 (`image.py`/`entity.py`/`config_flow.py`/
`diagnostics.py`) are next, in parallel, against T2's now-real (not paper) contract.

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
