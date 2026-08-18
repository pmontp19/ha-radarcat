# 05 - Pla d'implementació (MVP v0.1.0)

Taula de tasques per a l'orquestració (skill `orchestrate`). Mode: **arbre compartida +
bloqueig per fitxer** (Mode A) - cada unitat és un conjunt de fitxers disjunt, sense worktrees
separats. Manager = Sonnet 5 (aquesta sessió). Workers i revisors = Sonnet 5 (subagents,
`Agent Teams` no disponible en aquest entorn - flag experimental no activat). Oracle = Opus,
usat puntualment (ja consultat a §3 de `04-architecture.md`).

No referenciar aquests números `T*` a cap commit ni comentari de codi (`AGENTS.md`/
`CONTRIBUTING.md`).

## Ones

### T1 - Foundation

**Fitxers**: `custom_components/radarcat/const.py`, `tests/conftest.py`, `tests/fixtures/`
(copiar els PNG/JSON reals de `docs/captures/` - ja capturats, veure sota),
`custom_components/radarcat/strings.json` (claus esquelet), `translations/{ca,es,en}.json`
(esquelet amb les mateixes claus, contingut buit de moment).

Contingut de `const.py`: literal de `04-architecture.md` §2, sense inventar res més.

Fixtures reals ja capturades a `docs/captures/` (2026-08-17, un radar tile z=7 x=65 y=80 -
transparent, sense eco en aquell moment - i un base tile z=8 x=128 y=160, més
`metadata_sample.json`): copiar-les (no re-descarregar) a `tests/fixtures/` amb noms
descriptius. Qualsevol fixture addicional necessària (p.ex. un tile de radar AMB eco, per
provar la classificació de colors futura) s'ha de marcar `_SYNTHETIC` si es genera a mà.

**Sense dependències.** Bloqueja T2/T3/T4.

### T2 - `api.py` + `compositor.py` (Unit 1, risc geomètric)

**Fitxers**: `custom_components/radarcat/api.py`, `custom_components/radarcat/compositor.py`,
`tests/test_api.py`, `tests/test_compositor.py`.

