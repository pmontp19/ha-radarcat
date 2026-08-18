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

**Contracte**: `04-architecture.md` §6. Exemplar a mirar per l'estructura general (no per la
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

- `binary_sensor`/`sensor` de severitat de pluja (port de `RainDetector.swift`), amb ubicació
  d'usuari com als siblings (radi de seguiment/alerta).
- Blueprint d'automació de notificació de pluja.
- Opcions de configuració (interval, nombre de frames).
