"""Tests for compose_frame's tile geometry, encode_animation's WEBP output,
and encode_static's PNG output.

The geometry math is docs/04-architecture.md §4.1, a port of
../radarcat/Sources/RadarCat/RadarCompositor.swift's catalunyaCrop/
drawBaseTile/radar-draw-loop plus the one Pillow-only y-flip that project
never needed. This file is the regression guard against that project's own
past full-vertical-mirror bug (AGENTS.md, docs/04-architecture.md §4.1): the
size-only assertion (1) is necessary but never sufficient by itself; (2) and
(3) below are the ones that would actually catch a flipped y.
"""

from __future__ import annotations

import io

import pytest
from custom_components.radarcat.compositor import (
    compose_frame,
    encode_animation,
    encode_static,
)
from custom_components.radarcat.const import (
    BASE_X_RANGE,
    BASE_Y_RANGE,
    CATALUNYA_TILE_X,
    CATALUNYA_TILE_Y,
    TILE_SIZE,
)
from PIL import Image

from tests.conftest import load_fixture

# ---------------------------------------------------------------------------
# Expected canvas size, computed from const.py (never hardcoded) - see
# docs/04-architecture.md §4.1 step 1 / RadarCompositor.catalunyaCrop.
# ---------------------------------------------------------------------------


def _expected_crop() -> tuple[float, float, int, int]:
    x0 = (CATALUNYA_TILE_X[0] - BASE_X_RANGE.start) * TILE_SIZE
    x1 = (CATALUNYA_TILE_X[1] - BASE_X_RANGE.start) * TILE_SIZE
    y0 = (CATALUNYA_TILE_Y[0] - BASE_Y_RANGE.start) * TILE_SIZE
    y1 = (CATALUNYA_TILE_Y[1] - BASE_Y_RANGE.start) * TILE_SIZE
    return x0, y0, round(x1 - x0), round(y1 - y0)


CROP_X0, CROP_Y0, CW, CH = _expected_crop()


def _expected_pillow_position(
    grid_x: int, grid_y: int, span: int, *, radar: bool = False
) -> tuple[int, int]:
    """Independently re-derive dx/y_pillow for one tile (docs/04-architecture.md §4.1).

    Steps 2-4 are written out again here, separately from compositor.py, so
    this test does not just compare the implementation against itself.
    """
    if radar:
        dx = (2 * grid_x - BASE_X_RANGE.start) * TILE_SIZE - CROP_X0
        dy_native = (2 * grid_y - BASE_Y_RANGE.start) * TILE_SIZE - CROP_Y0
    else:
        dx = (grid_x - BASE_X_RANGE.start) * TILE_SIZE - CROP_X0
        dy_native = (grid_y - BASE_Y_RANGE.start) * TILE_SIZE - CROP_Y0
    y_pillow = CH - dy_native - span
    return round(dx), round(y_pillow)


def _blend_on_black(png: bytes) -> Image.Image:
    """Alpha-blend a tile's own pixels onto black, exactly as _paste_tile does.

    Several fixtures carry partial alpha (anti-aliased edges), so naively
    dropping alpha with ``.convert("RGB")`` does not reproduce what actually
    lands on the composited canvas - it must go through the same mask=tile
    paste onto a black background compose_frame uses internally.
    """
    tile = Image.open(io.BytesIO(png))
    if tile.mode != "RGBA":
        tile = tile.convert("RGBA")
    blended = Image.new("RGB", tile.size, (0, 0, 0))
    blended.paste(tile, (0, 0), mask=tile)
    return blended


def _visible_slice(
    y_pillow: int, span: int, canvas_h: int
) -> tuple[int, int, int, int]:
    """(canvas_top, canvas_bottom, tile_top, tile_bottom) for a pasted tile.

    A tile near a crop edge is only partially on-canvas (y_pillow can be
    negative, or y_pillow + span can exceed canvas_h); this maps the visible
    canvas rows back to the matching rows of the tile's own source pixels.
    """
    canvas_top = max(0, y_pillow)
    canvas_bottom = min(canvas_h, y_pillow + span)
    return canvas_top, canvas_bottom, canvas_top - y_pillow, canvas_bottom - y_pillow


