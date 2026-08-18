# Brand assets

`icon.png` (256×256, square, transparent corners) and `icon@2x.png` (512×512) live in
this directory. Home Assistant >= 2026.3 serves them through the Brands Proxy API, so
no upstream submission is involved: `home-assistant/brands` no longer accepts new
custom integrations. `ha-radarcat` tracks exactly those two files under
`custom_components/radarcat/brand/`.

Both files are required, not optional: HACS validation fails its `brands` check when a
repository neither ships `brand/icon.png` nor is listed in the (closed) brands repository.

The artwork is a rain cloud over three drops (blue-yellow-blue, a nod to the radar
severity legend's colour bands) with radar arcs fanning below, on a blue gradient disc -
stays legible down to 16 px on both light and dark backgrounds.
