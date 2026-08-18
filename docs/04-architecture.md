# 04 - Arquitectura (contracte vinculant)

Aquest document és el contracte que els mòduls paral·lels han de complir exactament - signatures
i formes de dades, no aproximacions. Ve informat per un ADR d'oracle (Opus, 2026-08-17,
investigació directa contra `home-assistant/core`/`frontend` reals) sobre `image` vs `camera` i
GIF vs WEBP; el veredicte i les cites són a §3.

## 1. Mòduls

```
custom_components/radarcat/
├── __init__.py          # setup/unload, PLATFORMS, RadarcatConfigEntry
├── const.py             # DOMAIN, URLs, graelles, retall, atribució, cadència  [Foundation]
├── api.py               # fetch de metadades + tiles (sessió injectada)        [Unit 1]
├── compositor.py        # compositing Pillow + codificació WEBP                [Unit 1]
├── coordinator.py       # DataUpdateCoordinator, finestra de 10 frames         [Unit 2]
├── entity.py            # base compartida (DeviceInfo, atribució, available)   [Unit 3]
├── image.py             # ImageEntity                                         [Unit 3]
├── config_flow.py       # flux sense camps + test_before_configure            [Unit 3]
├── diagnostics.py       # export redactat                                     [Unit 3]
├── strings.json + translations/{ca,es,en}.json                                [Unit 3]
└── manifest.json                                                              [Foundation, ja fet]
```

## 2. `const.py` (Foundation - contracte que TOTS els altres mòduls importen)

```python
DOMAIN = "radarcat"

METADATA_URL = "https://static-m.meteo.cat/ginys/referencia/tiles/dates-tiles-CAPPI_0m.json"
RADAR_TILES_BASE = "https://static-m.meteo.cat/tiles/radar"
FONS_TILES_BASE = "https://static-m.meteo.cat/tiles/fons/GoogleMapsCompatible"

# RadarGrid - z=7, únic zoom on existeix el radar. y creix cap al SUD.
RADAR_Z = 7
RADAR_X_RANGE = range(63, 69)   # 63..68 inclusiu
RADAR_Y_RANGE = range(78, 84)   # 78..83 inclusiu

# BaseGrid - z=8, únic zoom utilitzable per al mapa base. y creix cap al NORD (oposat al radar).
BASE_Z = 8
BASE_X_RANGE = range(126, 133)  # 126..132 inclusiu
BASE_Y_RANGE = range(157, 163)  # 157..162 inclusiu
TILE_SIZE = 256

# Retall de Catalunya en coordenades tile de BaseGrid (mesurat en píxels, veure
# 01-data-sources.md §5 - NO derivat de cap fórmula lat/lon).
CATALUNYA_TILE_X = (127.85, 130.55)
CATALUNYA_TILE_Y = (159.4, 161.95)

# Mínim de tiles de base per considerar la càrrega "bona" i cachejar-la (veure
# RadarCompositor.minGoodBaseTiles al projecte germà: els que intersecten de
# veritat el retall final, no el marge del voltant).
MIN_GOOD_BASE_TILES = 12

FRAME_COUNT = 10
FRAME_INTERVAL_MIN = 6
SCAN_INTERVAL_MIN = 6  # mateixa cadència que ../radarcat - no té sentit sondejar més sovint

ATTRIBUTION = "Servei Meteorològic de Catalunya (Meteocat)"
IMAGE_CONTENT_TYPE = "image/webp"
```

`RADAR_X_RANGE`/`RADAR_Y_RANGE` inclouen marge (alguns índexs 404, silenciós i esperat -
`01-data-sources.md` §14.2).

## 3. ADR: `image` platform + WEBP animat (oracle Opus, verificat contra codi real)

**Decisió**: `ImageEntity` (platform `image`), **no** `camera`. `_attr_content_type =
"image/webp"`, **no** GIF.

**Per què `image` i no `camera`** (verificat llegint `homeassistant/components/image/
__init__.py` i `camera/__init__.py` reals): `ImageView.handle` (image) escriu els bytes
directament a `web.Response.body` sense re-codificar res; el frontend (`hui-image.ts`) pinta un
`<img>` pla - el navegador anima sol. `camera`, en canvi, en mode "auto" fa polling de la
miniatura amb un `UPDATE_INTERVAL` fix de **10 s**, sempre, independentment de si hi ha dades
noves - pitjor que el refresc reactiu de `image`.

