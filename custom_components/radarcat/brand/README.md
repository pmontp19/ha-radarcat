# Brand assets

`icon.png` (256×256, square, transparent corners) and `icon@2x.png` (512×512) live in
this directory. Home Assistant >= 2026.3 serves them through the Brands Proxy API, so
no upstream submission is involved: `home-assistant/brands` no longer accepts new
custom integrations. `ha-radarcat` tracks exactly those two files under
`custom_components/radarcat/brand/`.

Both files are required, not optional: HACS validation fails its `brands` check when a
repository neither ships `brand/icon.png` nor is listed in the (closed) brands repository.

The artwork is Material Design Icons' `radar` glyph (the same icon system Home Assistant
uses throughout its own UI), recoloured with a blue gradient and rendered on a transparent
background - stays legible down to 16 px on both light and dark backgrounds. An earlier
hand-drawn cloud-and-raindrops version was replaced after review: freehand shapes drawn
with raw drawing primitives (arcs, polygons) read as amateurish next to a real vector
icon set's glyphs.
