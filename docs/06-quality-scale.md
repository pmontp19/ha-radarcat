# 06 - Quality Scale

Apliquem la **[Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/)** oficial de Home Assistant amb filtre **KISS i sentit comú**, el mateix criteri que `../ha-bomberscat/docs/06-quality-scale.md` i `../ha-avisoscat`.

- **Objectiu realista**: bronze + silver complerts, la majoria de gold, sense perseguir platinum al 100%.
- **No** aspirem a PR a `home-assistant/core` (la font no és una API oficialment suportada), així que no cal platinum al 100%.
- **Distribució**: HACS Custom Repository. Però la qualitat del codi ha de ser la mateixa que si fos core.

L'estat de cada regla es declara a [`custom_components/radarcat/quality_scale.yaml`](../custom_components/radarcat/quality_scale.yaml) (format oficial HA; hassfest valida que estigui present i ben format). Aquest document i el YAML han de portar sempre els mateixos verdictes.

**Llegenda**: ✅ `done` · ⏳ `todo` (prioritzat més avall) · 🚫 `exempt` (no aplica, amb raó)

Aquest projecte té una superfície molt més petita que els siblings: **una sola entitat** (`image.radarcat_radar`), **zero camps de configuració**, **cap event**, **cap blueprint**, **cap dada d'usuari**. Cada regla d'aquest document s'ha verificat contra el codi real de T1-T4 (83 tests, 100% de cobertura a `custom_components/radarcat`), no copiada dels veredictes dels siblings: moltes regles que allà tenen sentit (taules d'entitats de diagnòstic, events, `entity_category` per sensors) aquí són `exempt` perquè la cosa que classificarien senzillament no existeix.

---

## Criteris de classificació (KISS)

Quan dubtem entre `done` i `todo`, mirem:

1. **És gairebé gratis?** (1-5 línies de codi, patró ben documentat) → fer-ho ja, marcar `done`.
2. **És valor real per l'usuari?** (diagnosi, recovery, traduccions) → fer-ho en v1.
3. **És coixí per a futures integracions?** → marcar `todo` i tornar-hi.
4. **No aplica al nostre context?** (auth, discovery, devices físics, camps de configuració que no existeixen) → `exempt` amb comentari.

Quan una regla és `exempt`, **sempre** portem un comentari d'una línia explicant per què. Així un revisor extern (o nosaltres d'aquí 6 mesos) entén la decisió.

---

## Resum per tier

| Tier | Done | Todo | Exempt | Total |
| :---: | ---: | ---: | ---: | ---: |
| 🥉 Bronze | 14 | 1 | 5 | 20 |
| 🥈 Silver | 5 | 1 | 4 | 10 |
| 🥇 Gold | 7 | 4 | 10 | 21 |
| 🏆 Platinum | 2 | 1 | 0 | 3 |
| **Total** | **28** | **7** | **19** | **54** |

> Recompte verificat a Integration (T5) contra `custom_components/radarcat/quality_scale.yaml` i el codi real (83 tests, 100% cobertura, `ruff check`/`ruff format --check` nets).

---

## 🥉 Bronze - base obligatòria

### ✅ Ja complerts

| Regla | Com |
| --- | --- |
| `appropriate_polling` | `SCAN_INTERVAL_MIN = 6` min, la mateixa cadència amb la qual Meteocat publica un frame nou (`docs/01-data-sources.md` §7/§13). Sondejar més sovint no aportaria res |
| `common_modules` | `api.py`, `compositor.py`, `coordinator.py`, `entity.py`, `image.py`, `config_flow.py`, `diagnostics.py` separats, cadascun d'una responsabilitat |
| `config_flow` | `config_flow.py` + `config_flow: true` al manifest |
| `config_flow_test_coverage` | `test_config_flow.py` cobreix el formulari, l'èxit, els dos errors i l'avortament de segona instància |
| `dependency_transparency` | `requirements: ["Pillow>=10.0.0"]` al manifest, versionat explícitament |
| `entity_unique_id` | `RadarcatEntity.__init__` fixa `_attr_unique_id = f"{entry_id}_{description.key}"` |
| `has_entity_name` | `_attr_has_entity_name = True` a `RadarcatEntity` |
| `runtime_data` | `entry.runtime_data = coord` a `__init__.py`, amb `RadarcatConfigEntry = ConfigEntry[RadarcatCoordinator]` tipat (sense `hass.data`) |
| `test_before_configure` | `config_flow.py` crida `fetch_metadata` abans de crear l'entrada; qualsevol fallada mapeja a `cannot_connect` |
| `test_before_setup` | `async_setup_entry` crida `coord.async_config_entry_first_refresh()`, que llança `ConfigEntryNotReady` automàticament si falla (verificat llegint `homeassistant/helpers/update_coordinator.py`) |
| `unique_config_entry` | `async_set_unique_id(DOMAIN)` + `_abort_if_unique_id_configured()`, més `single_config_entry: true` al manifest; tests `test_entry_has_fixed_unique_id`/`test_second_instance_is_aborted` |
| `docs_high_level_description` | Secció "Què és" del README |
| `docs_installation_instructions` | Secció "Instal·lació" (HACS + manual) del README |
| `docs_removal_instructions` | Secció "Eliminar la integració" del README |

