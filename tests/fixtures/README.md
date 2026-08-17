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