**Contracte**: `04-architecture.md` §4 (amb la conversió de coordenades §4.1 - llegir-la sencera
abans d'escriure una línia), §5.

**Test crític de geometria** (obligatori, no opcional): compondre un frame amb els tiles reals
de `tests/fixtures/` i verificar que la insígnia "meteo.cat" (regió del tile base x=130,y=159,
veure `01-data-sources.md` §8) acaba a la cantonada INFERIOR DRETA del frame final - no a la
superior, no a l'esquerra. Si algun worker no pot verificar-ho amb els fixtures disponibles,
ha de baixar UN tile real més (`x=130,y=159`, base, z=8, sense timestamp) ell mateix, de forma
puntual i respectuosa (`01-data-sources.md` §13), i afegir-lo a fixtures.

Depèn de T1. Bloqueja T3/T4 (però pot avançar en paral·lel amb ells si el worker treballa
directament contra aquest contracte - decisió del manager: **es fa seqüencial igualment**,
perquè és l'única peça amb risc geomètric real i cal revisar-la abans que la resta hi construeixi
a sobre. Veure "Onades" més avall.

### T3 - `coordinator.py` + `__init__.py` (Unit 2)

**Fitxers**: `custom_components/radarcat/coordinator.py`, `custom_components/radarcat/
__init__.py`, `tests/test_coordinator.py`, `tests/test_init.py`.

**Contracte**: `04-architecture.md` §6. Exemplar a mirar per a l'estructura general (no per a la
lògica, que és pròpia): `../ha-cecat/custom_components/cecat/coordinator.py` i `__init__.py`.

Depèn de T1 + T2 (revisat).

### T4 - `image.py` + `entity.py` + `config_flow.py` + `diagnostics.py` + traduccions (Unit 3)

**Fitxers**: la resta de `custom_components/radarcat/*.py` no llistats a T2/T3, `strings.json`
(contingut final), `translations/{ca,es,en}.json` (contingut final), `custom_components/
radarcat/brand/` (icona - es pot deixar com a TODO explícit si no hi ha temps, mai inventar-se
un PNG), `tests/test_image.py`, `tests/test_config_flow.py`, `tests/test_diagnostics.py`,
`tests/test_translations.py` (parity check, com `../ha-cecat`).

**Contracte**: `04-architecture.md` §7/§8. Exemplar: `../ha-cecat/custom_components/cecat/
entity.py` (patró `CoordinatorEntity` + `available`), `../ha-cecat/custom_components/cecat/
config_flow.py` (patró `test_before_configure`, simplificat aquí perquè no hi ha camps).

Depèn de T1 + T2 (revisat).

## Onades (paral·lelisme real)

1. **Ona 1**: T1 (un worker).
2. **Ona 2**: T2 sol (worker + revisor adversarial + cicle de correcció fins que estigui net).
3. **Ona 3**: T3 i T4 en paral·lel (dos workers, arxius disjunts, tots dos contra el T2 ja
   revisat i real, no contra un contracte de paper) - cadascun amb el seu revisor adversarial.
4. **Ona 4**: T5 Integration.

## T5 - Integration

**Fitxers**: qualsevol seam que quedi (p.ex. `PLATFORMS` a `__init__.py` si T3/T4 no hi han
coincidit exactament), `docs/06-quality-scale.md` + `custom_components/radarcat/
quality_scale.yaml` (KISS, com `../ha-bomberscat`, escrit contra el codi REAL, no abans).

Passos:
1. `ruff check .` + `ruff format --check .` nets.
2. `pytest --cov=custom_components/radarcat --cov-fail-under=95` verd.
3. hassfest local (`python -m script.hassfest` si es pot, o simplement confirmar que
   `manifest.json`/`strings.json`/`translations` són coherents a mà si l'eina no és fàcil
   d'executar fora del checkout complet de `home-assistant/core`).
4. Commit (el manager, mai els workers).

## T6 - Verificació personal (manager, no delegable)

**Real, no només tests**: instal·lar `homeassistant` en un venv, crear una config mínima que
carregui `custom_components/radarcat/` des d'aquest repo, arrencar `hass`, afegir la integració
via UI o `configuration.yaml` de prova, confirmar:
- L'entitat `image.radarcat_radar` existeix i `available`.
- El seu contingut (`/api/image_proxy/...` o llegint `coordinator.data.content` directament) és
  un WEBP vàlid - obrir-lo com a imatge (com fa `../radarcat` amb el PNG de depuració) i
  confirmar visualment que és Catalunya, no un mirall ni un frame en blanc per error de xarxa.
- Els logs no tenen cap traça/excepció no gestionada.

Només després d'això es considera l'MVP fet - "els workers diuen que els tests passen" no és
verificació (regla dura de `orchestrate`).

## Després de l'MVP (v0.2.0, no ara)

- `binary_sensor`/`sensor` de severitat de pluja (port de `RainDetector.swift`) - **decisió
  revisada (oracle Opus, 2026-08-18)**: NO cal repetir el patró de selector de mapa dels
  siblings (`avisoscat`/`bomberscat`). HA ja té una ubicació de casa
  (`hass.config.latitude`/`longitude`/`elevation`), llegida directament per integracions reals
  del core (`sun`, `zone`, i sobretot `met` - previsió meteorològica que fa exactament això amb
  `track_home`). Únic camp de configuració necessari: el radi d'alerta. Cal:
  - Guardar-se de la ubicació no configurada: `latitude == 0 and longitude == 0` (o
    `config_source == ConfigSource.DEFAULT`) vol dir "sense configurar", com fa `met` mateix
    (avortar/desactivar amb un missatge clar).
  - Escoltar `EVENT_CORE_CONFIG_UPDATE` per reaccionar a un canvi de ubicació, però MAI llegir
    coordenades del payload de l'event (no és un snapshot garantit) - sempre rellegir
    `hass.config` de nou, igual que `sun`/`zone`/`met`.
  - Documentar l'única limitació real: "casa" a HA és un punt estàtic, no la ubicació de
    l'usuari en temps real (a diferència del CoreLocation de l'app macOS) - pot no coincidir amb
    on realment viu qui fa servir la integració (segona residència, instància allotjada, llar
    compartida).
  - Marcador de la ubicació sobre la imatge composta: no fer-ho a v1 - el `map` card natiu de HA
    ja dibuixa punt+radi contra `zone.home` sense cap codi d'imatge, i només val la pena si
    algun dia cal mostrar-ho fora d'un dashboard (notificacions amb imatge fixa). Reconsiderar
    un cop existeixi la transformada lat/lon -> píxel per al mostreig (gairebé gratis llavors).

- **Mode fosc: decisió revisada (oracle Opus, 2026-08-18) - descartat per ara, no és un rebuig
  definitiu.** La justificació original d'aquest projecte (`01-data-sources.md` §10, "HA ja
  gestiona el seu tema, la imatge no necessita inversió pròpia") era incompleta: el "chrome" del
  dashboard sí que es repinta sol, però el contingut d'una imatge servida és un raster inert que no
  ho fa mai - el mateix error de categoria que documenta `../radarcat/CLAUDE.md` per a l'app
  macOS. Verificat que no hi ha cap manera barata de resoldre-ho: el backend mai sap el tema del
  navegador en una petició d'imatge (`image_proxy` és agnòstic d'identitat, `state`+`token`
  només), l'únic mecanisme natiu de HA per triar imatge segons tema (`dark_mode_image`) no
  existeix a `picture-entity`/`picture-glance` (només a `picture-elements`, i reportat trencat
  des de 2021), i un filtre CSS `invert()` seria una rotació de to de 180° que trencaria la
  llegenda de colors de pluja (moderada->blau, feble->taronja...) exactament igual que un
  filtre ingenu en Python. Única solució real si mai cal: repetir el patró `radar`/
  `radar_actual` amb dues entitats més (`_dark`), amb el mateix algorisme d'inversió asimètrica
  de `RadarCompositor.swift` (base invertida, radar mai tocat) - doblant el cost de compositing
  per un desajust merament estètic, no funcional. No construir-ho sense una queixa real
  d'usuari primer.

