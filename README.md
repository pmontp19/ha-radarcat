# RadarCat (`ha-radarcat`)

Home Assistant custom integration showing the **Meteocat weather radar animation over
Catalonia**, the same composited radar this author's macOS menu-bar app
([`radarcat`](https://github.com/pmontp19/radarcat)) already renders.

> 🚧 **Scaffold only, design in progress.** Boilerplate (CI, release, HACS, licence) is in
> place. The design docs and the integration code are not written yet — see `AGENTS.md` for
> the current state.

## Installation

### Via HACS (recommended)

1. HACS → **Integrations** → menu (⋮) → **Custom repositories**.
2. Add `https://github.com/pmontp19/ha-radarcat`, category **Integration**.
3. Search **"RadarCat"** inside HACS and install it.
4. Restart Home Assistant.
5. **Settings → Devices & services → Add integration** → search **"RadarCat"**.

### Manual

1. Copy `custom_components/radarcat/` from this repository into the `custom_components/`
   folder of your Home Assistant installation.
2. Restart Home Assistant.
3. Add the integration from **Settings → Devices & services**.

## Development

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the dev environment, commit convention and test
stack. Design docs live in [`docs/`](docs/).

## Disclaimer

This project is **not affiliated with or endorsed by** Meteocat or the Generalitat de
Catalunya. Data is public but served through Meteocat's public radar widget, not a
documented, officially supported API — it can change without notice.

## Licence

MIT.
