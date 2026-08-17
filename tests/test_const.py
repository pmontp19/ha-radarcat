"""Guard the Foundation contract in const.py against accidental edits.

Values must match docs/04-architecture.md §2 literally, see that section's
comment before touching anything here.
"""

from custom_components.radarcat import const


def test_domain() -> None:
    assert const.DOMAIN == "radarcat"


def test_urls() -> None:
    assert const.METADATA_URL == (
        "https://static-m.meteo.cat/ginys/referencia/tiles/dates-tiles-CAPPI_0m.json"
    )
    assert const.RADAR_TILES_BASE == "https://static-m.meteo.cat/tiles/radar"
    assert (
        const.FONS_TILES_BASE
        == "https://static-m.meteo.cat/tiles/fons/GoogleMapsCompatible"
    )


def test_radar_grid() -> None:
    assert const.RADAR_Z == 7
    assert list(const.RADAR_X_RANGE) == list(range(63, 69))
    assert list(const.RADAR_Y_RANGE) == list(range(78, 84))


def test_base_grid() -> None:
    assert const.BASE_Z == 8
    assert list(const.BASE_X_RANGE) == list(range(126, 133))
    assert list(const.BASE_Y_RANGE) == list(range(157, 163))
    assert const.TILE_SIZE == 256


def test_catalunya_crop() -> None:
    assert const.CATALUNYA_TILE_X == (127.85, 130.55)
    assert const.CATALUNYA_TILE_Y == (159.4, 161.95)


def test_thresholds_and_cadence() -> None:
    assert const.MIN_GOOD_BASE_TILES == 12
    assert const.FRAME_COUNT == 10
    assert const.FRAME_INTERVAL_MIN == 6
    assert const.SCAN_INTERVAL_MIN == 6


def test_attribution_and_content_type() -> None:
    assert const.ATTRIBUTION == "Servei Meteorològic de Catalunya (Meteocat)"
    assert const.IMAGE_CONTENT_TYPE == "image/webp"
