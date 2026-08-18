# 01 - Fonts de dades

Evidència: ✅ verificat contra el codi font/live · 🗄️ verificat sobre una captura arxivada ·
📄 documentat per la font oficial · 🔶 inferència · ❓ no verificat.

Tota la geometria d'aquest document ve d'un projecte germà ja verificat i en producció,
`../radarcat` (app macOS Swift que compon aquest mateix radar cada 6 min des de fa setmanes):
`CLAUDE.md`, `Sources/RadarCat/RadarAPI.swift`, `RadarCompositor.swift`, `RadarGrid.swift`.
No es re-deriva res aquí que ja estigui verificat allà - es cita.

## 1. La font no és una API, és un giny

El radar de Meteocat es serveix des de `static-m.meteo.cat`, l'endpoint que alimenta el seu
propi giny web embedible (`ginys/mapaRadar`), no des de `apidocs.meteocat.gencat.cat` (l'API
oficial, amb clau i quota, però sense cap endpoint de radar documentat - ✅ verificat en la
investigació prèvia d'aquest mateix projecte, veure §11). Va ser reverse-engineered mirant el
trànsit de xarxa real del giny en un navegador (Chrome DevTools), no des d'una especificació.
✅ (`../radarcat/CLAUDE.md` §"Tile sources").

Si Meteocat canvia el conjunt de tiles, això s'ha de refer renderitzant el giny real i mesurant de
nou - mai recalculant des d'una fórmula lat/lon (aquesta relació NO és Web Mercator estàndard
per a aquestes graelles). ✅

## 2. Endpoints

| Endpoint | URL | Ús |
| --- | --- | --- |
| Metadades | `static-m.meteo.cat/ginys/referencia/tiles/dates-tiles-CAPPI_0m.json` | Timestamp del frame més recent (`dataUltimaImatge`, `dataSistema`) |
| Tiles de radar | `static-m.meteo.cat/tiles/radar/{YYYY}/{MM}/{DD}/{HH}/{mm}/{zz}/000/000/{xxx}/000/000/{yyy}.png` | PNG del tile de radar per timestamp+coordenades |
| Tiles de base | `static-m.meteo.cat/tiles/fons/GoogleMapsCompatible/{zz}/000/000/{xxx}/000/000/{yyy}.png` | PNG del tile de mapa base (sense timestamp - és estàtic) |

✅ (`RadarAPI.swift:6-33`). `{mm}`/`{HH}` etc. són components de la data en **UTC**
(`RadarAPI.swift:36-51`), no en hora local.

Format de `dataUltimaImatge`/`dataSistema`: `"MM/dd/yyyy HH:mm'Z'"` (literal `Z`, no ISO 8601
real) en locale `en_US_POSIX` i timezone UTC. ✅ (`RadarAPI.swift:74-86`).

## 3. Dues graelles de tiles diferents, dos zooms diferents

**Radar** (`RadarGrid`): només existeix a **z=7**. `x ∈ [63,68]`, `y ∈ [78,83]`, tile 256px.
Alguns d'aquests índexs retornen 404 (marge intencionat, no un error a tractar). El tile **y
creix cap al sud**. ✅ (`RadarGrid.swift:9-14`, `CLAUDE.md`).

**Base** (`BaseGrid`): existeix a z=7, z=8 i z=9, però **només z=8 és utilitzable**:

- z=7 és una imatge de giny pre-renderitzada, retallada en una graella 6x6 - **no** una
  projecció geogràfica contínua. Gairebé tota Catalunya cau en un únic tile (`x=64,y=80`); no
  hi ha Terres de l'Ebre; hi ha una vora negra real de ~24px al primer tile `y=81`. Descartat.
- z=9 és una projecció contínua real amb el doble de detall geomètric, però Meteocat renderitza
  les etiquetes de text a mida de PÍXEL fixa per tile - a z=9 la mateixa etiqueta ("Barcelona")
  surt a la meitat de mida en pantalla i n'apareixen moltes més (soroll). Mesurat normalitzant
  tots dos frames a l'amplada real de destinació (760px al popover macOS): z=9 fa les etiquetes
  MÉS PETITES, no més nítides. Descartat després de provar-ho i desfer-ho.
- **z=8** (`BaseGrid`, el que fa servir `RadarCompositor` avui): projecció contínua real, conté
  les Terres de l'Ebre, sense vora negra, sense fragment despenjat. El tile **y creix cap al
  nord** - el contrari del radar. `x ∈ [126,132]`, `y ∈ [157,162]`, tile 256px.