# ---------------------------------------------------------------------------
# 1. Output size (necessary, not sufficient on its own - see 2/3 below)
# ---------------------------------------------------------------------------


def test_output_size_matches_computed_crop() -> None:
    """compose_frame's canvas is exactly (cw, ch) from const.py, ~691x653."""
    base = {(128, 160): load_fixture("base_tile_z8_x128_y160.png")}
    radar = {(65, 80): load_fixture("radar_tile_z7_x65_y80_no_echo.png")}

    frame = compose_frame(base, radar)

    assert frame.size == (CW, CH)
    assert (CW, CH) == (691, 653)  # the value docs/04-architecture.md §4.1 expects


# ---------------------------------------------------------------------------
# 2. THE geometry check: a real base tile must land exactly where the
# formula says, not mirrored. docs/01-data-sources.md §8 places the
# meteo.cat badge in tile (130, 159), not the (128, 160) fixture this
# project has on disk - confirmed empirically (no pixel in that fixture
# falls near the badge's yellow/green hues), so asserting "the badge is in
# this fixture" would be asserting something false. Pinning tile (128, 160)
# to its own computed pixel offset is a strictly stronger check anyway (an
# exact position, not a loose corner region) and needs no extra fetch.
# ---------------------------------------------------------------------------


def test_base_tile_lands_at_its_computed_position_not_mirrored() -> None:
    """Tile (128, 160)'s content appears at the position §4.1 predicts."""
    base_png = load_fixture("base_tile_z8_x128_y160.png")
    base = {(128, 160): base_png}
    radar = {(65, 80): load_fixture("radar_tile_z7_x65_y80_no_echo.png")}

    frame = compose_frame(base, radar)

    dx, y_pillow = _expected_pillow_position(128, 160, TILE_SIZE)
    # Worked example (also quoted in the report): a flipped y would move
    # this tile far from (38, 243), not just off by a pixel.
    assert (dx, y_pillow) == (38, 243)

    expected_patch = _blend_on_black(base_png)
    actual_patch = frame.crop((dx, y_pillow, dx + TILE_SIZE, y_pillow + TILE_SIZE))
    assert actual_patch.tobytes() == expected_patch.tobytes()

    # The transparent no-echo radar tile scales onto a different column
    # entirely and must not have touched this region.
    radar_dx, _ = _expected_pillow_position(65, 80, TILE_SIZE * 2, radar=True)
    assert radar_dx != dx


# ---------------------------------------------------------------------------
# 2b. Real-geography direction check: two more real tiles, same column
# (x=129), different y only, so this isolates the y-axis specifically.
# (129, 161) is visually mountainous Pyrenean terrain with a cut-off "...ell"
# (la Seu d'Urgell) label; (129, 159) is flat grey sea plus the meteo.cat
# badge's edge - see tests/fixtures/README.md. Anchored to independently
# verified real content rather than to the formula agreeing with itself: a
# flipped y would put sea pixels where mountains are checked for (and vice
# versa), which fails on content, not merely on a mismatched offset.
# ---------------------------------------------------------------------------


