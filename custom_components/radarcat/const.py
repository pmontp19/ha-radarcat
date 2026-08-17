"""Constants for the RadarCat integration.

This module is the Foundation contract every later unit imports (see
docs/04-architecture.md §2). Values are copied verbatim from that section, do
not re-derive or "improve" any of them here.
"""

DOMAIN = "radarcat"

# Meteocat widget endpoints. See docs/01-data-sources.md §2 for the full URL
# templates (radar/base tile paths are built from these bases at request time).
METADATA_URL = (
    "https://static-m.meteo.cat/ginys/referencia/tiles/dates-tiles-CAPPI_0m.json"
)
RADAR_TILES_BASE = "https://static-m.meteo.cat/tiles/radar"
FONS_TILES_BASE = "https://static-m.meteo.cat/tiles/fons/GoogleMapsCompatible"

# RadarGrid - z=7, the only zoom where the radar exists. y grows SOUTH.
# See docs/01-data-sources.md §3; some indices in this range 404 (margin,
# expected, see §14.2).
RADAR_Z = 7
RADAR_X_RANGE = range(63, 69)  # 63..68 inclusive
RADAR_Y_RANGE = range(78, 84)  # 78..83 inclusive

# BaseGrid - z=8, the only zoom usable for the base map. y grows NORTH
# (opposite of the radar grid). See docs/01-data-sources.md §3.
BASE_Z = 8
BASE_X_RANGE = range(126, 133)  # 126..132 inclusive
BASE_Y_RANGE = range(157, 163)  # 157..162 inclusive
TILE_SIZE = 256

# Catalonia crop in BaseGrid tile coordinates (measured in pixels, see
# docs/01-data-sources.md §5 - NOT derived from any lat/lon formula).
CATALUNYA_TILE_X = (127.85, 130.55)
CATALUNYA_TILE_Y = (159.4, 161.95)

# Minimum number of base tiles to consider a load "good enough" to cache (see
# RadarCompositor.minGoodBaseTiles in the sibling project: the ones that
# actually intersect the final crop, not the surrounding margin).
MIN_GOOD_BASE_TILES = 12

FRAME_COUNT = 10
FRAME_INTERVAL_MIN = 6
SCAN_INTERVAL_MIN = 6  # same cadence as ../radarcat - polling faster gains nothing

ATTRIBUTION = "Servei Meteorològic de Catalunya (Meteocat)"
IMAGE_CONTENT_TYPE = "image/webp"