✅ (`RadarGrid.swift:16-29`, `CLAUDE.md` §"Tile sources", mesurat carregant el giny real de
Meteocat en un navegador i comparant amb el trànsit de xarxa capturat).

## 4. Nesting radar↔base i escalat 2x

Hi ha un nivell de zoom de diferència entre el radar (z=7) i la base (z=8): nesting XYZ estàndard, el tile de
base `(X,Y)` és fill del tile de radar `(X/2, Y/2)`. Cada tile de radar es dibuixa **escalat
2x** sobre l'espai de coordenades de la base, ancorat a `(2x, 2y)` - cobreix exactament els
seus 4 fills. Com que les dues graelles tenen la y invertida entre elles, l'ancoratge (2x,2y)
ja posa la meitat nord del tile de radar sobre el fill nord de la base sense necessitat de cap
flip d'imatge - només cal l'ancoratge correcte. ✅ (`RadarCompositor.swift:243-265`).

## 5. Retall final (bounding box de Catalunya)

En coordenades tile de `BaseGrid` (z=8): `x ∈ [127.85, 130.55]`, `y ∈ [159.4, 161.95]`. Resultat
final: **~691×653px**. Aquests valors són **mesurats empíricament** contra el contingut real
en píxels (fronteres/etiquetes, estable) amb marge afegit perquè l'eco de pluja (que sí que pot
sobresortir, p.ex. tempestes al Pirineu) no quedi tallat - **no es deriven de cap fórmula**.
✅ (`RadarCompositor.swift:40-91`).

## 6. Convenció de coordenades (si es porta a una llibreria d'imatge diferent)