def test_real_geography_mountain_tile_lands_north_of_sea_tile() -> None:
    """Mountain tile (129, 161) lands above sea+badge tile (129, 159).

    If BaseGrid's y-direction were ever flipped by mistake, this composed
    frame would show mountains at the BOTTOM and sea at the TOP - exactly
    the full-vertical-mirror bug class this project has shipped once before.
    """
    north_png = load_fixture("base_tile_z8_x129_y161_north.png")
    south_png = load_fixture("base_tile_z8_x129_y159_south.png")
    base = {(129, 161): north_png, (129, 159): south_png}

    frame = compose_frame(base, radar_tiles={})

    dx, north_y = _expected_pillow_position(129, 161, TILE_SIZE)
    south_dx, south_y = _expected_pillow_position(129, 159, TILE_SIZE)
    assert dx == south_dx  # same column: isolates the y-axis only

    # Readable independently of any pixel comparison: the mountain tile's
    # box sits at a smaller row index (higher on screen) than the sea tile's.
    assert north_y + TILE_SIZE / 2 < south_y + TILE_SIZE / 2

    # Tied to the actual pixels, not just the two offsets: the visible slice
    # of each real tile, cropped straight out of the composited canvas,
    # must match that same slice of its own untouched source PNG.
    for xy, png, y_pillow in (
        ((129, 161), north_png, north_y),
        ((129, 159), south_png, south_y),
    ):
        canvas_top, canvas_bottom, tile_top, tile_bottom = _visible_slice(
            y_pillow, TILE_SIZE, CH
        )
        source = _blend_on_black(png)
        expected = source.crop((0, tile_top, TILE_SIZE, tile_bottom))
        actual = frame.crop((dx, canvas_top, dx + TILE_SIZE, canvas_bottom))
        assert actual.tobytes() == expected.tobytes(), xy


# ---------------------------------------------------------------------------
# 3. Synthetic direction check: independent of any real fixture, fails
# immediately if south/north (Pillow large-row/small-row) are swapped.
# Grid x=128, y in {159, 161} are used instead of the literal
# BASE_X_RANGE/BASE_Y_RANGE endpoints: the endpoints are margin tiles that
# fall entirely outside the ~691x653 crop (zero overlap, verified via
# _expected_pillow_position before picking these), so they would show
# nothing on canvas regardless of geometry correctness.
# ---------------------------------------------------------------------------


def test_synthetic_south_tile_lands_below_north_tile() -> None:
    """South (small BaseGrid y) lands at a larger Pillow row than north.

    BaseGrid's y grows north (docs/01-data-sources.md §3); Pillow's row index
    grows downward. A tile closer to the crop's south edge must therefore
    land at a larger row index (lower on screen) than one near the north
    edge - if that were swapped, this is the flipped-y bug the whole project
    is written to catch.
    """
    red = Image.new("RGBA", (TILE_SIZE, TILE_SIZE), (255, 0, 0, 255))
    blue = Image.new("RGBA", (TILE_SIZE, TILE_SIZE), (0, 0, 255, 255))
    red_bytes, blue_bytes = io.BytesIO(), io.BytesIO()
    red.save(red_bytes, format="PNG")
    blue.save(blue_bytes, format="PNG")

    south_xy = (128, 159)
    north_xy = (128, 161)
    base = {south_xy: red_bytes.getvalue(), north_xy: blue_bytes.getvalue()}

    frame = compose_frame(base, radar_tiles={})

    south_dx, south_y = _expected_pillow_position(*south_xy, TILE_SIZE)
    north_dx, north_y = _expected_pillow_position(*north_xy, TILE_SIZE)
    assert south_y > north_y  # south tile's box starts at a larger row index

    # Sample a pixel safely inside each tile's on-canvas portion (both are
    # partially clipped by the crop margin, see the module comment above).
    south_sample = frame.getpixel((south_dx + 10, min(south_y + 10, CH - 1)))
    north_sample = frame.getpixel((north_dx + 10, max(north_y + 10, 0)))
    assert south_sample == (255, 0, 0)
    assert north_sample == (0, 0, 255)


# ---------------------------------------------------------------------------
# 2c. Real echo content check: a real RadarGrid tile with genuine visible
# rain (see tests/fixtures/README.md), composited alone at 2x scale, must
# actually deposit its own echo pixels at the anchor §4.1 predicts - not just
# a column number. Fills the gap AGENTS.md deferred: the only other real
# radar fixture (radar_tile_z7_x65_y80_no_echo.png) had no echo at capture
# time, so the radar draw path was never content-checked before this.
# ---------------------------------------------------------------------------


