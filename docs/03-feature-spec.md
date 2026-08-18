# 03 - Especificació funcional (MVP v0.1.0)

## 1. Objectiu

Una entitat Home Assistant que mostra **l'animació del radar de Meteocat sobre Catalunya**,
sense cap targeta Lovelace pròpia: qualsevol targeta estàndard (`picture-entity`,
`picture-glance`, `glance`) l'ha de renderitzar i animar sola, amb un `<img>` normal.

## 2. Entitats (v0.1.0)

| Entitat | Plataforma | Descripció |
| --- | --- | --- |
| `image.radarcat_radar` | `image` (`ImageEntity`) | L'animació dels últims 10 frames (~1h) com a WEBP animat |
| `image.radarcat_radar_actual` | `image` (`ImageEntity`) | Només l'últim frame compost, com a PNG estàtic (sense animar) |

Totes dues entitats sempre presents, sense cap camp de configuració que en triï una o altra
(decisió explícita de Pere, veure `AGENTS.md`): alguns usos (automatitzacions, dashboards amb
poc ample de banda, targetes que no volen moviment) volen només "com està ara mateix", el mateix
patró que fa servir AEMET (`02-existing-integrations.md` §2) - no calia forçar un únic entity per
a totes dues necessitats ni afegir un toggle al flux de configuració (que hauria trencat el
"zero camps" de §3). `radar_actual` reutilitza el mateix frame ja compost pel coordinator (l'últim
de la finestra), no en refà cap.

**Res més a v0.1.0.** Cap sensor, cap ubicació, cap avís de pluja - es documenten com a v0.2.0
a `05-implementation-plan.md` §"Després de l'MVP". La motivació és velocitat i abast mínim
provable, no una limitació tècnica: la lògica de classificació de pluja ja existeix portada a
`../radarcat` i es podria afegir després sense tocar el compositing.

## 3. Configuració

**Zero camps d'usuari.** El radar és tota Catalunya, sense variació per usuari - no hi ha res a
triar (a diferència dels siblings, que sí que necessiten ubicació/radi perquè el seu senyal és
puntual). El flux de configuració és una única pantalla de confirmació que fa una petició de
prova a l'endpoint de metadades (`test_before_configure`) abans de crear l'entrada:
- Èxit (200 + JSON amb els dos camps de data) → crea l'entrada.
- Qualsevol altra cosa (timeout, xarxa, JSON il·legible) → `cannot_connect` al formulari.

`single_config_entry: true` al manifest, més `unique_id` fix (`DOMAIN`) - una segona instal·lació
s'avorta, com a `cecat`.

## 4. Cicle de dades

- Sondeig de metadades cada **6 min** (mateixa cadència que `../radarcat`, veure
  `01-data-sources.md` §7/§13 - no té sentit sondejar més sovint una font que només publica
  cada 6 min, i seria més agressiu del que cal).
- Quan `dataUltimaImatge` canvia: es compon el frame nou (tiles de radar d'aquest timestamp +
  base cachejada) i s'afegeix a la finestra dels últims 10 frames (es descarta el més antic).
  Es reencapsula la finestra sencera com WEBP animat i es publica.
- Quan `dataUltimaImatge` NO canvia: no es refà res (ni xarxa ni compositing) - mateix
  contracte que `RadarStore.refresh()` (`isNew` check).
- Primer cicle (arrencada freda): es construeixen les 10 marques de temps de l'última hora
  (`latest`, `latest-6min`, ..., `latest-54min`, com `RadarAnimator.frameSet`) i es componen
  totes - igual que fa `radarcat` en arrencar.

## 5. Disponibilitat

Mateix patró que `cecat`/`incendiscat` (`docs/04-architecture.md` §5): `available` es basa en
l'antiguitat de l'última dada bona, no en `last_update_success` sol - un error transitori manté
visible l'última animació coneguda; només una font realment aturada (`> max(6×interval, 1h)`)
posa l'entitat `unavailable`.

## 6. Atribució i disclaimer

`_attr_attribution` a tota entitat: "Servei Meteorològic de Catalunya (Meteocat)". La insígnia
"meteo.cat" que porten els tiles de base **no es retalla ni es tapa** - veure
`01-data-sources.md` §11 sobre per què això és un requisit legal, no estètic.

## 7. No-objectius explícits d'aquest MVP

- Cap targeta Lovelace personalitzada (JS). Zero.
- Cap control de reproducció/scrub (play/pause/seek com `RadarAnimator` a macOS) - l'animació
  del WEBP és nativa del navegador, sense controls; si mai cal, seria una targeta HACS a part,
  no aquesta integració.
- Cap aparença clara/fosca pròpia (veure `01-data-sources.md` §10).
- Cap sensor de severitat de pluja ni ubicació d'usuari (v0.2.0).
- Cap opció de configuració (interval, etc.) - es reconsidera a v0.2.0 si cal.

## 8. Criteris d'acceptació de l'MVP

1. Instal·lada la integració (config flow sense camps), apareix `image.radarcat_radar`.
2. El seu contingut és un WEBP animat vàlid, amb la insígnia "meteo.cat" visible i sense
   distorsionar la geografia de Catalunya (verificable obrint el fitxer com a imatge).
3. En canviar `dataUltimaImatge` a la font, l'entitat es refresca (nou `image_last_updated`)
   sense reiniciar Home Assistant.
4. `pytest` (cobertura ≥95% als mòduls core: `api`, `compositor`, `coordinator`), `ruff check`,
   `ruff format --check`, hassfest i HACS validation, tots verds.
5. Verificat personalment pel manager executant una instància HA real amb la integració
   carregada (no només tests) - veure `05-implementation-plan.md` §"Verificació".