**Per què WEBP i no GIF**: el frame final ja és RGB opac (el compositing ja ha resolt l'alfa
abans de codificar), així que l'alfa binari de GIF no aporta res. El risc real és que la
paleta de 256 colors de GIF barregi les bandes de to de la llegenda de pluja (blau/verd/groc/
taronja/vermell/magenta, veure `01-data-sources.md` §9) - rellevant si algun dia s'hi construeix
un classificador (v0.2). WEBP amb `lossless=True` no quantitza res. `libwebp` ve inclòs a tots
els wheels oficials de Pillow (a diferència de `libimagequant`, exclòs per llicència GPLv3) -
cap dependència de sistema extra. Cap part d'`image_proxy` ni del frontend distingeix GIF de
WEBP: el mateix camí de codi serveix totes dues.

**Refresc reactiu**: el coordinator bumpeja `image_entity._attr_image_last_updated =
dt_util.utcnow()` i crida `async_write_ha_state()` DESPRÉS de cada reconstrucció amb èxit - mai
dins de `async_image()`. El frontend afegeix `&state=<image_last_updated isoformat>` a la URL
automàticament (`computeImageUrl`) - no cal cap paràmetre de cache-busting escrit a mà.

## 4. `compositor.py` (Unit 1 - la peça de risc geomètric real)

Funcions pures (sense HA, sense xarxa - reben bytes ja descarregats):

```python
def compose_frame(
    base_tiles: dict[tuple[int, int], bytes],   # (x, y) BaseGrid -> PNG bytes
    radar_tiles: dict[tuple[int, int], bytes],  # (x, y) RadarGrid -> PNG bytes (pot faltar-ne)
) -> PIL.Image.Image:
    """Compon un frame RGB opac, retallat a Catalunya (~691x653px)."""

def encode_animation(frames: list[PIL.Image.Image]) -> bytes:
    """WEBP animat, lossless, dels frames en ordre cronològic."""
```

### 4.1. CONVERSIÓ DE COORDENADES - llegir abans d'escriure `compose_frame`

`RadarCompositor.swift` treballa en coordenades natives de Core Graphics: **origen baix-
esquerra, y creixent cap AMUNT**, sense flip. **Pillow és l'invers: origen dalt-esquerra, y
creixent cap AVALL.** Aquesta NO és una diferència de graelles (radar vs base) - és una
diferència entre els dos RENDERITZADORS, i s'ha de corregir un cop, al final, sobre el canvas
sencer, no barrejant-la amb la lògica de graelles.

**Procediment (no et desviïs ni re-derivis la direcció de cap graella pel teu compte - les
fórmules de sota ja la porten incorporada correctament, verificada en producció):**

1. Calcula `crop_x0`, `crop_y0`, `cw`, `ch` EXACTAMENT com `RadarCompositor.catalunyaCrop`
   (`RadarCompositor.swift:84-91`), amb `CATALUNYA_TILE_X`/`CATALUNYA_TILE_Y`/`BASE_X_RANGE`/
   `BASE_Y_RANGE`/`TILE_SIZE` de `const.py`. Resultat esperat: `cw=691`, `ch=653`.
2. Per cada tile de base `(x, y)`: calcula `dx`, `dy_natiu` EXACTAMENT com
   `drawBaseTile` (`RadarCompositor.swift:212-217`):
   `dx = (x - BASE_X_RANGE.start) * TILE_SIZE - crop_x0`
   `dy_natiu = (y - BASE_Y_RANGE.start) * TILE_SIZE - crop_y0`
3. Per cada tile de radar `(x, y)`, escalat 2x: EXACTAMENT com
   `RadarCompositor.swift:257-264`, amb `radar_ts = TILE_SIZE * 2`:
   `dx = (2*x - BASE_X_RANGE.start) * TILE_SIZE - crop_x0`
   `dy_natiu = (2*y - BASE_Y_RANGE.start) * TILE_SIZE - crop_y0`
4. **La ÚNICA conversió que Pillow necessita i Swift no** - aplica-la igual per a tiles de
   base (`tile_h = TILE_SIZE`) i de radar (`tile_h = radar_ts`), just abans de `Image.paste`:
   `y_pillow = ch - dy_natiu - tile_h`
   Enganxa amb `canvas.paste(tile_img, (round(dx), round(y_pillow)))`.
