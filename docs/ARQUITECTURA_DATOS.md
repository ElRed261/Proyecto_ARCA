# Arquitectura del dato — OMS (Neo Arca)

Documento de referencia del modelo de datos de la observación. Cierra las
decisiones tomadas con el dueño a lo largo de la revisión del oráculo
(`../OLD`, fuera del repositorio). Todo lo que se implemente debe respetar esta ley.

---

## 1. Las cuatro reglas

| # | Regla |
|---|---|
| **R1** | Se guarda **todo lo que el humano digita**: sinóptica y los tres CLI, completo, aunque el resumen mensual no use una parte. |
| **R2** | **Ningún valor calculado se guarda.** Se deriva al leer. Sólo se persisten los insumos que las fórmulas necesitan. |
| **R3** | **Cada dato tiene un único dueño.** Los demás módulos lo leen derivado; nunca lo escriben. |
| **R4** | **El día se cierra a las 06Z del día siguiente** (= 02:00 local). Después de eso no se corrige nada del día anterior sin pasar por auditoría. |

Consecuencia central: **no puede existir dos veces el mismo número**. Si se
corrige un insumo, todo lo derivado se recalcula en la próxima lectura — en
la grilla, en los CLI y en el resumen mensual.

---

## 2. Almacenamiento: SQLite es la verdad

### Tabla existente

```
summary_logs(id, station_id, year, month, day, kind, data, sha256, created_at)
```

**Un registro por día**: `kind='diario'`, `day=26`, y en `data` el documento
del día completo (sección 3). No se normaliza en tablas por hora: cargar el
día debe ser **una sola lectura**, y las estadísticas mensuales leen 28–31
documentos (~14 MB totales), costo despreciable.

### Tabla nueva (trazabilidad de correcciones)

```
document_versions(id, station_id, year, month, day, at, actor,
                  sha256_antes, sha256_despues, resumen_cambio)
```

Da la respuesta a «¿quién cambió la temperatura del 12Z y cuándo?», que es
la garantía que exige R4.

---

## 3. El documento del día (schema 2)

```json
{
  "schema": 2,
  "meta": {
    "estacion": "78486",
    "fecha": "2025-10-26",
    "actualizado": "2025-10-26T21:14:07-04:00",
    "cerrado_en": null
  },
  "horas": {
    "00Z": { "observador": "…", "datos": {…}, "grupos": {…} },
    "03Z": { … }, "06Z": { … }, "09Z": { … },
    "12Z": { … }, "15Z": { … }, "18Z": { … }, "21Z": { … }
  },
  "cli": {
    "3074": { "2": { "viento_vel": "3.6", "pres_alti": "…",
                     "fenomenos": { "granizo": true } }, … },
    "4074": { "8": { "observador": "AC", "fenomenos": {…} }, … },
    "5074": { … }
  }
}
```

- Los contenedores conservan los nombres del build (`horas` y, dentro de
  cada hora, `datos` + `synop`); lo que cambia con schema 2 es el
  **contenido**, no los nombres. Los lectores aceptan también los
  alias de la arquitectura (`synop`/`grupos`).
- **El observador no va en `meta`**: va por hora (`synop[hora].observador`,
  siempre presente aunque esté vacío) y por fila/documento en los CLI.
- `meta.fecha` en ISO. `actualizado` y `cerrado_en` en ISO con zona.

### 3.1 `horas[hora]` (el contenedor histórico se conserva)

| Bloque | Contenido |
|---|---|
| `observador` | nombre del observador de esa hora (siempre presente) |
| `datos` | `ts`, `th`, `pres_est`, `p3`, `p24`, `Tmax`, `Tmin`, `Tmax_24h`, `Tmin_24h`, `LL`, `LL_24h` |
| `grupos` | `YYGGiw`, `IrIXHVV`, `Nddff`, `7wwW1W2`, `8NhCLCMCH`, `0CSDLDMDH`, `1snTxTxTx`, `2snTnTnTn`, `3Ejjj`, `5EEEjE`, `5nFnFnFn`, `56DLDMDH`, `6RRRtr`, `7R24R24R24R24`, `8NsChshs_1…_6`, **`9spspsp_1…_24`** |

**Son 24 grupos 9Sp, ni uno más.** `555` y `29uuu` son encabezados
posteriores del mensaje SYNOP: **no** son grupos 9Sp y **no se guardan**
(`29uuu` además se calcula: es `pres_nmm`).

