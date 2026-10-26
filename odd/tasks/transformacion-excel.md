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

## Mapa de la hoja 5074 (verificado en `docs/Estación Central 01032026.xlsm`)

La hoja es un formulario ancho (`A1:BE55`). Lo que quedó **confirmado** leyendo
el archivo real:

| Bloque | Celdas | Contenido real encontrado |
|---|---|---|
| Cabecera del día | `B2`..`B5`, `AU5` | República Dominicana / INDOMET / título / año |
| Temperatura del aire | `B9` máx, `E9` mín | 31 / 23 |
| Humedad relativa | `R9` máx, `T9` mín | 88.5 / 62.3 |
| Presión de estación | `V9` máx, `AB9` mín | 1017.1 / 1014.1 |
| Hora local por grupo | `I13`=2, `N13`=8, `S13`=14, `X13`=20 | 4 grupos de 5 columnas (I-M, N-R, S-W, X-AB) = 06Z, 12Z, 18Z, 00Z |
| Presión por grupo | fila `17` estación, `18` corrección de altitud, `19` NMM | `I17`=1014.2, `I18`=1.6, `I19`=1015.8 (y lo mismo en N, S, X) |
| Temperatura del subsuelo | `AF13:AV15` | 4 grupos (AF, AL, AQ, AT) × 3 filas: 25.2/25.4/29.4/28 … |
| Piche / Tanque C / Evaporígrafo | rótulos `AF18`/`AH18`/`AL18`, unidades fila `19` | sin valores en este archivo (fila de valores vacía) |
| Iniciales del observador | `AM19` | `KMC` |
| Notas | `B22:Y35` | vacío en este archivo |
| Fenómenos (cabecera) | fila `22`: `Z` hora local, `AD` ráfagas, `AH` intensidad, `AI` fenómeno, `AK` inicio, `AM` final, `AP` duración, `AT` iniciales | |
| Fenómenos (sub-cabecera) | fila `24`: `Z` horas, `AB` minutos, `AD` `dd 16-p`, `AF` `ff (m/s)` | |
| Fenómenos (datos) | fila `26` en adelante | `AI26`=R, `AJ26`=A, `AK26`=04:00:00, `AM26`=04:15:00, `AP26`=15 MINUTOS, `AT26`=KMC |

## Preguntas abiertas (bloquean la implementación)

1. **Presión menor de 1000 hPa.** El decodificador del oráculo
   (`decode_pressure_h`) hace `1000 + int(dígitos[1:4]) / 10`, así que `9984`
   daría **1098.4**, no 998.4. La regla que se deduce de tus dos ejemplos es
   otra: `0162` → 1016.2 (prefijo 10) y `9984` → 998.4 (sin prefijo). ¿Cuál
   vale?
2. **Temperatura del subsuelo.** Los 4 grupos de columna (AF, AL, AQ, AT) y las
   3 filas (13, 14, 15): ¿son 4 profundidades × 3 horas (02, 08, 14 locales) y
   falta la hora 20, o son 4 horas con la profundidad en otra fila?
3. **Piche / Tanque C / Evaporígrafo.** Rótulos en la fila 18 y unidades en la
   19, pero la fila de valores está vacía en el archivo de ejemplo. ¿La fila de
   valores es la 20?
4. **Hora local de los fenómenos.** `Z` (horas) y `AB` (minutos) parecen dos
   celdas separadas que hay que unir; en la fila de datos solo aparecieron
   `AK`/`AM` con la hora completa. ¿Se guardan hora y minutos por separado o
   concatenados?
5. **Formato viejo.** En una muestra de 60 de los 4.885 Excel todos resultaron
   `new` (con hoja `3074`) y ninguno `old`. Necesito la ruta de un Excel del
   formato viejo para validar los rangos que me diste (`I17:AA18`,
   `AF13:AW14`, `B20:AW33`, `AP17:AW18`, `AF16:AN18`).

## Acuerdos de la ronda (respuestas del dueño, verificadas)

- **Filas 7 a 9 no se extraen**: son rótulos y encabezados del formulario.
- **Profundidades del subsuelo** = fila 12. Leídas en el formato nuevo:
  `AF12`=5, `AI12`=10, `AL12`=15, `AM12`=20, `AO12`=25, `AQ12`=50, `AT12`=100
  (cm). Son **7 profundidades × 3 filas** (13, 14, 15, alineadas con las horas
  locales 02, 08 y 14). Si una profundidad no tiene valor, queda vacía: en el
  archivo de ejemplo solo traen valor 5, 15, 50 y 100 cm.
- **Piche / Tanque C / Evaporígrafo** = fila **20** (las filas 18 y 19 son
  rótulos y unidades). En el archivo de ejemplo la fila 20 está vacía.
- **Horas**: en el Excel son celdas separadas (horas y minutos); el programa las
  maneja juntas, así que **se concatenan**. Igual criterio para toda hora.