5. Ordre de dibuix: totes les de base primer (formen el fons), després totes les de radar a
   sobre (poden tenir alfa parcial allà on no hi ha eco - `Image.alpha_composite` o
   `canvas.paste(tile, box, mask=tile)` si el tile és RGBA).

Si un test de geometria (Unit 1, veure `05-implementation-plan.md`) no dona la insígnia
"meteo.cat" a la cantonada inferior dreta del frame final, **atura't i informa** - no ajustis
signes a cegues fins que "sembli bé"; la causa gairebé segur és haver saltat el pas 4 o haver-lo
aplicat només a un dels dos tipus de tile.

### 4.2. Tolerància a tiles absents

Un tile que falta (404, timeout) simplement no es dibuixa - mai una excepció que aturi tot el
frame (`01-data-sources.md` §14.2). `compose_frame` rep només els tiles que `api.py` ha
aconseguit baixar; no necessita saber per què en falta algun.

### 4.3. `encode_animation`

```python
frames[0].save(
    buf, format="WEBP", save_all=True, append_images=frames[1:],
    duration=FRAME_INTERVAL_MIN * 1000 // 10,  # veure nota de cadència de reproducció sota
    loop=0, lossless=True, method=6, minimize_size=True,
)
```

Nota: la durada REAL entre frames representa 6 min de dades, però reproduir-la a 6 min/frame
seria una animació pràcticament estàtica a ull humà - mateixa idea que `RadarAnimator.
stepInterval` (0.35s), que reprodueix ràpid perquè és per a l'ull humà, no un rellotge real.
`duration=600` ms/frame (loop continu, `loop=0`) és el punt de partida raonable; ajustable sense
tocar cap altra part del sistema si en la verificació manual es veu massa ràpid/lent.

### 4.4. `encode_static` - l'últim frame sol (v0.1.1, `image.radarcat_radar_actual`)

```python
def encode_static(frame: PIL.Image.Image) -> bytes:
    """PNG del frame més recent, sense animar. Sense concerns de paleta/dithering
    (§4.3) - un únic frame no té res a quantitzar."""
```

PNG, no WEBP: l'animació necessitava WEBP per evitar la paleta de 256 colors de GIF (§3), però
un frame sol no té aquest problema - PNG és més simple i universalment compatible, sense cap
motiu real per triar WEBP aquí. `IMAGE_CONTENT_TYPE` (animat) i `STATIC_IMAGE_CONTENT_TYPE`
(`"image/png"`) són constants separades a `const.py`.

## 5. `api.py` (Unit 1)

```python
class RadarcatConnectionError(Exception): ...
class RadarcatFormatError(Exception): ...

async def fetch_metadata(session: aiohttp.ClientSession) -> tuple[datetime, datetime]:
    """(latest_image_utc, system_utc). Llança RadarcatConnectionError/RadarcatFormatError."""

async def fetch_tile(session: aiohttp.ClientSession, url: str) -> bytes | None:
    """None (no excepció) si 404 o cos buit - un tile que falta és normal, veure §4.2."""

def radar_tile_url(timestamp: datetime, x: int, y: int) -> str: ...
def base_tile_url(x: int, y: int) -> str: ...
```

`session` s'injecta sempre des de `async_get_clientsession(hass)` (Platinum `inject_websession`
- mai crear una sessió pròpia dins d'aquest mòdul).

## 6. `coordinator.py` (Unit 2 - depèn del contracte de §4/§5, no de la seva implementació)

```python
@dataclass
class RadarcatData:
    content: bytes              # WEBP animat, ja codificat
    static_content: bytes       # PNG de només l'últim frame (§4.4), ja codificat
    latest_timestamp: datetime  # dataUltimaImatge del frame més nou de la finestra
    frame_count: int

class RadarcatCoordinator(TimestampDataUpdateCoordinator[RadarcatData]):
    ...
```

`static_content` es deriva de `frames[-1]` (el mateix objecte `PIL.Image` que ja forma part de la
finestra, no un fetch/compose apart) via `encode_static` (§4.4) - cap cost addicional de xarxa.

Estat entre cicles: `_base_tiles: dict | None` (cachejat un cop que arriba a
`MIN_GOOD_BASE_TILES`, mai abans - mateix contracte que `ensureBase` del projecte germà: una
càrrega per sota del llindar NO es cacheja com a definitiva, es reintenta sencera el proper
cicle), `_frames: list[tuple[datetime, PIL.Image.Image]]` (finestra de com a màxim
`FRAME_COUNT`, ordenada cronològicament, la més antiga es descarta en afegir-ne una nova).