El pipeline Swift treballa en coordenades natives de Core Graphics (origen baix-esquerra, y
creixent cap amunt), sense flip de CTM. **Pillow/PIL treballa a l'inrevés** (origen dalt-
esquerra, y creixent cap avall, com qualsevol llibreria d'imatge "normal"). Això vol dir que
la matemàtica de `dx`/`dy` de `RadarCompositor.swift` **no es pot copiar literalment**: cal
re-derivar-la en l'espai top-left de Pillow (el component `04-architecture.md` ho fa
explícit). Aquest avís existeix perquè el propi `radarcat` va enviar un mirall vertical complet
a producció un cop per no distingir aquests dos espais. 🔶 (avís, no fet directament al codi
d'aquest repo encara).

## 7. Cadència de refresc

Meteocat publica un frame nou cada 6 min. `radarcat` fa polling de metadades cada 6 min i
compon 10 frames (l'última hora) cada cop que `dataUltimaImatge` canvia. ✅
(`RadarAnimator.swift:47`, `RadarStore.swift:119` `refreshInterval = 6*60`).

## 8. Insígnia d'atribució incrustada als tiles de base

El tile de base `x=130,y=159` (z=8) porta la insígnia "meteo.cat" incrustada directament als
píxels (no com a overlay HTML del giny). Regió normalitzada (origen dalt-esquerra, y avall):
`x ∈ [0.764, 0.890]`, `y ∈ [0.822, 0.917]`. Els seus colors (groc del sol RGB 241,204,54 → to
48°; verd del núvol RGB 2,135,53 → to 143°) cauen als mateixos rangs de to que un eco de pluja
real - en un frame real això va generar 70 de 94 mostres "humides" que eren la insígnia, no
pluja. ✅ (`RadarCompositor.swift:93-125`, `RainDetector.swift:28-34`).

Rellevant per a aquest projecte NOMÉS si mai s'afegeix un sensor de severitat de pluja (v0.2,
fora de l'MVP): qualsevol mostreig de píxels ha d'excloure aquesta regió.

## 9. Llegenda de colors del radar (per a un futur sensor de pluja)

Classificació per to (hue), no per RGB exacte: gris (delta<30) = sense eco; 45°-170° (verd/
groc) = moderada; 170°-300° (cian/blau/lila) = feble; 300°-345° (magenta) = calamarsa; resta
(vermell/taronja) = forta. ✅ (`RainDetector.swift:211-233`). No cal per a l'MVP (imatge animada
pura), documentat aquí perquè quan es faci v0.2 no calgui re-derivar-ho.

## 10. Aparença clara/fosca: NO aplicable a aquest port

`radarcat` inverteix la luminància de la capa de base per a l'aparença fosca del menú macOS
(`CIColorInvert` + corba tonal, mai sobre el radar). Això és estètica específica d'una barra de
menú macOS - Home Assistant ja gestiona el seu propi tema al frontend (Lovelace), i la imatge
d'un `picture-entity` no necessita cap inversió pròpia. **Es descarta explícitament portar
aquesta part** - simplifica el compositing (una sola variant per frame, no dues per aparença).
🔶 (decisió d'abast d'aquest projecte, no un fet de la font).

## 11. Ús legal / atribució

- L'API oficial documentada (`apidocs.meteocat.gencat.cat`) cobreix XEMA (estacions), XDDE
  (llamps) i previsió, amb clau i quota mensual - **no** documenta cap endpoint de radar. 📄
  (investigació prèvia d'aquest mateix projecte, veure `../radarcat`'s chat history / issues).
- L'avís legal de meteo.cat permet reutilitzar contingut no protegit per PI sota la Llei
  18/2015 (reutilització d'informació del sector públic) si es manté sense alterar i amb
  atribució i data. Prohibeix l'ús de marca/logo de la Generalitat en apps no afiliades. 📄
- **Conseqüència de disseny**: com `radarcat` (que manté visible la insígnia "meteo.cat" com a
  atribució, veure §8), aquesta integració ha de conservar la insígnia tal qual apareix als
  tiles de base (no retallar-la ni tapar-la) i el `README`/`manifest.json` han d'incloure
  atribució textual explícita a Meteocat/Generalitat, mai marca gràfica pròpia que suggereixi
  afiliació. 🔶

## 12. Etiqueta de la integració a Home Assistant

`manifest.json.iot_class = "cloud_polling"` (font remota, sense descobriment local). 📄.

## 13. Etiqueta de recerca / peticions

El giny és un servei públic no documentat com a contracte versionat. Peticions només de
lectura, espaiades, mai autenticades, mai agressives - mateixa cadència que `radarcat` (6 min),
no més ràpid "perquè es pot". 🔶.

## 14. Trampes (per número, com als altres repos)

1. Radar i base map són dues piràmides diferents a zooms diferents - mai tractar-les com una.
2. Alguns índexs de `RadarGrid` (marge) 404 - silenciós i esperat, no un error.
3. El z=7 de base és un giny pre-tallat, no una projecció contínua - no ressuscitar-lo.
4. El z=9 de base té més detall geomètric però etiquetes MÉS PETITES a mida de pantalla real -
   verificar sempre renderitzant a la mida final, mai només mirant la resolució en brut.
5. La y del radar creix cap al sud; la y de la base cap al nord - fàcil d'invertir per error
   en fer el nesting 2x.
6. Els límits del retall final (§5) són mesurats en píxels, no derivats de cap fórmula lat/lon.
7. La insígnia d'atribució (§8) col·lideix amb la detecció de pluja per to - excloure-la sempre
   abans de classificar cap píxel, si mai s'implementa v0.2.
8. Les dates de metadades no són ISO 8601 real (`"MM/dd/yyyy HH:mm'Z'"`, literal `Z`).
9. Pillow treballa top-left/y-avall; el pipeline Swift original treballa bottom-left/y-amunt -
   la matemàtica de posicionament NO es pot copiar literalment (§6).
10. No hi ha quota ni ToS documentats per a aquest giny concret (a diferència de l'API oficial) -
    ser conservador amb la cadència en lloc d'assumir que "no hi ha límit" vol dir "sense límit".
11. `RadarMeta.dataUltimaImatge` és el rellotge de veritat per saber si hi ha un frame nou - mai
    disparar una recomposició per un simple tick del temporitzador si el timestamp no ha canviat.

## 15. Veredicte

**Sí, hi ha prou base per construir l'MVP, i el risc geomètric és baix.** Tota la matemàtica de
graelles/retall/nesting ja està verificada en producció per `radarcat` (setmanes funcionant,
amb tests). El risc real d'aquest projecte no és "no sabem on són els tiles" - és (a) portar
correctament aquesta matemàtica a l'espai de coordenades invertit de Pillow (§6, un error
real que ja va passar un cop al projecte germà) i (b) que la font és un giny no documentat
sense garanties de contracte (§10) - mitigat mantenint la mateixa cadència conservadora que
`radarcat` i tolerància a tiles que fallen (§14.2).
