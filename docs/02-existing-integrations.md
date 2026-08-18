# 02 - Integracions de referència

Recerca feta amb dos agents de cerca independents (GitHub, HACS default store, fòrum HA,
`home-assistant/core`) durant la fase de disseny d'aquest projecte, 2026-08-17. ✅ = verificat
contra repositori/codi real; 📄 = documentat per la font; 🔶 = inferència.

## 1. Meteocat a Home Assistant: només sensors, mai radar

`figorr/meteocat` (https://github.com/figorr/meteocat) és l'única integració Meteocat activa i
al HACS default store. ✅ Última actualització fa pocs dies en el moment de la recerca. Conté
`sensor.py` i `weather.py` - dades XEMA (estacions), previsió, alertes. **No té `camera.py` ni
`image.py`, cap imatge de radar.** ✅ (llistat de fitxers verificat via GitHub API).

`karasu/meteocat` és un intent antic i abandonat (2019, "not usable yet"). ✅

**Conclusió: cap integració HA existent mostra el radar de Meteocat, animat o no.** Aquest
projecte no té precedent directe a portar - sí el té el patró general (§2-3).

## 2. El patró més proper: AEMET (`aemet`, integració oficial de HA core)

`homeassistant/components/aemet/image.py`: un `ImageEntity` que el coordinator substitueix
sencer cada cicle amb una única imatge de radar (`Image(content_type, content)`), font oficial
d'AEMET. **Una imatge estàtica per cicle**, no animada - cap targeta Lovelace pròpia, es mostra
amb una `picture-entity`/`picture-glance` genèrica. ✅ (verificat llegint el fitxer real a
`home-assistant/core`).

Aquest és el precedent estructural que aquest projecte estén: mateix patró (coordinator →
`image` entity), amb la diferència que **el nostre contingut és un GIF/WEBP animat amb els 10
últims frames**, no una sola imatge - decidit a `03-feature-spec.md`/`04-architecture.md` a
partir de la recerca a `references/` sobre el platform `image` (veure oracle ADR).

## 3. Buienradar (NL/BE, integració oficial `buienradar`)

Exposa `camera` (`BuienradarCam`, desactivada per defecte) amb **una imatge fixa** de tot els
Països Baixos - tot i que Buienradar sí ofereix un endpoint d'animació pròpia
(`image.buienradar.nl/2.0/image/animation/...`) que HA **no** fa servir. ✅. Sense targeta
dedicada; la gent només posa una `picture-entity` genèrica sobre l'entitat `camera`.

## 4. RainViewer: `weather-radar-card` (HACS default, ~434★, molt actiu)

https://github.com/jpettitt/weather-radar-card. Compon tiles **al navegador** (Leaflet +
canvas, crossfade entre frames, compensació de moviment opcional amb optical flow en un Web
Worker). Fonts fixes per configuració (RainViewer, NOAA, DWD) - **no genèric**, afegir Meteocat
implicaria fork, no configuració. ✅.

Descartat com a base per aquest projecte: (a) no hi ha manera neta d'afegir-hi Meteocat sense
fork, (b) recompondre tiles al navegador de cada client repeteix feina que el nostre backend ja
fa un cop per cicle per a tots els clients - el patró AEMET (§2) és més eficient i més idiomàtic
en HA per a un backend Python que ja fa el compositing.

## 5. DWD (Alemanya): `Rain Warner` (comunitat, HACS custom)

Decodifica RADOLAN en una entitat `camera` + overlay Leaflet amb previsió de moviment. Sense
integració oficial de radar al core `dwd_weather_warnings`. 📄 (fòrum HA). Mateixa família que
Buienradar/AEMET: backend compon, frontend mostra amb components estàndard.

## 6. Fallback de cost zero, descartat conscientment per aquest MVP: iframe del giny

El fòrum HA recomana sovint incrustar el giny d'un tercer via `webpage`/iframe card (p.ex.
Windy.com) per a radars regionals no coberts. Descartat aquí perquè: (a) el giny de Meteocat
no és una pàgina pensada per incrustar-se de forma fiable fora del seu propi lloc (X-Frame-
Options/CSP no verificats, i encara que funcionés, no dona cap entitat ni cap dada que HA pugui
fer servir en automacions), i (b) l'objectiu explícit d'aquest projecte és una integració real
amb entitat pròpia, no un embed de tercers. 🔶 (decisió d'abast).

## 7. No existeix cap "mapa de radar natiu" al core de HA

`ha-map-card` (HACS, no core) és qui de vegades es confon amb això - afegeix capes Leaflet
extra a un mapa, però requereix connectar sensors REST/automacions a mà per a qualsevol font.
No és un precedent de codi a reutilitzar per aquest projecte. ✅.

## Veredicte

**Cap integració existent cobreix Meteocat, i el precedent més proper (AEMET) valida el patró
`DataUpdateCoordinator` + `image` entity per a "una imatge de radar servida per un backend
Python"** - l'única variació real d'aquest projecte respecte AEMET és animar-la (GIF/WEBP amb
10 frames) en lloc de servir una sola imatge per cicle, i compondre-la nosaltres mateixos amb
Pillow (Meteocat no publica cap animació ja feta, a diferència de Buienradar). Aquesta variació
es tanca a `04-architecture.md`, informada per un oracle ADR sobre `image` vs `camera` i
GIF vs WEBP (veure aquell document).