### ⏳ Pendent

| Regla | Esforç | Què |
| --- | ---: | --- |
| `brands` | S | `custom_components/radarcat/brand/icon.png` no existeix (verificat: no hi ha directori `brand/`). No es fabrica cap PNG per fingir-ho fet: cal una icona real 256×256 abans de publicar-la via Brands Proxy API |

### 🚫 Exempts

| Regla | Raó |
| --- | --- |
| `action_setup` | Cap service action exposada: entitat passiva única, res a disparar |
| `docs_actions` | Conseqüència de l'anterior |
| `docs_triggers` | La integració no dispara cap event a `hass.bus`: no hi ha res disparador-de-trigger a documentar |
| `docs_conditions` | Cap Condition platform pròpia ni atribut prou distintiu més enllà de la doc genèrica de HA per a `image` |
| `entity_event_setup` | No ens subscribim a events d'entitat d'altres integracions; només escoltem el nostre propi coordinator |

---

## 🥈 Silver - robustesa runtime

### ✅ Ja complerts

| Regla | Com |
| --- | --- |
| `config_entry_unloading` | `async_unload_entry` desforça els platforms i crida `coordinator.async_shutdown()` |
| `entity_unavailable` | `RadarcatEntity.available` sobreescriu el default de `CoordinatorEntity` i delega a `RadarcatCoordinator.available` (finestra d'antiguitat pròpia, `docs/04-architecture.md` §6) |
| `integration_owner` | `codeowners: ["@pmontp19"]` al manifest |
| `log_when_unavailable` | `_async_update_data` llança `UpdateFailed` en cada fallada de metadades, exactament el patró "Coordinator approach" de la regla oficial. Verificat llegint `update_coordinator.py` real: `DataUpdateCoordinator._async_refresh` ja fa `logger.error(...)` un únic cop en la transició a fallada i `logger.info("Fetching %s data recovered", ...)` un únic cop en la recuperació. No calia cap crida manual a `_LOGGER` en aquest mòdul |
| `test_coverage` | 100% a `custom_components/radarcat` (`pytest --cov-fail-under=95`, gate a `ci.yml`) |

### ⏳ Pendent

| Regla | Esforç | Què |
| --- | ---: | --- |
| `parallel_updates` | XS | Cap constant `PARALLEL_UPDATES` declarada a `image.py` (verificat, absent). La regla oficial no té excepció per plataformes basades en coordinator: cal declarar `PARALLEL_UPDATES = 0` explícitament encara que, amb una sola entitat push, no hi hagi col·lisió real |

### 🚫 Exempts

| Regla | Raó |
| --- | --- |
| `action_exceptions` | Cap service action |
| `docs_configuration_parameters` | Zero camps de configuració existeixen (`docs/03-feature-spec.md` §3): no hi ha res a documentar |
| `docs_installation_parameters` | Mateix motiu: no hi ha cap paràmetre a referenciar |
| `reauthentication_flow` | El giny de Meteocat no és autenticat (sense clau ni sessió): no hi ha res a re-autenticar |

---

## 🥇 Gold - UX excel·lent

### ✅ Ja complerts

| Regla | Com |
| --- | --- |
| `devices` | Un únic device de servei "RadarCat" (`DeviceEntryType.SERVICE`) a `RadarcatEntity.__init__` |
| `diagnostics` | `diagnostics.py`: `frame_count`, `latest_timestamp`, `last_update_success`, `available`, `consecutive_failures`, `last_error`. Res a redactar (sense ubicació d'usuari) |
| `docs_data_update` | Secció "Com s'actualitza" del README (cadència, cicle de 10 frames) |
| `docs_examples` | Exemple de targeta Lovelace (`picture-entity`) al README |
| `docs_known_limitations` | Secció "Limitacions conegudes" del README (sense play/pause/scrub, sense sensor de pluja) |
| `docs_supported_functions` | La funció de l'única entitat descrita al README |
| `entity_translations` | `_attr_translation_key = "radar"` + `translations/{ca,es,en}.json`, `entity.image.radar.name` a totes tres. Verificat per `test_translations.py` (paritat de claus i placeholders) |

### ⏳ Pendent

| Regla | Esforç | Què |
| --- | ---: | --- |
| `docs_troubleshooting` | S | Cap secció de resolució de problemes escrita encara: sense historial real de suport encara del qual partir |
| `exception_translations` | S | Cap carpeta `exceptions/` ni cadena d'excepció traduïda (verificat, absent) |
| `icon_translations` | S | Cap `icons.json` (verificat, absent) |
| `repair_issues` | M | Cap crida a `async_create_issue` a tot el codi (verificat, absent) |

### 🚫 Exempts

| Regla | Raó |
| --- | --- |
| `discovery` | Servei `cloud_polling` (manifest): no és un dispositiu de xarxa local descobrible |
| `discovery_update_info` | Conseqüència de l'anterior: no existeix cap flux de discovery |
| `docs_supported_devices` | La integració no exposa dispositius físics, consumeix un giny web públic |
| `docs_use_cases` | L'única entitat és una imatge de només visualització, sense cap estat ni atribut sobre el qual construir una automació a v0.1.0. El sensor de severitat de pluja (el disparador natural) es diferi a v0.2.0 |
| `dynamic_devices` | Un únic device fix per entrada, sense cicle de vida d'alta/baixa |
| `entity_category` | No existeix cap entitat de diagnòstic/config a v0.1.0: l'única entitat és el contingut principal que ofereix la integració |
| `entity_device_class` | `ImageEntity`/`ImageEntityDescription` (`homeassistant.components.image`, verificat llegint el codi real) no defineixen cap concepte de `device_class` |
| `entity_disabled_by_default` | L'única entitat és el contingut principal: desactivar-la per defecte contradiria el propòsit de la integració, i encara no existeix cap entitat secundària/diagnòstica per desactivar |
| `reconfiguration_flow` | Zero camps de configuració: no hi ha res a reconfigurar |
| `stale_devices` | Sense cicle de vida dinàmic de device (mateix motiu que `dynamic_devices`) |

---

## 🏆 Platinum - excel·lència tècnica

### ✅ Ja complerts

| Regla | Com |
| --- | --- |
| `async_dependency` | `aiohttp`/`ClientSession` a tot arreu (`api.py`, `coordinator.py`, `config_flow.py`); cap ús de `requests` ni cap altra I/O de xarxa síncrona |
| `inject_websession` | `async_get_clientsession(hass)` és l'única font de sessió, tant a `coordinator.py` com a `config_flow.py`; `api.py` mai crea la seva pròpia (rep `session` com a paràmetre a totes les seves funcions) |

### ⏳ Pendent

| Regla | Esforç | Què |
| --- | ---: | --- |
| `strict_typing` | M-L | Cap configuració de `mypy` a `pyproject.toml` ni a cap workflow de CI (verificat, absent). Ningú l'ha executat encara contra aquest codi |

---

## Prioritització per versió (KISS)

### v0.1.0 (aquesta release): ja complert
Bronze + Silver quasi complets (`brands`/`parallel_updates` són l'únic deute, tots dos XS-S). Gold: diagnòstics, devices, traduccions i tota la documentació bàsica del README ja fets.

### v0.2.0: Gold restant i coixí tècnic
- `parallel_updates` (XS, hauria de fer-se abans fins i tot, és gairebé gratis)
- `brands` (icona real 256×256)
- `icon_translations`, `exception_translations`, `repair_issues` (probablement lligats al sensor de severitat de pluja i a la detecció de canvis d'esquema del giny)
- `docs_troubleshooting`

### v0.3.0: Platinum tècnic
- `strict_typing` (mypy net)

---

## Què **no** farem (sentit comú)

| Descart | Raó |
| --- | --- |
| Sensors/events/blueprint a v0.1.0 | Fora d'abast explícit de l'MVP (`docs/03-feature-spec.md` §7). Moltes regles Gold (`docs_use_cases`, `entity_category`, `entity_disabled_by_default`) només tindran sentit real quan aquestes entitats existeixin |
| Discovery local | Servei cloud, no hi ha res a la xarxa local a descobrir |
| Reauth flow | Font pública sense autenticació |
| Platinum al 100% sense PR a core | La font no és una API oficialment suportada; no hi ha cap maintainer de `home-assistant/core` a satisfer |

---

## Referències

- [Integration Quality Scale (overview)](https://developers.home-assistant.io/docs/core/integration-quality-scale/)
- [Rules index](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/): cada regla té la seva pàgina amb exemples
- Format de `quality_scale.yaml` i criteris KISS calcats de `../ha-bomberscat/docs/06-quality-scale.md` i `../ha-avisoscat`