**Fuera de `synop`**: `correc_alt`, `visibilidad`, `viento_dir`, `viento_vel`
y todo lo calculado.

### 3.2 `cli.3074` — sólo entradas manuales
`viento_vel` (**siempre manual**), `pres_alti` (manual, altímetro) y
`fenomenos` (11 booleanos + `tiempo_presente`). Nada más.

### 3.3 `cli.4074` — sólo entradas manuales
`observador` (iniciales OBS. por fila) y `fenomenos`.

### 3.4 `cli.5074` — se guarda completo tal cual
Decisión del dueño: **se deja como está**, sin derivar nada por ahora. Se
persisten todas sus secciones (diario, horario, subsuelo, evaporímetros,
fenómenos, `iniciales_obs`). Es una desviación consciente de R2/R3 y queda
como deuda con seguimiento.

---

## 4. Tabla de mapeo única (documento ↔ formulario ↔ origen)

### 4.1 Sinóptica

| Campo del formulario | Clave del documento | Origen |
|---|---|---|
| Ts, Th, Pres. estación, P3, P24 | `datos.ts`, `datos.th`, `datos.pres_est`, `datos.p3`, `datos.p24` | **manual** |
| T máx, T mín, T máx 24h, T mín 24h, LL, LL 24h | `datos.Tmax`, `Tmin`, `Tmax_24h`, `Tmin_24h`, `LL`, `LL_24h` | **manual** |
| 44 celdas de grupo (`meteo_*`, `extra_8ns_*`) | `grupos.<nombre SYNOP>` | **manual** |

### 4.2 Derivados (nunca se guardan)

| Derivado | Fórmula | Insumos |
|---|---|---|
| `tvap` (tensión de vapor) | `h26(Th) − h27(Th)·(Ts−Th)` | `ts`, `th` |
| `hr` (humedad relativa) | `(tvap / h28(Ts))·100` | `ts`, `th` |
| `ptor` (punto de rocío) | `Ts − [1−0.01·hr]·…` | `ts`, `th` |
| `dif` | `Ts − Th` | `ts`, `th` |
| `pres_nmm` (= grupo `29uuu`) | `pres_est + ch` de la estación | `pres_est` + `stations.ch` |
| `tend_dif` | `\|pres_est − p3\|` | `pres_est`, `p3` |
| `tend_car` | `tendencia_a(pres_est − p3)` | `pres_est`, `p3` |
| `visibilidad` | tabla de 75 filas sobre los **2 últimos dígitos** de `IrIXHVV` | `grupos.IrIXHVV` |
| `tiempo_presente` | `7wwW1W2[1..3]` (fallback `Nddff`) | `grupos` |
| `correc_alt` | `ch` de la estación | `stations.ch` |

### 4.3 CLI 3074

| Campo | Origen | Transformación |
|---|---|---|
| `temp_seco` | `datos.ts` | directa |
| `temp_humedo` | `datos.th` | directa |
| `pres_est` | `datos.pres_est` | directa |
| `pres_nmm` | `pres_est` | `+ ch` |
| `tend_dif`, `tend_car` | `pres_est`, `p3` | ver 4.2 |
| `hr`, `tvap`, `ptor` | `ts`, `th` | ver 4.2 |
| `visibilidad` | `grupos.IrIXHVV` | tabla |
| `viento_dir` | `grupos.Nddff` | dígitos 2–3 (`dd`) × 10 → grados |
| **`viento_vel`** | — | **manual (siempre)** |
| **`pres_alti`** | — | **manual (siempre)** |
| **`fenomenos`** | — | **manual (entradas directas)** |

### 4.4 CLI 4074

| Campo | Origen |
|---|---|
| `lluvia_6h` | `datos.LL` |
| `temp_max`, `temp_min` | `datos.Tmax`, `datos.Tmin` |
| `estado_suelo` | `grupos.3Ejjj` |
| `nubosidad` | `grupos.Nddff` / `8NhCLCMCH` |
| **`observador`** | **manual (iniciales OBS.)** |
| **`fenomenos`** | **manual** |

---

## 5. Flujos

### 5.1 Guardar

```
edición (autosave 700 ms o Guardar)
  → validación con mensajes verbatim
  → BEGIN IMMEDIATE
      · leer documento del día (o crear vacío)
      · si está cerrado (ver 5.4) y el rol no puede corregir → rechazar
      · mutar SÓLO el módulo afectado (synop | cli.3074 | cli.4074 | cli.5074)
      · actualizar meta.actualizado, recalcular sha256
      · registrar document_versions
      · UPSERT (station, year, month, day, kind='diario')
  → COMMIT
  → marcar el día en la cola de sync
```

