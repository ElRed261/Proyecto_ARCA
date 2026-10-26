# Contrato del oráculo — cómo Neo Arca valida contra `../OLD`

**El oráculo es `../OLD`**: la aplicación React+Tauri v2.2.0 original, movida
fuera del repositorio por el dueño (2026-10-20) para no mezclarla con el
código nuevo. Las rutas de este documento se leen desde la raíz del repo:
archivada completa, read-only. A nivel de **fórmulas y comportamiento**,
Neo Arca se guía por ella hasta el corte (F8). Este documento fija las
reglas del contrato.

## Reglas

1. **Fórmulas verbatim.** Toda fórmula OMM/metereológica se porta copiada
   letra por letra desde el Rust del oráculo
   (`../OLD/frontend/src-tauri/src/modules/synoptic/calculations.rs`,
   `monthly.rs`) hacia `oms_calc/src/*.rs`. Sin "mejoras", sin renombres
   de variables, sin reordenar términos. El diff del port debe poder
   justificarse línea por línea.
2. **Mensajes exactos.** Los mensajes de validación/error que el usuario
   ve son parte del contrato: "el grupo 'X' en hora YYZ", "Falta nombre
   de observador", "Sistema de Calidad", etc. viajan verbatim.
3. **Diff vacío = fase verde.** Cada fase se valida corriendo el corpus
   real (488 observaciones + 63 documentos JSON legacy) por el código
   nuevo y por el oráculo: los resultados deben ser byte-a-byte iguales
   (salvo las desviaciones firmadas abajo).
4. **Semántica de documentos.** El documento diario JSON (meta/horas/
   datos/synop/calculado + claves CLI `cli3074`/`cli4074`/`cli5074`) y el
   mensual mantienen la forma del oráculo — el importador legacy y la
   sincronización dependen de ella.
5. **`../OLD` es read-only.** La migración de datos legacy corre solo
   sobre copias temporales. Nada escribe dentro de `../OLD`, y el repo tiene
   `OLD/` en `.gitignore` para que no vuelva a entrar por accidente.

## Mapa de portación (fórmula → destino)

| Oráculo (OLD) | Neo Arca |
|---|---|
| `calculations.rs::tendencia_a` | `oms_calc::tendencia_a` (F0) |
| `calculations.rs` (realizar_calculos y helpers) | `oms_calc::synoptic.rs` + 26 pyfunctions (F2) |
| `monthly.rs` | `oms_calc::monthly.rs` (F2) |
| `json_handler/utils.rs` (validaciones, cap SYNOP) | `oms_core.services.synoptic` |
| `modules/cli/mod.rs` (save/load genérico, derived pass) | `oms_core.services.cli` |
| `storage.rs` write_guard / dual save | `oms_core` (atomic write + Savepoint) |
| `audit/service.rs` | `oms_core.services.audit` (F6) |
| `sync` (backoff `min(2^attempts,60)`) | `oms_core.services.sync` (F7) |
| `SynopticPage.jsx` (flujo UI) | `oms_ui.pages.synoptic` (F4 + rondas) |
| `cli3074/4074/5074 pages` | `oms_ui.pages.cli{3074,4074,5074}` (rondas 4–5) |

**Puente Python↔Rust**: los datos entran y salen como JSON
(`realizar_calculos_json`, `recalculate_derived_fields_json`,
`process_day_data_json`) — la frontera es pura, sin I/O ni Qt dentro de
`oms_calc` (ADR-03).

## Desviaciones firmadas (aprobadas por el dueño, en orden)

Estas son las ÚNICAS desviaciones del oráculo. Todo lo demás es verbatim.

1. **D3 (F3)** — `secrets` de Python para sesiones (en vez del mecanismo Tauri).
2. **D4 (F3/F6)** — tildes verbatim en etiquetas; delete + deactivate para estaciones.
3. **D7 (F1)** — env JSON vacío se ignora en importación (corrige un bug del oráculo).
4. **F5 CORREGIR** — Lluvia en su día y nubosidad real día/tarde (el oráculo
   tenía artefactos heredados; el dueño ordenó corregirlos en vez de portarlos).
4b. **R32 PRECISIÓN** — Humedad relativa, punto de rocío y tensión de vapor se
   derivan de los insumos guardados (`datos.ts` / `datos.th`, un decimal). El
   oráculo leía `hum_hr` / `hum_ptor` / `hum_tvap` ya calculados con precisión
   completa, así que el promedio mensual difiere en ±0,1/0,2. El dueño eligió
   la derivación: la regla R2 (no se guardan valores calculados) es lo que
   mantiene el dato fiable, y la estadística se calcula siempre desde el mismo
   insumo. El resto de columnas (temperaturas, presiones, viento, nubosidad y
   lluvia) coincide exacto con el oráculo.
5. **F6 keep-deny** — encargado mantiene el modelo deny-por-defecto.
6. **F7 D1/D2** — wrapper de hilo sync; `last_error` nunca levanta.
7. **Rondas de UI (4–12)** — la presentación se re-crea 1:1 contra las
   imágenes `OLD/IMG/*.png` **cuando la imagen y el JSX difieren, gana la
   imagen** (p. ej. headers uniformes del 4074, sufijos sin índices,
   disciplina de color roja del 5074). El *comportamiento* (navegación,
   guardado, atajos) sigue al JSX verbatim.
8. **Autosave sin botón Guardar (ronda 8)** — los CLIs guardan con debounce
   silencioso; el oráculo tenía botón explícito.

## Cómo se valida una fase nueva

```bash
# 1. tests del núcleo + frontera (venv free-threaded)
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests -q

# 2. tests de UI (venv GIL: PySide6 6.12 solo wheels GIL)
QT_QPA_PLATFORM=offscreen .venv-gil/bin/python -m pytest tests -q

# 3. lint
.venv/bin/ruff check oms_core oms_ui tests packaging run_dev.py

# 4. oráculo de fórmulas: corpus real 0 mismatches (F1 §6.3, F2, F4, F5)
```

Después: evidencia en `Migración/evidencias/<fase>/` (nota + capturas) y
commit `neoarca(<fase>)` con el resultado medido en el cuerpo.
