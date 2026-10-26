# Resumen Mensual — rediseño 1:1 (rondas 13+)

Módulo Resumen del shell Neo Arca. Objetivo: llevar la página del port
funcional F5 (widgets pelados) al diseño de `OLD/IMG/Resumen Mensual.png`
con identidad violeta del módulo (`#7c3aed`; el rail usa `#a855f7`), sin
romper ninguna invariante del port (headers verbatim 31×21, overlay de
correcciones, export Excel, historial persistido en SQLite).

Referencia: `OLD/IMG/Resumen Mensual.png` (estado Historial, sin documento).
Oráculo de comportamiento: `OLD/frontend/src/features/summary/pages/SummaryPage.jsx`.

## Specs

- **S1** Cabecera: título `Resumen Mensual SYNOP` y subtítulo
  `Generación y visualización de resúmenes climáticos`.
- **S2** Acciones de cabecera: `Historial` (contorno, icono clock) siempre;
  `Tabla de Datos` (icono file-json) y `Gráficos` (icono bar-chart) solo con
  documento cargado — así lo muestra la imagen; `Generar Manual` (relleno
  violeta, icono plus) siempre.
- **S3** Panel violeta con encabezado `CARGA AUTOMÁTICA POR ESTACIÓN Y PERÍODO`
  (icono gauge) y campos `Estación Meteorológica`, `Mes`, `Año`, casilla
  `Incluir correcciones (overlay)` y botón `Cargar Mes`.
- **S4** Sección `Historial de Reportes Guardados` (icono clock). Estado vacío:
  recuadro punteado con icono de advertencia, título `No hay resúmenes` y
  cuerpo `Selecciona una estación y un período arriba para generar tu primer
  resumen mensual, o importa archivos manualmente.` (verbatim).
- **S5** Tarjetas del historial: badge de período, nombre de estación,
  `N días`, etiqueta `SYNOP`, acción borrar (trash) y acción abrir (arrow-right).
- **S6** Pestaña `Tabla de Datos`: barra meta (estación, período, días
  analizados) + exportación Excel; tabla 31×21 con encabezados oscuros.
- **S7** Invariantes del port F5 intactas: `generate_month` transaccional,
  21 headers verbatim, marca de correcciones por día, export openpyxl,
  historial persistido (`kind='mensual'`).
- **S8** La casilla `Incluir correcciones (overlay)` es real: apagada genera
  el mes sin aplicar correcciones aprobadas.

## Tasks

| ID | Specs | Ruta | Estado |
|---|---|---|---|
| T1 | S1,S2,S3,S4,S5,S8 | frame + panel + historial + overlay real | hecho (round13) |
| T2 | S6 | pestaña Tabla de Datos (meta + skin oscuro) | hecho (round13) |
| T3 | S2 | pestaña Gráficos (QtCharts, grupos temp/presión/humedad/viento/lluvia/nubes) | pendiente (botón oculto hasta que exista) |
| T4 | S2 | `Generar Manual` = importación real de archivos de observación | pendiente (hoy genera el mes seleccionado) |

## Log

- **L1** (verbatim) «Muy bien amigo, lee todas las documentaciones y contexto
  de la sesión y continuemos con el módulo de Resumen mensual.»
- **L2** (verbatim) «Continua, pero usa RTK para consumir menos tokens»

- **L3** Ronda 13 implementada: cabecera + panel violeta + tarjetas + vacío +
  pestaña Tabla (meta bar, encabezados oscuros, export esmeralda) + overlay
  real (`generate_month(..., overlay=False)`). Hallazgo: `oms_ui/icons.py`
  nunca aplicó el color pedido — la sustitución de `currentColor` corría
  sobre el cuerpo y no sobre el header SVG, así que TODOS los iconos salían
  negros; arreglado y fijado con `tests/test_icons.py`.

---

# Ronda 32 — exactitud estadística contra el oráculo y selección de fecha

## Specs

- **S9** La selección de fecha del **Sinóptico** deja de ser un campo libre: se
  elige de la lista de días que existen para la estación, con el mismo patrón
  que la Auditoría (día, observador, horas registradas).
- **S10** La **Auditoría** y el **Resumen mensual** usan ese mismo selector de
  período/estación: una sola forma de elegir el día y el mes en los tres módulos.
- **S11** El Resumen mensual reproduce las reglas estadísticas del oráculo
  (`OLD/frontend/src-tauri/src/monthly_summary/`): `process_day_data` por día
  (Rust) y las reglas de mes de `analyze_files` (Python).
- **S12** Lluvia: se respeta la **desviación firmada F5** (`CONTRATO_ORACULO.md`):
  la lluvia queda en su propio día. El oráculo la corría al día anterior y el
  dueño ordenó no portar ese artefacto. El corrimiento NO se implementa.
- **S13** Viento: velocidad en m/s desde el documento, **× 3.6 a km/h** antes
  de promediar y sumar; dirección desde el grupo `Nddff` (dd × 10), que es lo
  que el oráculo leía de su fila `cli3074.viento_dir`; formato máximo
  `"<RUMBO> <vel>,<decimal>"` con coma.
