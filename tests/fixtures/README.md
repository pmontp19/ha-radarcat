# Fixtures

Per [`../../AGENTS.md`](../../AGENTS.md)'s evidence discipline: real fixtures here are byte-for-byte
copies of `docs/captures/`, never invented. Synthetic fixtures (none yet) must carry a
`_SYNTHETIC` suffix and a `_comment` key saying so.

## Real fixtures (literal copies)

| Fixture | Source capture | What it holds |
| --- | --- | --- |
| `radar_tile_z7_x65_y80_no_echo.png` | `docs/captures/radar_tile_2026-08-17T1142Z_z7_x65_y80.png` | RadarGrid tile z=7, x=65, y=80, captured 2026-08-17 11:42Z. Transparent, no echo at capture time. |
| `base_tile_z8_x128_y160.png` | `docs/captures/base_tile_z8_x128_y160.png` | BaseGrid tile z=8, x=128, y=160, captured 2026-08-17. Static base map tile (no timestamp). |
| `metadata_sample.json` | `docs/captures/metadata_sample.json` | Response of `METADATA_URL`, captured 2026-08-17 (single respectful request, ~12:01Z). `{"dataUltimaImatge":"08/17/2026 11:54Z","dataSistema":"08/17/2026 12:01Z"}` - the non-ISO-8601 `"MM/dd/yyyy HH:mm'Z'"` format documented in `docs/01-data-sources.md` §2. |
| `base_tile_z8_x129_y161_north.png` | `docs/captures/base_tile_z8_x129_y161_north.png` | BaseGrid tile z=8, x=129, y=161. Visually: mountainous terrain, comarca borders, a cut-off "...ell" label (la Seu d'Urgell) - unmistakably northern/Pyrenean content, independent confirmation that BaseGrid's y grows north (docs/01-data-sources.md §3). Same x as the south fixture below, different y only, to isolate the y-axis direction specifically. |
| `base_tile_z8_x129_y159_south.png` | `docs/captures/base_tile_z8_x129_y159_south.png` | BaseGrid tile z=8, x=129, y=159. Visually: flat grey (sea) plus the meteo.cat attribution badge's edge (blue icon + partial "m" text near the top-right corner) - independently confirms docs/01-data-sources.md §8's claim that the badge lives in a south tile, from a different tile than `base_tile_z8_x128_y160.png` above. |