- **Controls de zoom: investigat (oracle Opus, 2026-08-18, navegador real + trànsit de xarxa
  del propi giny de Meteocat) - descartat, no és un rebuig definitiu.** El giny oficial és
  Leaflet amb `maxNativeZoom: 7` fixat explícitament a la capa de radar (trobat literalment al
  seu JS): el radar mai fa cap petició per sobre de z=7, a cap nivell de zoom, ni tan sols al
  topall del propi giny (z=10) - Leaflet només escala visualment el mateix tile de z=7
  (confirmat visualment: l'eco surt borrós en apropar-se, mai més detallat). El mapa base sí
  que canvia de z de veritat (08->09->10), però sempre acompanyat d'un requadre proporcionalment
  més petit - mai "mateix requadre, z més alt", que és exactament l'error que aquest projecte ja
  va descobrir i evitar (z=9 fa les etiquetes més petites, no més nítides, veure
  `01-data-sources.md` §3). Conclusió: un zoom de veritat és canviar la MIDA DEL REQUADRE (i
  re-triar la z adequada per a aquell requadre), no exposar la z com a paràmetre - una funció
  molt més gran que un simple toggle, i que contradiu els no-objectius explícits de l'MVP (zero
  camps, zero targeta pròpia, `03-feature-spec.md` §3/§7). Cap drecera de dashboard tampoc:
  `picture-entity`/`picture-glance` no tenen cap opció de retall/zoom pròpia. Si mai es
  reconsidera: fer-ho com `radar`/`radar_actual` - entitats addicionals amb retalls fixos,
  mesurats i verificats a mà un per un (p.ex. una zona metropolitana concreta), mai un paràmetre
  genèric de zoom.

- Blueprint d'automació de notificació de pluja.
- Opcions de configuració (interval, nombre de frames).