**Merge por módulo**: guardar la grilla sinóptica no toca `cli`; guardar un
CLI no toca `synop` ni los otros CLI. Es prevención de *lost update*, no de
consistencia (la consistencia la da R2 + R3).

### 5.2 Cargar el día (*«cargo el 26/10/2025»*)

```
load_day(estacion, 2025-10-26)
  ├─ 1 SELECT en summary_logs
  │    (si no existe → documento vacío: 8 horas + 3 CLI vacíos)
  ├─ overlay de correcciones aprobadas (auditoría)
  ├─ derivar en lectura (tabla 4.2 + 4.3 + 4.4)
  └─ devolver DayDocument:
        sinop    → 8 horas completas
        cli3074  → 24 filas (manual + derivado)
        cli4074  → 24 filas (iniciales + fenómenos + derivado)
        cli5074  → secciones completas
```

La grilla sinóptica y las tres vistas CLI se hidratan **del mismo objeto**,
en una sola pasada.

### 5.3 Resumen mensual

28–31 documentos del mes → overlay → derivar → adaptar a las 8 horas
sinópticas → estadísticas (21 columnas) → Excel. Consume 7 campos del 3074
(8 filas) y 3 del 4074 (4 filas), pero **todos esos datos están guardados**
porque R1 manda.

### 5.4 Cierre del día (R4)

**El día D se cierra a las 06Z del día D+1** (= 02:00 local).

| Hora del parte | Momento local | Editable hasta | Ventana |
|---|---|---|---|
| 06Z (D) | 02:00 | 02:00 del día D+1 | 24 h |
| 09Z (D) | 05:00 | 02:00 del día D+1 | 21 h |
| 12Z (D) | 08:00 | 02:00 del día D+1 | 18 h |
| 15Z (D) | 11:00 | 02:00 del día D+1 | 15 h |
| 18Z (D) | 14:00 | 02:00 del día D+1 | 12 h |
| 21Z (D) | 17:00 | 02:00 del día D+1 | 9 h |
| 00Z (D+1) | 20:00 | 02:00 del día D+1 | 6 h |
| 03Z (D+1) | 23:00 | 02:00 del día D+1 | 3 h |

Después del cierre:
- el observador **no edita**;
- admin / control_calidad sí, con justificación obligatoria;
- cada cambio queda en `document_versions`.

Al cerrar se escribe `meta.cerrado_en`. No se borra ni se archiva nada.

### 5.5 Exportación / importación (Drive)

| Sentido | Qué pasa |
|---|---|
| Exportar | SQLite → JSON schema 2 por día en `Documents/OMS/synop/<est>/<año>/<mes>/` |
| Importar | JSON v1 o v2 → limpiar → validar → UPSERT → reporte |
| Drive | transporta los JSON; la base es local de cada estación |

---

## 6. Migración de los archivos existentes

Los 2.554 documentos v1 tienen los carriles `9spspsp_18…_24` **contaminados**
(medido sobre 500 archivos):

| Carril | Contenido real | Acción |
|---|---|---|
| `_1` … `_17` | grupos 9Sp válidos | conservar |
| `_18` | `555` (3.855 de 3.861) | **descartar** |
| `_19` | grupo `29uuu` (`290…`) | **descartar** (se recalcula) |
| `_20`, `_22`, `_23`, `_24` | texto («Calculos de Estación»…) | **descartar** |
| valores malformados | `900090`, `9*0090`, `29071=` | **descartar** y reportar |

La migración usa la herramienta `oms_core.services.ingest` (dry-run +
manifiesto, nunca sobrescribe).

---

## 7. Plan de implementación

| Fase | Contenido | Criterio de aceptación |
|---|---|---|
| **A1** | Tabla de mapeo única en el core (`observed` / `derived`) | una sola fuente para escribir y leer; tests de ida y vuelta |
| **A2** | `load_day` completo (synop + 3 CLI + derivación) | cargar 26/10/2025 trae las 8 horas **y** los 3 CLI |
| **A3** | Guardado schema 2 (sin derivados) + `document_versions` | el documento no contiene claves derivadas |
| **A4** | Cierre a 06Z + roles + justificación | tests de ventana y de rechazo |
| **A5** | Migración de los 2.554 archivos | 0 pérdidas, reporte de descartes |
| **A6** | Export schema 2 + Drive | ida y vuelta export→import idéntica |

