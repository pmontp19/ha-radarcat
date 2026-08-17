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
`diagnostics.py`+translations verification) are landed and reviewed clean, built in parallel
against T2's real contract with no file-scope collisions. Full suite: 82 tests, 100% coverage.

Two Required findings fixed after adversarial review, both independently re-verified before
being dispatched as fixes:
- T3: a metadata-fetch outage longer than one `SCAN_INTERVAL_MIN` cycle left the frame window
  non-contiguous (one big gap, self-healing over ~1h) instead of rebuilding cleanly.
  `_async_update_data` now rebuilds the full window from scratch whenever the gap since the
  newest cached frame isn't exactly one `FRAME_INTERVAL_MIN` - same "second cold start"
  treatment, no partial splicing. Regression-proven: the worker reverted the fix, confirmed the
  new test fails, then restored it.
- T4: `RadarcatImage` never seeded `image_last_updated` at construction, so the entity read
  `unknown` for up to a full poll cycle after every setup even though `async_image()` already
  served a correct WEBP (`BaseCoordinatorEntity.async_added_to_hass` only registers the
  coordinator listener, it never replays `_handle_coordinator_update` for the refresh that
  already happened via `async_config_entry_first_refresh()`). Fixed with a shared
  `_sync_image_last_updated()` called from both `__init__` (cold start) and
  `_handle_coordinator_update` (steady state).
- T4 also added `consecutive_failures`/`last_error` to `diagnostics.py` (already tracked by
  `coordinator.py` for exactly this, previously unread by anything).

**Deferred, accepted gaps** (both low-severity, not blocking the MVP):
- No real Meteocat radar tile with visible rain echo exists as a fixture, so the 2x-scale radar
  anchor is only column-position-checked, not content-checked, in `test_compositor.py`. Capture
  one opportunistically when it's actually raining over the sampled tile; do not fabricate one.
- `coordinator.py`'s `consecutive_failures`/`last_error` only update on a metadata-fetch
  failure, not on a failure during tile-fetch/compose/encode (those still correctly flip
  `last_update_success` via HA's own machinery - only this integration's own diagnostics
  counters would lag). Needs a considered exception boundary to fix well, not a quick broad
  `except`; revisit in v0.2.0 rather than rushing it into the MVP.

**v0.1.0 MVP is done and personally verified**: booted a real `hass` instance (the test
harness's `async_test_home_assistant`, not a hand-rolled bootstrap), drove the actual config
flow end to end, and confirmed the coordinator composed a real 10-frame, 691x653 animated WEBP
against LIVE Meteocat data (real convective storms over Catalonia on 2026-08-17), with correct
orientation and a correctly-seeded `image_last_updated` from the very first state (the T4 fix
holds in practice, not only in tests). `docs/06-quality-scale.md` + `quality_scale.yaml` record
28 done / 7 todo / 19 exempt against the real code, not copied from the siblings.

**v0.2.0 backlog** (not started): `brands` (no `brand/icon.png` yet), `parallel_updates`,
`docs_troubleshooting`, `exception_translations`, `icon_translations`, `repair_issues`,
`strict_typing` - plus the rain-severity sensors and user location described in
`docs/03-feature-spec.md` §7's non-goals.

**Gotcha for any future ad-hoc verification script outside pytest**: `pytest_homeassistant_
custom_component`'s own `testing_config/custom_components/` has an `__init__.py` (a real
package, not a namespace one) - whichever `custom_components` gets imported FIRST in the
process wins the `sys.modules` cache for good, so a bare script must
`import custom_components.radarcat` before importing anything from that plugin, or HA's loader
will never find this integration (`IntegrationNotFound`). Pytest itself never hits this because
test files import `custom_components.radarcat.*` before the plugin needs to.

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