- **Corrección de altura no se guarda**: el programa la carga por estación.
- **Vacío se queda vacío**: nunca se inventa un valor.
- **Presión, formato viejo** (cada valor en 4 celdas): la regla correcta, dada
  por el dueño, es `v = int("9884") / 10 = 988.4` y `int("0165") / 10 = 16.5`,
  que al ser menor de 1000 se lleva a `1016.5`. Es decir:
  `v = int(dígitos) / 10; si v < 1000 → v += 1000`. El decodificador del oráculo
  (`1000 + int(dígitos[1:4]) / 10`) **está mal** para los valores por debajo de
  1000 y no se porta.
- **Formato nuevo**: la presión viene como número normal (`1011.5`, `996.3`);
  no necesita decodificación.
- **Formato viejo sin hoja 5074**: verificado en
  `Datos-Brutos/Central/2023/Diciembre/07122023.xlsm` (hojas `1200Z`, `1500Z`,
  `1800Z`, `2100Z`, `0000Z`, `0003Z`, `0006Z`, `0009Z`, `Guardar TXT`,
  `Instrucciones de llenado`): **no existe la hoja 5074**, la hoja Z ocupa
  `A1:J36` y los datos del día viven ahí con el desfase de filas del oráculo.
  En ese formato `cli["5074"]` se guarda vacío.
- **Pendiente**: el dueño describió un 5074 viejo con cada presión en 4 celdas
  (`I17:AA18`, `AF13:AW14`, `B20:AW33`, `AP17:AW18`, `AF16:AN18`), pero el
  archivo viejo que encontré **no tiene esa hoja**. Falta la ruta de un archivo
  que sí la tenga en versión vieja; si no existe, el 5074 viejo se declara
  inexistente y queda vacío.

## Barrido completo del corpus (3.757 Excel, no una muestra)

Escaneadas las hojas de **todos** los archivos de
`~/Documentos/Trabajo-INDOMET/Datos-Brutos` leyendo `xl/workbook.xml` de cada
paquete (sin abrir el libro), excluyendo la carpeta `Estaciones  - Json`:

| Grupo | Archivos | Qué significa |
|---|---|---|
| Con `3074` + `4074` + `5074` | **2.715** | traen los tres CLI |
| Solo hojas Z, sin CLI | **434** | Central 89 · Higuero 129 · Las Américas 216 |
| Binarios `.xls` (formato viejo de Excel) | **607** | Barahona 1 · Central 132 · Higuero 263 · Las Américas 211 |
| Corrupto / ilegible | 1 | |

Los `.xls` binarios no se pueden leer con openpyxl: hace falta convertirlos o un
lector aparte (`xlrd`), así que quedan **pendientes de decisión**.

### Desde cuándo existen los CLI (primera fecha por estación)

| Estación | Primera observación con CLI |
|---|---|
| Central | 2021-04-15 |
| Arroyo Barril | 2021-10-20 |
| Barahona | 2023-10-17 |
| Higuero | 2024-01-25 |
| Las Américas | 2024-10-17 |
| Santiago | 2025-02 |
| Punta Cana | 2025-04-07 |
| El Catey | 2025-08-26 |
| Cabrera | 2025-08-27 |
| La Romana | 2025-10-23 |
| Monte Cristi | 2026-03-28 |
| Puerto Plata | 2026-04-01 |
| Sabana de la Mar | 2026-07-10 |
| Jimaní | 2026-09-04 |

El uso de los CLI **se generaliza a partir de 2024** (243 archivos en 2024, 760
en 2025 y 1.704 en 2026). Antes de 2024 la mayoría de las observaciones solo
tiene hojas Z.

### Regla acordada

En las observaciones que **no** traen hojas CLI, el documento se escribe igual
con `cli["3074"]`, `cli["4074"]` y `cli["5074"]` presentes y **todos sus valores
vacíos**. No se inventa nada.

### Anomalías detectadas en los nombres de archivo

Tres archivos no siguen el patrón `DDMMYYYY` y hay que resolverlos por contenido
o pidiendo la fecha: `MDSD013052024.xlsm`, `Estacion Central 154042025.xlsm`,
`120072025.xlsx`.

## Metadatos: estación y fecha salen del CONTENIDO, no del nombre

Verificado en archivos reales de cada variante.

### Variantes `new` y `old` — fila 3 de cualquier hoja Z

```
0006Z fila 3: ['AA XX', '10061', '78486.0', '2025-04-10', '']
1200Z fila 3: ['AA XX', '10121', '78486.0', '2025-04-10', '']
2100Z fila 3: ['AA XX', '10211', '78486.0', '2025-04-10', '']
                col 1   col 2    col 3      col 4
```

- **columna 3 = código de estación** (`78486`)
- **columna 4 = fecha ISO** (`2025-04-10`)
- Vale igual en el formato viejo (`1200Z` fila 3 col 3 = `78486`, col 4 =
  `2023-12-07`).

Se lee de una hoja del **día** (06Z o 12Z), nunca de `0000Z`/`0003Z`: esas
pertenecen al día anterior por la regla del cierre a las 06Z
(`Estacion Central 10042025.xlsm` trae `2025-04-09` en `0000Z`/`0003Z` y
`2025-04-10` en `0006Z`/`1200Z`/`2100Z`).

