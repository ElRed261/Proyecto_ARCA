# Transformación Excel → JSON (submódulo admin)

Generar los documentos JSON del archivo desde los Excel de observación, con los
tres bloques CLI (3074, 4074 y **5074**) completos, para rehacer el dato desde
la fuente en vez de arrastrar documentos incompletos.

Referencia: `OLD/pipeline/src/arca_pipeline/transform/excel_to_json.py`
(637 líneas, núcleo puro sin UI) y su prototipo
`OLD/miscelaneos/scratch/excel_to_json.py` (918 líneas, Tkinter).

## Specs

- **S1** Submódulo **solo para el rol administrador**, con su entrada en la
  navegación, que abre una ventana para **cargar una carpeta entera** de Excel.
- **S2** La ventana lista cada archivo con formato detectado, estación, fecha y
  resultado (transformado / omitido / error con motivo), y al final un resumen.
- **S3** Cada Excel se convierte en **un documento JSON schema 2** con
  `meta`, `synop` (las 8 horas con datos y grupos), `cli["3074"]`,
  `cli["4074"]` y `cli["5074"]`.
- **S4** Se soportan las tres versiones de Excel que existen en producción:
  `new` (hoja `3074` completa), `old` (sin hoja `3074`, solo hojas Z) y
  `horrible` (hoja `3074` con los dígitos partidos en celdas). La detección es
  por hojas, verbatim del oráculo.
- **S5** El mapa de celdas es **declarativo** y vive en un solo módulo
  (`oms_core/services/excel_formats.py`), una tabla por formato y por bloque
  (synop / 3074 / 4074 / 5074), no disperso en funciones.
- **S6** El CLI 5074 se lee de su hoja (hoy nadie la lee): extremos de
  temperatura, ráfaga máxima (dirección y velocidad), humedad máxima y mínima,
  presión máxima y mínima de estación, insolación, radiación, lluvia,
  evaporación del tanque A, punto de rocío, recorrido del viento y temperaturas
  del subsuelo, más las filas de hora local, barómetro, presión de estación,
  corrección de altitud y presión NMM.
- **S7** Nada se adivina: cada campo del documento tiene que salir de una celda
  identificada y estar cubierto por un test con un Excel real del corpus.
- **S8** Un Excel ilegible o de formato desconocido **no se escribe**: se
  informa y se sigue con el siguiente archivo.
- **S9** La escritura respeta las reglas del dato: un JSON por estación y día,
  sin reemplazar a ciegas (si el día ya existe, la ventana lo dice antes).

## Tasks

| ID | Specs | Ruta | Estado |
|---|---|---|---|
| T1 | S5, S7 | mapa declarativo de celdas de los 3 formatos (synop + 3074 + 4074) extraído del oráculo | pendiente |
| T2 | S6, S7 | mapa de celdas de la hoja 5074 en los 3 formatos | pendiente |
| T3 | S3, S4, S8 | transformador `parse_excel` → documento schema 2 | pendiente |
| T4 | S1, S2, S9 | ventana admin de carpeta completa con reporte por archivo | pendiente |
| T5 | S7 | tests por formato con Excel reales del corpus | pendiente |

## Log

- **L1** (verbatim) «Creo que hay un problema en la parte de los datos por lo
  que veo man. Dejemos el resumen en pausa y añadamos un Sub módulo de
  trasnformación de datos. Si te fijas en el OLD hay un programa que me permite
  trasnformar las obsergvasiónes en Excel para macros de diferentes formas a
  Json, Lo que quiero es solo para el admin un sub modulo que me abra una
  ventana para cargar TODOS los Excles y se trasformen a Json estructurados
  Incluyendo los datos del CLI 5074. Sin embargo hay datos que no recuerdo en
  que celdas se ubican en los Excel, porque son como 3 versiones diferentes de
  Excel. Así que trabajemos con esto primero para tener los datos BIEN hechos y
  no ir adivinando con el resumen mensual. De paso aviso que eliminaré todas las
  observasiones Json porque a la mayoría les falta el CLI 5074, así también
  iniciamos con todo limpio. Procede con el analicis.»
- **L2** Análisis: el oráculo tiene **dos** transformadores y **ninguno** lee
  el 5074 (0 coincidencias en ambos archivos). El mapa de celdas del 3074 y del
  synop sí está completo y verbatim (`SYNOP_CELL_MAP`, `SPSP_CELLS` con los 24
  carriles, `CLOUD_EXTRA_CELLS`, `DATOS_CELLS_NEW` y `DATOS_CELLS_OLD` con el
  desfase de 2 filas, `CLI3074_DATA_ROWS` = 11/14/17/20/23/26/29/32).
- **L3** El Excel real (`docs/Estación Central 01032026.xlsm`) trae las hojas
  MENU, `0006Z`…`0003Z`, FORMULAS, `3074`, `4074`, `5074`, Guardar TXT e
  Instrucciones. La hoja `5074` es un formulario ancho (A1:BE55) con grupos por
  columna: temperatura (B/E), ráfaga (I/K), humedad (R/T), presión de estación
  (V/AB), insolación (AF), radiación (AI), lluvia (AL), evaporación (AM), punto
  de rocío (AQ), recorrido del viento (AT) y temperatura del subsuelo (AF11+),
  más las filas 13-19 de hora local, barómetro, correcciones y presión NMM.
- **L4** Inventario del corpus: **4.885 Excel** en
  `~/Documentos/Trabajo-INDOMET/Datos-Brutos` (16 estaciones, años **2023-2026**)
  frente a **2.550 JSON** en el archivo (años **2000-2026**). Los JSON anteriores
  a 2023 **no tienen Excel de origen**: borrarlos perdería ese archivo, así que
  el borrado masivo tiene que esperar y limitarse a lo regenerable.
- **L5** Pausa pedida: el Resumen mensual no se retoma hasta tener el dato
  rehecho. La desviación R32 queda firmada y medida; el adaptador ya lee los
  tres layouts.
