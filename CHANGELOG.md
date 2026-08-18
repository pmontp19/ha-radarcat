# Changelog

## [0.1.1](https://github.com/pmontp19/ha-radarcat/compare/ha-radarcat-v0.1.0...ha-radarcat-v0.1.1) (2026-08-18)


### Features

* add brand icon, closing the HACS brands gap ([67cb9d5](https://github.com/pmontp19/ha-radarcat/commit/67cb9d59a23ae782408140b2ae45c04fcfe93825))


### Bug Fixes

* replace hand-drawn brand icon with a real MDI radar glyph ([9c3d48f](https://github.com/pmontp19/ha-radarcat/commit/9c3d48f48bfb37b12d21f0b941888e9af7c17157))

## 0.1.0 (2026-08-18)


### Features

* T1 foundation (const.py, translations, test fixtures) ([61fe13c](https://github.com/pmontp19/ha-radarcat/commit/61fe13ce282c9fa35190e55e6ef7c65ad9ac5cff))
* T2 api.py + compositor.py (tile fetch, Pillow geometry, WEBP encode) ([032bff2](https://github.com/pmontp19/ha-radarcat/commit/032bff2e81a5d5f19380011d0925d747de8bd28b))
* T3 coordinator.py + __init__.py (rolling frame window, setup wiring) ([969de0d](https://github.com/pmontp19/ha-radarcat/commit/969de0ddc426f009931fa13fd8672cda94a1206f))
* T4 entity.py, image.py, config_flow.py, diagnostics.py ([d7f67b2](https://github.com/pmontp19/ha-radarcat/commit/d7f67b22d9f7150c2759165b9641b7781bca262a))
* v0.1.1 static last-frame image entity (image.radarcat_radar_actual) ([ff01655](https://github.com/pmontp19/ha-radarcat/commit/ff0165536ce4b622bc0ae52953e746e0136f4a24))


### Bug Fixes

* config flow description contradicted itself ([65fcebb](https://github.com/pmontp19/ha-radarcat/commit/65fcebbfa1367f192580b90123115a3d83aafe86))
* exclude Pillow from dependabot, remove missed em dashes ([2fb38f6](https://github.com/pmontp19/ha-radarcat/commit/2fb38f68b8152755f01b6bfbdfe3d51faae77d35))


### Documentation

* add real screenshots to README ([84ad3ab](https://github.com/pmontp19/ha-radarcat/commit/84ad3ab7099b63a7cdda95fcc4015ca70aad2a54))
* data sources and existing-integrations research ([f2e379e](https://github.com/pmontp19/ha-radarcat/commit/f2e379ebdfce72bf713cab4ccb22e0ebd6a7fd16))
* drop widget wording from README, tighten config-flow screenshot ([dfe33c1](https://github.com/pmontp19/ha-radarcat/commit/dfe33c19960e2584463c183af990800e8e9b36e4))
* feature spec, architecture contract and implementation plan ([5bb4f88](https://github.com/pmontp19/ha-radarcat/commit/5bb4f887007c34a4857ffdc8baf56b86f2615503))
* fix Catalan grammar across README and design docs ([76d5607](https://github.com/pmontp19/ha-radarcat/commit/76d5607717cf798fc4845e66f460c159ebba8aee))
* record MVP completion and personal verification in AGENTS.md ([a72e503](https://github.com/pmontp19/ha-radarcat/commit/a72e5030f87a6e550005358d0498a21b95d037d1))
* record two oracle ADRs for v0.2.0 backlog (location, dark mode) ([e40d4e7](https://github.com/pmontp19/ha-radarcat/commit/e40d4e74028dd31f4dfbec31548fef820178d506))
* record zoom-controls oracle ADR for v0.2.0 backlog ([248e1e8](https://github.com/pmontp19/ha-radarcat/commit/248e1e8956c035641f0ac8c359b036cd9e5c303e))
* T5 integration - real README content, quality scale ([0017077](https://github.com/pmontp19/ha-radarcat/commit/0017077e1456b3a21cab738d13be2b25336e7b17))
* tighten the remaining two README screenshots ([b4859eb](https://github.com/pmontp19/ha-radarcat/commit/b4859ebb7377ca7ab0add85bfdaf3ea3da709374))
* v0.1.1 contract for a static last-frame image entity ([b82ddb5](https://github.com/pmontp19/ha-radarcat/commit/b82ddb58169394c2c8d5db2b4924940b1a9c86cc))
