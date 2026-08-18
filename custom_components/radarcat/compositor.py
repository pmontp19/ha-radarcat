"""Pillow compositing and WEBP encoding for RadarCat frames.

Geometry is a port of RadarCompositor.swift's already-verified-in-production
math (../radarcat/Sources/RadarCat/RadarCompositor.swift, cited by line below);
see docs/04-architecture.md §4.1 for the one genuinely new step this port
needs that Swift never did: converting Core Graphics' bottom-left/y-up origin
to Pillow's top-left/y-down origin. Do not re-derive any grid's y-direction
here - the formulas below already carry it correctly, verified live against
Meteocat's own widget (docs/01-data-sources.md §3, §6).
"""

from __future__ import annotations

import io

from PIL import Image

from .const import (
    BASE_X_RANGE,
    BASE_Y_RANGE,
    CATALUNYA_TILE_X,
    CATALUNYA_TILE_Y,
    FRAME_INTERVAL_MIN,
    TILE_SIZE,
)

__all__ = ["compose_frame", "encode_animation", "encode_static"]


def _catalunya_crop() -> tuple[float, float, int, int]:
    """(crop_x0, crop_y0, cw, ch): the Catalonia crop in native BaseGrid pixels.

    Literal port of RadarCompositor.catalunyaCrop (RadarCompositor.swift:84-91):
    both grids are already in the same native (bottom-left, y-up) space at
    this step, so no y-flip belongs here - that conversion happens once, in
    _paste_tile, on the full canvas (docs/04-architecture.md §4.1 step 4).
    """
    x0 = (CATALUNYA_TILE_X[0] - BASE_X_RANGE.start) * TILE_SIZE
    x1 = (CATALUNYA_TILE_X[1] - BASE_X_RANGE.start) * TILE_SIZE
    y0 = (CATALUNYA_TILE_Y[0] - BASE_Y_RANGE.start) * TILE_SIZE
    y1 = (CATALUNYA_TILE_Y[1] - BASE_Y_RANGE.start) * TILE_SIZE
    return x0, y0, round(x1 - x0), round(y1 - y0)


def _paste_tile(
    canvas: Image.Image, data: bytes, dx: float, dy_native: float, span: int
) -> None:
    """Paste one tile at its native-space offset, flipped into Pillow's origin.

    dx/dy_native arrive already computed by the two call sites in
    compose_frame exactly as drawBaseTile / the radar draw loop compute them
    (RadarCompositor.swift:212-217, :257-264). y_pillow is the single
    conversion Swift never needed (docs/04-architecture.md §4.1 step 4): Core
    Graphics stays y-up with no CTM flip, Pillow is always y-down. Pasting
    through the tile's own alpha (mask=tile) rather than alpha_composite is
    required because the canvas is mode "RGB" (compose_frame) while tiles are
    RGBA: alpha_composite demands both images be RGBA and raises ValueError
    on an RGB canvas regardless of destination, whereas paste(mask=...) works
    across mode "RGB"/"RGBA" and also clips silently for tiles that land
    partly or fully outside the canvas (the margin tiles at the edge of
    BASE_X_RANGE/BASE_Y_RANGE do).
    """
    tile = Image.open(io.BytesIO(data))
    if tile.mode != "RGBA":
        tile = tile.convert("RGBA")
    if tile.size != (span, span):
        tile = tile.resize((span, span))
    y_pillow = canvas.height - dy_native - span
    canvas.paste(tile, (round(dx), round(y_pillow)), mask=tile)


def compose_frame(
    base_tiles: dict[tuple[int, int], bytes],
    radar_tiles: dict[tuple[int, int], bytes],
) -> Image.Image:
    """Composite one opaque RGB frame cropped to Catalonia (~691x653px).

    Base tiles first (opaque, they form the background), radar tiles on top
    at 2x scale (radar only exists at RadarGrid's z=7, one level below
    BaseGrid's z=8 - docs/01-data-sources.md §4), pasted through their own
    alpha so a no-echo tile's transparent pixels let the base show through
    (docs/04-architecture.md §4.1 step 5). A tile missing from either dict is
    simply not drawn, never an error (§4.2) - callers (the coordinator, T3)
    decide what "missing" means for their own cache thresholds.
    """
    crop_x0, crop_y0, cw, ch = _catalunya_crop()
    canvas = Image.new("RGB", (cw, ch), (0, 0, 0))

    for (x, y), data in base_tiles.items():
        dx = (x - BASE_X_RANGE.start) * TILE_SIZE - crop_x0
        dy_native = (y - BASE_Y_RANGE.start) * TILE_SIZE - crop_y0
        _paste_tile(canvas, data, dx, dy_native, TILE_SIZE)

    radar_span = TILE_SIZE * 2
    for (x, y), data in radar_tiles.items():
        dx = (2 * x - BASE_X_RANGE.start) * TILE_SIZE - crop_x0
        dy_native = (2 * y - BASE_Y_RANGE.start) * TILE_SIZE - crop_y0
        _paste_tile(canvas, data, dx, dy_native, radar_span)

    return canvas


def encode_animation(frames: list[Image.Image]) -> bytes:
    """Encode frames (chronological order) into a lossless animated WEBP.

    save() parameters match docs/04-architecture.md §4.3 exactly. duration is
    FRAME_INTERVAL_MIN*1000//10 ms/frame: the real Meteocat cadence is 6
    min/frame, but playing it back at that speed would look practically
    static to a human eye - same reasoning as RadarAnimator.stepInterval in
    ../radarcat. lossless=True means the Quantize/dithering concerns that
    apply to a palette format (GIF) never apply here - nothing gets
    quantized.
    """
    if not frames:
        raise ValueError("encode_animation requires at least one frame")
    buf = io.BytesIO()
    frames[0].save(
        buf,
        format="WEBP",
        save_all=True,
        append_images=frames[1:],
        duration=FRAME_INTERVAL_MIN * 1000 // 10,
        loop=0,
        lossless=True,
        method=6,
        minimize_size=True,
    )
    return buf.getvalue()


def encode_static(frame: Image.Image) -> bytes:
    """Encode a single frame as a plain PNG (docs/04-architecture.md §4.4).

    Unlike encode_animation, there is nothing to quantize here: WEBP earned
    its place over GIF (§3) only to avoid a 256-color palette mangling the
    rain-severity hue bands across multiple frames, which cannot happen to a
    single frame. PNG is simpler and universally compatible, with no reason
    to prefer WEBP for this one image.
    """
    buf = io.BytesIO()
    frame.save(buf, format="PNG")
    return buf.getvalue()