---

## 8. Decisiones del dueño (registro)

1. El observador es **por hora**, no por observación.
2. **24 grupos 9Sp**, ni uno más. `555` y `29uuu` van **fuera** (encabezados posteriores; `29uuu` se calcula).
3. `viento_vel` es **siempre manual**; `pres_alti` (altímetro) también.
4. Los **fenómenos booleanos** viven **sólo en el CLI**.
5. La **velocidad** no se deriva de `Nddff` (a diferencia del oráculo).
6. **CLI 5074**: se deja como está por ahora; no se deriva nada de él.
7. **Cierre del día**: 06Z del día siguiente.
8. Nombres correctos de los derivados: `hr`, `tvap`, `ptor` (no `hum_hr`, `hum_tvap`, `hum_ptor`).
9. Se guarda **toda** la información digitada, aunque el resumen no la use.

---

## 9. Reparaciones de datos aplicadas (2026-10-20)

### Precedencia de los `_cor.json`
El flujo de correcciones del oráculo escribe `<nombre>_cor.json` junto al
original. Cuando ambos existen para el mismo día, **el corregido manda**:
`legacy_migration.migrate_root()` los ordena al final de forma explícita
(no por orden alfabético) y hay un test que lo fija.

### Códigos de estación mal escritos
28 documentos tenían un código que no existe en `stations`, así que la base
los rechazaba por integridad referencial. Se corrigieron en disco (con
respaldo en `~/Documentos/OMS/respaldos/prefijos_estacion_<fecha>/`):

| Código en el archivo | Estación correcta | Evidencia |
|---|---|---|
| `485` (2) | `78485` | observadores P. HENRIQUEZ (644 : 9), BILLY, FELIZABETH |
| `784855` (1) | `78485` | FELIZABETH (514 : 149) |
| `78` (24) | `78485` | el único archivo con observador trae CAROLINA PAULINO y FRANKLIN GOMEZ; además 78485 **no** tenía esos días (opción menos destructiva: 3 colisiones contra 23 si fuera 78484) |
| `784784` (1) | `78484` | BELKIS M (468 : 132) |

Se verificó que esos documentos **no son copias** de otro día (huella de
datos distinta a las demás estaciones), por lo que son observaciones propias
con el código mal digitado.

Tres días quedaron en conflicto (`2024-04-09`, `2024-04-15`, `2026-06-02`):
ya existía un documento de `78485` para esa fecha. Se conservó el de la base,
se reescribió en disco para que disco y base coincidan, y la variante `78`
quedó en el respaldo para comparación manual.

Estado final: **2.550 documentos** en la base (2.549 schema 2 + 1 legado
previo), 2.551 versiones, **0 archivos rechazados** en el ensayo sobre el
árbol completo.

---

## 10. Rutas por sistema operativo (A7)

Dos carpetas distintas, y la razón de que no sean una:

| Qué | Dónde | Por qué |
|---|---|---|
| **Base SQLite** | carpeta de datos del usuario (`platformdirs`) | SQLite con WAL **no puede vivir en una carpeta sincronizada**: los locks no funcionan sobre red y el archivo se corrompe |
| **JSON** | `Documentos/OMS/…` | es el transporte: Drive lo sincroniza entre estaciones |

### La base, por SO

| SO | Ruta |
|---|---|
| Linux | `$XDG_DATA_HOME/oms` → `~/.local/share/oms/oms.db` |
| Windows | `%LOCALAPPDATA%\NeoArca\oms\oms.db` |
| macOS | `~/Library/Application Support/oms/oms.db` |

**Override**: `OMS_DATA_DIR=<ruta>` gana sobre todo (desarrollo, CI, instalación
portable). `oms_core.paths.database_path()` es la única fuente.

### Los JSON, por SO

| SO | Ruta |
|---|---|
| Linux | `$XDG_DOCUMENTS_DIR/OMS` → `~/Documentos/OMS` |
| Windows | `%OneDrive%\Documents\OMS` si existe, si no `%USERPROFILE%\Documents\OMS` |
| macOS | `~/Documents/OMS` |

En Windows la carpeta Documentos suele estar **redirigida a OneDrive**, por eso
se prueba primero; el árbol de JSON sí puede vivir ahí (es sólo archivos).
