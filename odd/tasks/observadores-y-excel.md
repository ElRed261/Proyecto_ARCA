# Observadores y carga de Excel (ronda 23)

Tres defectos reportados en vivo por el dueño más una capacidad nueva: iniciales
del observador en los tres CLI, nombre del observador al abrir un día, el gate
del grupo `7wwW1W2` según la Tabla 1860, y la carga de planillas `.xlsm` que
hoy sólo existe en el código viejo.

## Specs

S1. «En el CLI 4074 las filas de las horas 15 y 16 tienen 0, quitalos.»
    El `0` gris del placeholder queda únicamente en las filas 2, 5, 8, 11, 14,
    17, 20 y 23 (las ocho horas sinópticas).

S2. «Quiero también que se pueda cargar archivos de Excel habilitado para
    macros, pero necesitará una transformación de datos, En la carpeta OLD
    dentro de Proyectos existe el código exacto de transformar de Excel a JSon,
    solo quedaría copiarlo y modificarlo para que use el esquema nuevo de Json.»
    Decisión: el botón «Importar Excel» vive **dentro de «Cargar Observación»**.
    Fuente del algoritmo: `OLD/pipeline/src/arca_pipeline/transform/excel_to_json.py`
    (637 líneas, puro, `openpyxl`, formatos `new` / `old` / `horrible`).

S3. «Quiero también que el orden en el que aparecen los dias al cargar una
    Observación sea 1 2 3 4 5 6 ... y no 1 10 11 12... así se pierde la
    secuencia.»

S4. «Además que no veo que se cargue el nomre del observador en la Observación.»
    El nombre del observador se guarda y se lee por hora; la ventana tiene que
    mostrarlo al abrir el día.

S5. «Quiero que leas el manual para que veas cuando el IrIxhVV tiene como
    segundo dígito el 2 pues se desactiva el campo 7wwW1W2, que sucede, pero
    estoy viendo que se carga un valor cuando si no está activo ese campo debe
    quedar en 7.»
    Manual OMM N°306, Tabla de cifrado 1860: el grupo `7wwW1W2` se **incluye**
    con `iX` 1, 4 y 7, y se **omite** con 2, 3, 5 y 6. Con el grupo omitido el
    campo muestra `7` y queda apagado. Decisión del dueño: se muestra `7` y se
    **conserva** lo ya guardado.

S6. «Tampoco veo que se carguen las iniciales de los Observadores en los CLI,
    cada hora debe tener las iniciales del observador, pero no los veo, si
    falta ese campo en el Squema del Json añadelo.»
    Decisión del dueño: es un campo propio de cada CLI llamado **OBS**; el 4074
    lo tiene por fila (24), el 5074 tiene **uno solo** para toda la planilla y
    el 3074 también lo necesita por hora. Las iniciales se guardan en el JSON
    del CLI, no se derivan del nombre de OBS.

S7. «Si el Excel trae un día que ya existe en la base» → nunca sobrescribe:
    avisa y pide confirmación antes de reemplazar.

## Tasks

- [x] T1 (S1) `oms_ui/pages/cli4074.py`: `ZERO_PLACEHOLDER_ROWS` sin 15 ni 16 · tests
- [x] T2 (S3) `oms_ui/observation_picker.py`: días ordenados numéricamente · tests
- [x] T3 (S4) `oms_ui/pages/synoptic.py`: el nombre del observador se pinta por hora · tests
- [x] T4 (S5) gate `iX ∈ {1,4,7}` en `oms_calc` + campo en `7` apagado conservando lo guardado · tests Rust/Python
- [x] T5 (S6) campo OBS por hora en 3074, uno solo en 5074, y carga/guardado en el JSON · tests
- [x] T6 (S2/S7) `oms_core/services/excel_import.py` (port de `excel_to_json.py` al schema 2) + botón en el selector + confirmación de reemplazo · tests

## Log