- **S14** Nubosidad por hora: `cli["4074"][fila].nubosidad` si existe; si no,
  dígito N de `Nddff`; si no, `Nh` de `8NhCLCMCH` (orden verbatim del oráculo).
- **S15** Los documentos schema 2 se leen con su forma real: horas en `synop`,
  CLI en `cli["3074"] / ["4074"] / ["5074"]`, grupos en `synop[hh]["grupos"]`.

## Tasks

| ID | Specs | Ruta | Estado |
|---|---|---|---|
| T1 | S15, S14, S13 | adaptador schema 2 en `oms_core/services/summary.py` | hecho (d6e0a43) |
| T2 | S12 | lluvia en su día: corrimiento del oráculo **no** portado (desviación F5) | hecho |
| T3 | S11 | verificación día×columna contra los dos oráculos 10/2025 | en curso |
| T4 | S9 | selector de día tipo Auditoría para el Sinóptico | pendiente |
| T5 | S10 | mismo selector en Auditoría y Resumen | pendiente |
| T6 | S11 | fijar la paridad con tests (no debilitar asserts) | pendiente |

## Log

- **L4** (verbatim) «Me gusta ese nuevo readme. Chévere. Ahora iniciemos con la
  lógica de el resumen mensual. Primero lo primero es que La selección de las
  fechas que sea como en la auditoría, tanto para seleccionar las Observaciones
  Sinópticas como para la auditoría como para el resumen mensual. Las reglas
  estadísticas del resumen mensual están en OLD. por lo que te toca recrear los
  calculos ocn rust y lo demás con Python para hacer lo demás. Analiza todo el
  proceso, como son datos estadísticos es necesario que sea una precisión
  exacta.»
- **L5** Diagnóstico medido el 2025-10 con el oráculo
  `OLD/Resumen_Mensual_Synop/resumen_{78485,78486}_102025.json`: antes del fix
  **21 de 21 columnas** diferían y casi todo salía nulo. Causa: el adaptador
  buscaba las claves planas del oráculo (`cli3074`, `cli4074`, `horas`) y los
  documentos reales son schema 2 (`synop`, `cli[...]`, grupos). Además la
  lluvia no se corría al día anterior y el viento no se derivaba del grupo
  `Nddff`. Tras T1+T2 quedan diferencias de 1 decimal en magnitudes derivadas
  (humedad/punto de rocío/tensión de vapor) y huecos de datos concretos
  (78486 sin documento el 2025-10-25; 78486 sin velocidad de viento el
  2025-10-04).
- **L6** Hallazgo de precisión: el oráculo calculaba la humedad desde
  `cli3074[row].temp_seco/temp_humedo` con **precisión completa**, mientras el
  documento schema 2 solo guarda `datos.ts/th` redondeados a 1 decimal. Por eso
  el promedio de humedad difiere ±0,1/0,2 aunque la fórmula sea idéntica. Para
  paridad bit a bit haría falta re-importar el corpus bruto
  (`~/Documentos/Trabajo-INDOMET/Datos-Brutos/Estaciones  - Json/`) que sí
  conserva esa precisión.

- **L7** Corrección del análisis: la lluvia no era un bug. `docs/CONTRATO_ORACULO.md`
  registra la desviación firmada **F5 CORREGIR** («Lluvia en su día y nubosidad
  real día/tarde»), y `tests/test_f5_summary.py` la fija como decisión de
  producto. El corrimiento al día anterior se revirtió: los dos tests que
  fallaban volvieron a pasar sin tocarlos.
- **L8** Segundo bug real del adaptador: los documentos guardan **dos layouts**
  del bloque CLI. El actual usa filas AST (`cli["3074"]["2"]`) con solo
  `viento_vel`/`pres_alti`/`fenomenos`; el migrado legacy usa
  `cli["3074"]["horas"]["1".."24"]` con todos los campos. `_cli_rows` lee los
  tres layouts (plano del oráculo, filas AST, `horas`). Medido en el archivo
  real: **1** documento con bloque legacy completo, **1.483** con el reducido y
  **1.066** sin bloque 3074.
- **L9** Brecha de precisión caracterizada: 22 de 30 días de 78485 y 24 de 31 de
  78486 difieren ±0,1/0,2 en humedad media, punto de rocío y tensión de vapor.
  Causa: el oráculo leía `hum_hr/hum_ptor/hum_tvap` ya calculados con precisión
  completa; el documento actual solo guarda `datos.ts/th` con 1 decimal y la
  humedad se deriva de ahí (regla R2: no se guardan derivados). Igualar bit a
  bit exigiría guardar derivados (rompe R2) o re-importar los valores viejos.
- **L10** Huecos de datos confirmados: `78486/2025/10/25` está **vacío** en el
  archivo (sin `datos` ni `grupos`) mientras el bruto del mismo día tiene
  Tmax 23,5 / Tmin 23 / pres_est 1010,0; y `78464/2000/01/01` es el documento
  legacy fuera de schema ya conocido. En los 2.550 documentos del archivo solo
  esos dos están vacíos.