def test_real_radar_echo_tile_lands_at_its_2x_scaled_position() -> None:
    """Real echo tile (64, 80) composites, at 2x scale, onto its predicted anchor."""
    radar_png = load_fixture("radar_tile_z7_x64_y80_with_echo.png")
    radar_span = TILE_SIZE * 2

    frame = compose_frame(base_tiles={}, radar_tiles={(64, 80): radar_png})

    dx, y_pillow = _expected_pillow_position(64, 80, radar_span, radar=True)
    canvas_top, canvas_bottom, tile_top, tile_bottom = _visible_slice(
        y_pillow, radar_span, CH
    )

    # _paste_tile resizes the 256x256 source to the 512x512 radar span before
    # blending (compositor.py's own resize call, reproduced here rather than
    # skipped, since a resize is the one step this fixture's assertion cannot
    # bypass without silently comparing the wrong pixels).
    resized = (
        Image.open(io.BytesIO(radar_png))
        .convert("RGBA")
        .resize((radar_span, radar_span))
    )
    resized_bytes = io.BytesIO()
    resized.save(resized_bytes, format="PNG")
    expected_full = _blend_on_black(resized_bytes.getvalue())
    expected_visible = expected_full.crop((0, tile_top, radar_span, tile_bottom))
    actual_visible = frame.crop((dx, canvas_top, dx + radar_span, canvas_bottom))
    assert actual_visible.tobytes() == expected_visible.tobytes()

    # Guard against the byte-equality check above passing on a degenerate
    # all-black comparison: real echo pixels (blue/cyan/green/orange cluster
    # plus scattered noise dots, see tests/fixtures/README.md) must actually
    # have landed on the canvas, not just an empty/transparent tile.
    non_black = sum(1 for pixel in actual_visible.getdata() if pixel != (0, 0, 0))
    assert non_black > 100


# ---------------------------------------------------------------------------
# Missing tiles are tolerated, never an error (docs/04-architecture.md §4.2)
# ---------------------------------------------------------------------------


def test_missing_radar_tiles_are_simply_not_drawn() -> None:
    """An empty radar dict never raises; the base still composes."""
    base = {(128, 160): load_fixture("base_tile_z8_x128_y160.png")}

    frame = compose_frame(base, radar_tiles={})

    assert frame.size == (CW, CH)


def test_no_tiles_at_all_still_returns_correctly_sized_frame() -> None:
    """Even with nothing to draw, compose_frame returns the right-sized canvas."""
    frame = compose_frame({}, {})
    assert frame.size == (CW, CH)


# ---------------------------------------------------------------------------
# encode_animation: docs/04-architecture.md §4.3 exact save() parameters
# ---------------------------------------------------------------------------


def test_encode_animation_produces_a_readable_animated_webp() -> None:
    """The output re-opens as WEBP with as many frames as were passed in."""
    frames = [
        Image.new("RGB", (32, 32), color)
        for color in [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
    ]

    result = encode_animation(frames)

    reopened = Image.open(io.BytesIO(result))
    assert reopened.format == "WEBP"
    assert reopened.n_frames == len(frames)


def test_encode_animation_rejects_empty_frame_list() -> None:
    """No frames is a programming error, not a silent empty WEBP."""
    with pytest.raises(ValueError):
        encode_animation([])


# ---------------------------------------------------------------------------
# encode_static: docs/04-architecture.md §4.4, a plain PNG of one frame only
# ---------------------------------------------------------------------------


def test_encode_static_produces_a_readable_png_matching_the_frame_size() -> None:
    """The output re-opens as a PNG with the exact size of the source frame."""
    frame = Image.new("RGB", (CW, CH), (10, 20, 30))

    result = encode_static(frame)

    reopened = Image.open(io.BytesIO(result))
    assert reopened.format == "PNG"
    assert reopened.size == (CW, CH)


def test_encode_static_preserves_pixel_content() -> None:
    """No quantization/dithering (§4.4): pixels round-trip exactly."""
    base = {(128, 160): load_fixture("base_tile_z8_x128_y160.png")}
    radar = {(65, 80): load_fixture("radar_tile_z7_x65_y80_no_echo.png")}
    frame = compose_frame(base, radar)

    result = encode_static(frame)

    reopened = Image.open(io.BytesIO(result)).convert("RGB")
    assert reopened.tobytes() == frame.tobytes()