L1 (dueño, verbatim): «En el CLI 4074 las filas de las horas 15 y 16 tienen 0,
quitalos. Quiero también que se pueda cargar archivos de Excel habilitado para
macros, pero necesitará una transformación de datos, En la carpeta OLD dentro de
Proyectos existe el código exacto de transformar de Excel a JSon, solo quedaría
copiarlo y modificarlo para que use el esquema nuevo de Json. Quiero también que
el orden en el que aparecen los dias al cargar una Observación sea 1 2 3 4 5 6
... y no 1 10 11 12... así se pierde la secuencia. Además que no veo que se
cargue el nomre del observador en la Observación. Quiero que leas el manual para
que veas cuando el IrIxhVV tiene como segundo dígito el 2 pues se desactiva el
campo 7wwW1W2, que sucede, pero estoy viendo que se carga un valor cuando si no
está activo ese campo debe quedar en 7. Tampoco veo que se carguen las iniciales
de los Observadores en los CLI, cada hora debe tener las iniciales del
observador, pero no los veo, si falta ese campo en el Squema del Json añadelo.
Procesa todo paso a aso y preguntame ante la más minima duda.»

L2 (dueño, respuestas): las iniciales son «un campo en la columna de los CLI que
se llama OBS en el 4074, en los Json deberían estar esas iniciales, tambien el
5074 tiene un solo campo de OBS a diferencia de el 4074»; el Excel va «dentro de
«Cargar Observación»»; con iX=2 se debe «mostrar «7» y conservar lo guardado»; y
un día existente «nunca sobrescribe: pide confirmación».

L3 (evidencia): manual OMM N°306, Tabla de cifrado 1860 — «1 Dotada de personal
Incluido · 2 Dotada de personal Omitido (ningún fenómeno significativo) ·
3 Dotada de personal Omitido (sin observación) · 4 Automática Incluido, tablas
4677 y 4561 · 5 Automática Omitido · 6 Automática Omitido · 7 Automática
Incluido, tablas 4680 y 4531». El código tenía `matches!(ix, "1" | "4")`:
faltaba el 7.

L4 (implementación): T1-T4 en `3b8f15b`, T5 en `9b73acf`, T6 con el port en
`oms_core/services/excel_import.py` (mapas de celdas y decodificadores
verbatim del original; el destino son claves de formulario tomadas de
`document_map`, nunca una segunda tabla). El libro se abre con
`keep_vba=True` para `.xlsm` y **jamás se escribe**: las macros quedan
intactas. Un día existente pide confirmación antes de reemplazarse (S7) y el
libro roto se informa con el mensaje del parser. 21 tests con libros
sintéticos construidos por openpyxl.

## Slice boundary

This feature's commits on `neo-arca` (the delivery strategy for the whole
branch is still the owner's decision — see README):

- `3b8f15b` T1-T4 (4074 rows, day order, per-hour observer, Table 1860 gate)
- `9b73acf` T5 (observer initials in the CLI 3074 / already in 5074)
- `96bb02d` T6 (Excel import module, window button, confirmation, tests)

Each one is self-contained: tests and docs travel with the behaviour they
describe, so any of them can be reviewed alone.

L5 (decisión del dueño, ronda 24): ante el reporte «todo del CLI 5074 debe
guardarse», la verificación dio 0 campos perdidos en seis escenarios (base,
`save_hour` del día, export, import de Excel, merge de bloques y texto no
numérico); el bloque `cli.5074` se guarda entero. El fallo real era de la
ventana: el autosave con debounce de 700 ms no se volcaba al cambiar de día,
navegar o cambiar de estación, y la vista cacheada se recargaba con los datos
del otro día. Arreglado en `735c88e` con `flush_pending()` en las tres vistas y
`_flush_cli_views()` antes de cada cambio de contexto.

L6 (decisión del dueño): el almacenamiento del 5074 queda como está —
**opción A**, dentro del documento del día (`cli.5074`), sin archivo aparte. Un
solo dueño, una sola escritura atómica, versionado y respaldo ya cubiertos. El
test `test_the_5074_block_is_never_cleaned` pinta ese invariante.