Con esto **no hace falta ningún algoritmo de nombres**: la fecha del documento
es la de adentro. El nombre queda solo como informe.

### Variante `.xls` (hojas `3074 (2)` / `4074 (2)` / `5074 (2)`)

- **No tiene hojas Z**, así que los metadatos salen de la propia hoja `3074 (2)`:
  el código aparece en la **fila 1, columna 18** (`78482`).
- La fecha interna (`fila 33, columna 7`) puede estar **obsoleta**: el archivo
  `Barahona/2025/Diciembre/09122025  DIONYs.xls` declara **2018-09-23**. Parece
  una plantilla reutilizada que no actualizó la celda.
- Por eso, en esta variante la fecha se valida cruzada: si la fecha interna cae
  fuera del mes de la carpeta, manda el nombre del archivo (que sí coincide con
  la secuencia). El conflicto se informa en el reporte de la ventana.

## Regla de admisión (dueño, ronda 3, corregida)

**La condición necesaria son las hojas Z.** Un libro se procesa si trae hojas Z,
tenga o no hojas CLI:

- **Z + CLI** → se procesa con los tres bloques CLI llenos.
- **Z sin CLI** → se procesa igual, con `cli["3074"]`, `cli["4074"]` y
  `cli["5074"]` presentes y **vacíos**.
- **CLI sin Z, o ni Z ni CLI** → **no se procesa**: se informa y se salta.

Barrido de los 3.757 candidatos con calamine (el glob `*.xls*` también atrapa
copias `.pdf` y `.txt` del mismo nombre, que no son Excel):

| Grupo | Archivos | Decisión |
|---|---|---|
| **Hojas Z + CLI** | **2.706** (2.590 `.xlsm` + 116 `.xlsx`) | **se procesan** |
| **Hojas Z sin CLI** | **435** (Central 89 · Higuero 129 · Las Américas 217) | **se procesan, CLI vacíos** |
| Solo hojas CLI | 10 (Las Américas 5 · El Catey 2 · Barahona 1 · Higuero 1 · Puerto Plata 1) | se descartan |
| Ni Z ni CLI | 606 | 605 son **copias `.pdf`/`.txt`** y 1 corrupto: no son Excel |

**Total a procesar: 3.141 observaciones.**

**Corrección al informe anterior**: los «607 `.xls` binarios» no eran Excel
binarios; son copias `.pdf`/`.txt` del mismo nombre que el glob atrapaba. Con
calamine los `.xls` reales se abren sin problema.

### Hojas duplicadas

Hay libros con `3074`, `3074(1)`, `4074`, `4074(1)`, `5074`, `5074(1)` (por
ejemplo `Central/2024/Diciembre/ESTACION CENTRAL 17122024 .xlsm`). Se prefiere
siempre el nombre exacto; si solo existe el sufijado, se usa ese, y el reporte
lo deja anotado. Igual criterio para las hojas Z.

## Reporte: cabeceras reales de la hoja 3074 en las 3.141 observaciones

Barridas las 3.141 con hojas Z; 2.706 traen hoja `3074`. Se leyó la cabecera
real de cada libro (fila 7) y la fila donde aparece la hora 2. **Ningún archivo
está roto**: hay cuatro variantes de cabecera, y el problema era el mapa del
oráculo, que no coincide con ninguna.

| Variante | Archivos | Estaciones | Cabecera | Fila de la hora 2 |
|---|---|---|---|---|
| 1 | **2.380** | todas (Central 342, Higuero 234) | `Estación / NMM / Altímetro / 3 H. TEND / TERMOMETROS / PTO R / T VAP / HR / DIR. / VEL.` | **10** (datos 9-32) |
| 2 | **171** | Higuero | `EST / NMM / ALT / 3 H. TEND / TERMOMETROS / PTO R / T VAP / HR / DIR / VELOC / … / VENTISCA` | 10 — **mismo layout que la 1**, solo cambian los rótulos |
| 3 | **146** | Central 145, Santiago 1 | `HORA LOCAL / PRESIÓN (mbar) - 1000 / TEMPERATURA 0C / HUMEDAD` | **11** — una fila más de cabecera |
| 4 | **9** | Cabrera 8, Higuero 1 | `HORA LOCAL / PRESIÓN (hPa) - 1000 / TEMPERATURA ºC / HUMEDAD / VIENTO / VISIBILIDAD / TIEMPO PRESENTE / FENÓMENOS` | no aparece en las filas 9-33: hay que revisarla aparte |

En **todas**, la hora local está en la **columna A** y las filas de datos son
consecutivas (una por hora), no las 8 filas sueltas que asumía el oráculo.

### Hojas Z: cuatro tamaños

| Filas de la hoja Z | Archivos |
|---|---|
| 37 | 2.312 |
| 31 | 581 |
| 30 | 171 |
| 32 | 77 |

Confirma lo que decía el dueño: con el tiempo se agregaron grupos `9spspsp`
(los carriles pasan de 4 filas a 7). El transformador no debe asumir un alto fijo:
lee los 24 carriles desde `SPSP_CELLS` y deja vacíos los que no existan.