Cicle (`_async_update_data`):
1. `fetch_metadata`. Si falla → `_record_failure` + `raise UpdateFailed` (mateix patró
   `cecat`/`incendiscat`: mai perdre `self.data` per un error transitori).
2. Si `latest_timestamp` == l'últim conegut → retorna `self.data` sense tocar res (§4 de
   `03-feature-spec.md`).
3. Si és la primera execució amb èxit (`_frames` buit): calcula les `FRAME_COUNT` marques de
   temps (`latest`, `latest - 6min`, ..., ordre cronològic) i compon-les totes.
4. Altrament: compon NOMÉS el frame nou (les altres 9 ja són a `_frames`), afegeix-lo, descarta
   el més antic si la finestra supera `FRAME_COUNT`.
5. `encode_animation(frames actuals)` → `RadarcatData`. Retorna.

`available` (property): mateix patró que `CecatCoordinator.available`
(`../ha-cecat/custom_components/cecat/coordinator.py:182-194`) - `> max(6*interval, 1h)` és
`unavailable`, no `last_update_success` sol.

## 7. `image.py` + `entity.py` (Unit 3)

```python
class RadarcatEntity(CoordinatorEntity[RadarcatCoordinator]):
    """DeviceInfo compartit + ATTRIBUTION + available (delega al coordinator, com CecatEntity)."""

class _RadarcatImageBase(RadarcatEntity, ImageEntity):
    """Sincronització d'`image_last_updated` compartida entre les dues entitats `image`
    (animada i estàtica, §"v0.1.1" més avall) - la mateixa lògica de bump, la mateixa
    condició de "només si latest_timestamp ha avançat", una sola vegada."""

class RadarcatImage(_RadarcatImageBase):
    _attr_content_type = IMAGE_CONTENT_TYPE
    _attr_translation_key = "radar"

    async def async_image(self) -> bytes | None:
        return self.coordinator.data.content if self.coordinator.data else None

class RadarcatStaticImage(_RadarcatImageBase):
    _attr_content_type = STATIC_IMAGE_CONTENT_TYPE
    _attr_translation_key = "radar_actual"

    async def async_image(self) -> bytes | None:
        return self.coordinator.data.static_content if self.coordinator.data else None
```

El bump de `_attr_image_last_updated` es fa al LISTENER del coordinator (registrat a
`async_added_to_hass`, o directament aprofitant que `CoordinatorEntity` ja crida
`async_write_ha_state()` en cada actualització) - MAI dins `async_image()` (advertència
explícita de la doc oficial, veure ADR §3). Cal seguir el patró ja corregit en revisió
(§"State of the repository" a `AGENTS.md`): seed `_attr_image_last_updated` també a `__init__`,
no només al listener, perquè `async_config_entry_first_refresh()` ja ha corregit dades abans que
cap de les dues entitats es construeixi.

### v0.1.1 - `image.radarcat_radar_actual`

Segona entitat, sempre present (docs/03-feature-spec.md §2, decisió explícita, no una opció de
configuració). `async_setup_entry` (T3/`__init__.py`, ja landed) ha d'afegir totes dues entitats
a la mateixa crida `async_add_entities([...])`.

`DeviceInfo`: dispositiu de servei únic "RadarCat", `entry_type=SERVICE`, com els tres siblings.

## 8. `config_flow.py` + `diagnostics.py` (Unit 3)

Config flow: una sola pantalla, sense camps, `test_before_configure` (crida `fetch_metadata`),
`unique_id` fix = `DOMAIN`. Sense options flow a v0.1.0 (no hi ha res a configurar, §3 de
`03-feature-spec.md`).

Diagnostics: `frame_count`, `latest_timestamp`, `coordinator.last_update_success`,
`consecutive_failures` si n'hi ha. Res a redactar a v0.1.0 (no hi ha ubicació d'usuari) -
deixar-hi un comentari explicant per què, com fan els siblings amb les regles `exempt`.

## 9. Resiliència i `quality_scale.yaml`

Mateix criteri KISS que `../ha-incendiscat/docs/06-quality-scale.md`: bronze+silver complets,
la majoria de gold, sense perseguir platinum al 100%. `docs/06-quality-scale.md` es crea a
Integration amb l'estat real un cop el codi existeix (no abans, per no inventar-se `done` que
encara no ho són).
