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
