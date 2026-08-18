# RadarCat (`ha-radarcat`)

> Integració de Home Assistant que mostra **l'animació del radar meteorològic de Meteocat sobre Catalunya**, en una única entitat `image`, sense cap targeta Lovelace pròpia.

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
![GitHub release (latest by date)](https://img.shields.io/github/v/release/pmontp19/ha-radarcat)
![CI](https://github.com/pmontp19/ha-radarcat/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/github/license/pmontp19/ha-radarcat)

## Què és

RadarCat compon, cada cop que Meteocat publica un frame nou, els tiles del seu radar públic i el mapa base de Catalunya en un WEBP animat amb els últims 10 frames (aproximadament l'última hora). És el mateix pipeline de compositing (graelles, retall i escalat) que aquest autor ja fa servir a la seva app de menú macOS ([`radarcat`](https://github.com/pmontp19/radarcat)), ara portat a Home Assistant.

## Instal·lació

### Via HACS (recomanat)

1. HACS → **Integrations** → menú (⋮) → **Custom repositories**.
2. Afegiu `https://github.com/pmontp19/ha-radarcat`, categoria **Integration**.
3. Cerqueu **"RadarCat"** dins HACS i instal·leu-la.
4. Reinicieu Home Assistant.
5. **Configuració → Dispositius i serveis → Afegeix integració** → cerqueu **"RadarCat"**.

### Manual

1. Copieu `custom_components/radarcat/` d'aquest repositori dins la carpeta `custom_components/` de la vostra instal·lació de Home Assistant.
2. Reinicieu Home Assistant.
3. Afegiu la integració des de **Configuració → Dispositius i serveis**.

## Configuració

**Cap.** El flux d'instal·lació és una única pantalla de confirmació (fa una petició de prova a Meteocat abans de crear l'entrada); no hi ha cap camp a omplir perquè el radar cobreix tot Catalunya sense cap variació per usuari.

## Les entitats

| Entitat | Plataforma | Descripció |
| --- | --- | --- |
| `image.radarcat_radar` | `image` | WEBP animat amb els últims 10 frames (~1 hora) del radar de Meteocat sobre Catalunya, amb la insígnia "meteo.cat" d'atribució visible |
| `image.radarcat_radar_actual` | `image` | Només l'últim frame compost, en PNG estàtic (sense animar) - pensat per a automatitzacions o targetes que no volen moviment |

Totes dues entitats són sempre presents, sense cap camp de configuració que en triï una o altra: `radar_actual` reutilitza el mateix frame ja compost pel coordinator (l'últim de la finestra), no en refà cap ni fa cap petició de xarxa addicional.

**Com s'actualitza**: es consulten les metadades de Meteocat cada 6 minuts (la mateixa cadència amb la qual Meteocat publica). Si el frame més recent no ha canviat, no es refà res. Si n'hi ha un nou, es compon només aquell frame i es descarta el més antic de la finestra. En instal·lar la integració, o si hi ha hagut una interrupció de més d'un cicle de 6 minuts, es reconstrueix la finestra completa dels 10 frames de cop en lloc de deixar-hi un forat.

## Com utilitzar-la

Cap targeta pròpia: qualsevol targeta estàndard que mostri una entitat `image` (`picture-entity`, `picture-glance`, `glance`...) ja la renderitza i l'anima sola amb un `<img>` normal, sense cap JavaScript addicional. Es va escollir la plataforma `image` (no `camera`) i WEBP (no GIF) precisament per això: el navegador anima el WEBP sense polling propi, a diferència de `camera`, que consultaria la miniatura cada 10 segons encara que no hi hagués dades noves (vegeu `docs/04-architecture.md` §3).

```yaml
type: picture-entity
entity: image.radarcat_radar
name: Radar Catalunya
```

## Limitacions conegudes

- **Sense controls de reproducció** (play/pause/scrub): l'animació és la del WEBP nadiu del navegador. Si mai cal un control explícit, seria una targeta HACS a part, no aquesta integració.
- **Cap sensor de severitat de pluja ni ubicació d'usuari**: la classificació de pluja per color ja existeix portada a `../radarcat`, però queda diferida a v0.2.0.
- **Cap opció de configuració** (interval, nombre de frames): es reconsiderarà a v0.2.0 si cal.

## Font de dades

El radar es serveix des del giny públic de Meteocat (`static-m.meteo.cat`), no des de la seva API oficial documentada: no hi ha cap contracte de versionat ni garantia que no canviï. Detalls complets (endpoints, graelles de tiles, cadència) a [`docs/01-data-sources.md`](docs/01-data-sources.md).

## Eliminar la integració

**Configuració → Dispositius i serveis → RadarCat** → menú (⋮) → **Elimina**. Si la vau instal·lar via HACS, també podeu desinstal·lar-la des de HACS un cop eliminada l'entrada.

## Desenvolupament

```bash
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python -r requirements_dev.txt

.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

Documentació de disseny i arquitectura a [`docs/`](docs/): [fonts de dades](docs/01-data-sources.md), [integracions de referència](docs/02-existing-integrations.md), [especificació funcional](docs/03-feature-spec.md), [arquitectura](docs/04-architecture.md), [pla d'implementació](docs/05-implementation-plan.md), [quality scale](docs/06-quality-scale.md).

Voleu contribuir? Mireu [`CONTRIBUTING.md`](CONTRIBUTING.md) (convenció de commits, cicle de release, tests).

## Disclaimer

This project is **not affiliated with or endorsed by** Meteocat or the Generalitat de Catalunya. Data is public but served through Meteocat's public radar widget, not a documented, officially supported API: it can change without notice.

## Licence

MIT.
