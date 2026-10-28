# Implementación del sistema de diseño OMS

Aplicar al programa lo aprobado en los mockups (`Migración/evidencias/DISENO_NUEVO/`),
bajo el contrato de `docs/DISENO_OMS.md`.

Punto de partida real, medido:

- **213 `setStyleSheet` inline** con literales de color: `synoptic.py` 40,
  `audit_observation.py` 35, `cli5074.py` 32, `summary.py` 24, `cli3074.py` 18,
  `cli4074.py` 17, `observation_picker.py` 12, `login_window.py` 9, resto repartido.
- **27 asserts con color literal** en `tests/test_f4_ui.py`, `test_widgets.py`,
  `test_icons.py`, `test_theme_tokens.py` y `test_no_gradients.py`.
- **Una sola familia empaquetada** (Plus Jakarta Sans 400–800): no hay monoespaciada.
- Ya hecho: `PALETTE` claro/oscuro, `theme.qss` tokenizado (0 literales), estados
  `:focus/:disabled/:hover`, conmutador de tema en Configuración, cero degradados y
  cero propiedades que Qt ignora (`tests/test_no_gradients.py`).

## Specs

**S1 — Un solo origen de color.** Ningún `setStyleSheet` en `oms_ui/` contiene un literal
`#hex` ni `rgba()`: todo color sale de `PALETTE`. Verificable con un test de fuente que
recorra `oms_ui/**/*.py` y falle si encuentra un literal, igual que
`tests/test_no_gradients.py`.

**S2 — Paleta completa y sin deuda.** `PALETTE` gana los roles de **datos** (las ocho
series de las gráficas) y **desaparecen** los transicionales `acento_debil`,
`acento_debil_alt` y `violeta_*` que sólo existían para mapear los literales viejos. Un
test comprueba que cada rol usado por `theme.qss` y por el código existe en las dos
paletas.

**S3 — Una sola familia, cifras tabulares.** Se usa **una sola familia empaquetada**
(Plus Jakarta Sans, que ya viaja con la app) para texto y para números: al ir en el
paquete se ve igual en Linux, Windows y macOS. Todo dato numérico —celdas, campos,
valores de tarjeta, ejes— lleva la característica OpenType `tnum` activada, porque la
fuente tiene **cifras proporcionales**: hoy `1111` mide 22,25 px y `0000` mide 43,88 px,
así que ninguna columna numérica puede alinear. Con `tnum` las cinco combinaciones
medidas dan exactamente **36,0 px**. Verificable con `QFontMetricsF`.

**S13 — Accesibilidad al color.** Ninguna serie se distingue **sólo** por color: cada
gráfica suma forma (relleno, línea sólida, punteada, barra) y el gráfico de humedad
separa unidades por eje. Además, Configuración → Apariencia ofrece una **paleta
accesible** (Okabe–Ito, ocho clases distinguibles bajo cualquier tipo de daltonismo:
`#D55E00`, `#0072B2`, `#E69F00`, `#009E73`, `#56B4E9`, `#CC79A7`, `#999999`) aplicable
a las seis gráficas. Verificable: un test que comprueba que cada serie tiene estilo
propio y que las dos paletas existen, y el contraste de cada color de serie contra el
fondo de su tema (≥ 3:1).

**S4 — Armazón.** Rail de 200 px expandido / 76 colapsado con el logo `OMS · Observations`
como acceso a Inicio, seis entradas con monograma, correo y `Salir`; el estado activo se
pinta con la propiedad `active` y una regla del QSS, no concatenando strings. Barra de
estado `Listo` visible. Sin botón `Inicio` en la lista (es el logo, como hoy).

**S5 — Sinóptico.** Conserva **exactamente** la grilla de 16 filas con sus tramos
(`Fecha` ocupa 4 columnas) y el riel derecho con horas, módulos CLI, nubosidad extra y las
dos acciones. Cambia el trazo: etiquetas de texto, campos de 34 px, estados reales, sin
degradado ni fotografía de fondo, título en color de texto. Verificable: los tests de
`test_f4_ui` siguen pasando y una captura por tema.

**S6 — CLI 3074 / 4074 / 5074.** Conservan sus columnas, sus 24 renglones, los carriles de
fenómenos y las tarjetas del 5074. `OBS.` del mismo ancho que una columna de datos y los
carriles a ancho fijo. Título en color de texto. Verificable: `test_f5_ui` y las pruebas
de CLI verdes, más capturas.

**S7 — Auditoría como capa del Sinóptico (A+D+B).** La auditoría de una observación usa la
misma grilla del Sinóptico, en lectura, con el estado por campo (punto y borde), las
acciones `corregir`/`marcar` sobre la celda activa, la **cola de pendientes** con
`Siguiente pendiente` y el **riel de historial** `guardado → propuesto` con quién y cuándo.
El selector de estación/año/mes/día y el reporte conservan su contenido. Verificable:
`test_a20_audit_report.py` y los tests de auditoría verdes, más capturas.

**S8 — Resumen.** Tabla con las **21 columnas comprimidas** (decisión A del dueño) y la
línea de metadatos; historial con `QAbstractTableModel` en vez de una tarjeta por entrada;
pestaña **Gráficas** con el esquema de OLD: sidebar de seis variables, tres tarjetas de
estadísticas y una caja de gráfico por variable, con el widget de dibujo propio
(área/línea/barra, eje gemelo en viento, **eje derecho para el punto de rocío**, dominio
0–8 en nubosidad) y las dos paletas de serie de S13. Verificable:
`test_f6_summary` y los tests del servicio verdes; una captura por variable y tema, más
una de la humedad con la paleta accesible.

**S9 — Transformar y Configuración.** Trazo nuevo y, en Transformar, la conversión en un
worker con progreso por archivo y botón deshabilitado mientras corre (hoy corre en el hilo
de UI). Configuración conserva rutas, estructura, backups, apariencia, sincronización y
migración. Verificable: `test_transform_admin` y `test_f7_ui` verdes.

**S10 — Login.** Tarjeta de 440 px con lockup, subtítulo, tagline, campos, botón y pie.
**Sin emojis**: el candado `🔒` del pie sale del código (hoy se dibuja como un cuadro
porque la fuente no trae emojis). Verificable: `test_f75_design` verde y un test que
prohíbe emojis en las cadenas de UI.

**S11 — Los tests afirman el rol, no el hex.** Los 27 asserts con literal se migran a
`PALETTE["rol"]` conservando la intención (por ejemplo: «el campo marcado usa el color de
error»), nunca se borran. Verificable: `grep -c '#[0-9a-fA-F]{6}' tests/*.py` baja a los
que verifican el propio mapa de paleta.

**S12 — Sin regresiones de dato.** Ninguna fase toca el cálculo, el esquema ni las reglas
R1–R4. La suite completa (`-m "not slow"`, hoy 818) queda verde al cierre de cada fase y
las 54 pruebas de Rust siguen pasando.

## Tasks

Orden por dependencia y por riesgo creciente. Cada fase es un commit (o dos si toca tests
aparte) y termina con capturas nuevas en `Migración/evidencias/DISENO/`.

| ID | Fase | Alcance | Riesgo | Esfuerzo |
|---|---|---|---|---|
| F1 | **Base de estilo** | S2, S3: roles de datos en `theme.py`, helper de fuente con `tnum`, helper `estilo()` que devuelve la hoja por rol, retirar los roles transicionales | Bajo | 3 h |
| F2 | **Armazón** | S4: `main_window.py` (rail, activo por propiedad, barra de estado), `theme.qss` con `QPushButton[active]` | Bajo | 4 h |
| F3 | **Login** | S10: `login_window.py`, sacar el emoji, alinear la tarjeta al mockup | Bajo | 2 h |
| F4 | **Sinóptico** | S5: 40 inline fuera, etiquetas de texto, campos de 34 px, riel derecho, fuera `HOUR_THEMES` del fondo, título en tinta | **Alto** | 12 h |
| F5 | **CLI** | S6: 67 inline entre los tres, `OBS.` uniforme, carriles fijos, títulos legibles | Medio | 8 h |
| F6 | **Auditoría** | S7: 35 inline en `audit_observation.py` + las otras tres vistas; cola, historial y estado por campo | **Alto** | 10 h |
| F7 | **Resumen** | S8, S13: tabla, historial con modelo, las seis gráficas con widget propio, rocío en eje derecho y paleta accesible | **Alto** | 12 h |
| F8 | **Transformar y Configuración** | S9: trazo nuevo y conversion en worker con progreso | Medio | 6 h |
| F9 | **Cierre** | S1, S11: `grep` de literales en cero, 27 asserts migrados, capturas definitivas, borrar `tools/mockup_pantallas.py` | Medio | 3 h |

Total estimado: **~60 h** de trabajo enfocado, en 9 fases.

### Verificación por fase

Todas iguales, sin excepción:

1. Test de la fase en verde (los existentes, migrados cuando afirman literales).
2. Suite completa `QT_QPA_PLATFORM=offscreen .venv-gil/bin/python -m pytest -q -m "not slow"`.
3. `cargo test` si la fase tocó el crate (ninguna debería).
4. Capturas nuevas con `tools/capturar_pantallas.py` en claro y oscuro.
5. `git diff --stat` revisado: si una fase pasa de ~400 líneas útiles, se parte.

### Entrega

La rama `neo-arca` ya acumula ~36.000 líneas contra `origin/main`: no se puede abrir un PR
que lo contenga todo. Tres PRs encadenados, cada uno con la suite verde y sus capturas:

- **PR 1 — Base y armazón**: F1, F2, F3 (tokens, fuente, rail, login).
- **PR 2 — Captura de datos**: F4, F5 (Sinóptico y los tres CLI).
- **PR 3 — Análisis y administración**: F6, F7, F8, F9.

## Decisiones resueltas

**D1 — Tipografía (dueño, L4):** una fuente estándar para todo, igual en los tres
sistemas. Se queda la familia ya empaquetada y se resuelve la alineación numérica con
`tnum`, medido: todas las cifras pasan a 36,0 px. No entra una segunda familia.

**D2 — Gráficas (dueño, L4):** widget propio con `QPainter`. Cero dependencias nuevas; el
código del mockup es la semilla de la implementación y se conservan series, colores y
tipos de OLD.

**D3 — Escala mixta (dueño, L4):** el punto de rocío pasa a **eje derecho** con su unidad,
como el recorrido del viento. Se conservan los códigos de color en las seis gráficas y,
además, se agrega soporte para daltonismo (S13): forma redundante en cada serie y una
paleta accesible conmutalbe.

## Log

**L1** — «Ahora pasemos a planificar la implementación, Haz un plan detallado de cómo
implementar estas modificaciones.»

**L2** — Mediciones del punto de partida: 213 `setStyleSheet` inline, 27 asserts con hex,
una sola familia tipográfica empaquetada.

**L3** — El trabajo de diseño previo dejó listo: `PALETTE` con 42 roles en cada tema,
`theme.qss` sin literales, los cuatro estados, el conmutador de tema, cero degradados y
cero propiedades que Qt ignora. Las fases de este plan asumen eso como base, no lo repiten.

**L4** — Respuesta del dueño a las tres decisiones, textual: «1. Usemos una fuente estandar
para todo, tantpo para Linux, Windows y Mac. 2. Pues trabajemos los charts con Widgets
propios, 3. Movamos elpunto de rocio al eje derecho, pero manteniend códigos de colores en
todas las gráficas, así de forma visual es más probable que s einterprete el gráfico mejor,
De paso agrega soporte para personas daltónicas.»

**L5** — Medición que sostiene D1: la familia empaquetada tiene cifras proporcionales
(`1111` 22,25 px, `0000` 43,88 px) y con `tnum` las cinco combinaciones dan 36,0 px. Sin
`tnum`, ninguna columna numérica puede alinear. El `woff2` sí lo carga Qt 6.12
(`addApplicationFont` devuelve la familia), así que no hace falta cambiar el formato.

**L6** — Soporte de daltonismo (S13) en la app, no sólo en el mockup: la paleta Okabe–Ito
queda como opción de Configuración → Apariencia, junto con la forma redundante de cada
serie. Se descarta distinguir series sólo por color.

**L8** — F1 a F3 cerradas con la suite en verde. Dos lecciones quedan asentadas: el gate
de la suite va con `> log; echo EXIT=$?` porque un `| tail` devolvió 0 con un segfault
(exit 139) y el commit salió igual; y mover un manejador de clic de un widget a su
contenedor no hace fallar el test, lo segfaultea.

**L9** — §5.6 reescrita con el esquema de OLD: sidebar de seis variables, tres tarjetas de
estadísticas y una caja de gráfico por variable, con el rocío en el eje derecho. La sección
anterior describía las bandas por unidad, que el dueño rechazó.

**L7** — Defecto detectado al revisar el render de humedad, a corregir en F7: el eje derecho
repite etiquetas cuando el rango es chico (22, 21, 21, 20, 20) porque los cinco cortes se
redondean al mismo entero. El widget de la app calcula el paso con «números lindos» según
el rango antes de dibujar, y un test lo fija sobre un rango de 19–22 °C.

## Estado y cortes de entrega

El hook de cada commit reclama el corte de entrega: la rama acumula ~37.600 líneas
contra `origin/main`, muy por encima del slice de ~400. El corte no se hace por commits
sueltos sino por los tres PRs de la estrategia de entrega, y hasta que existan esos PRs
todo commit nuevo pertenece al PR 1 si toca tokens, armazón o login, y al PR 2 en
adelante si toca captura de datos.

| Fase | Estado | Commits | Evidencia |
|---|---|---|---|
| F1 Base de estilo | cerrada | `a2c2357` | 8 tests en `tests/test_theme_datos.py` |
| F2 Armazón | cerrada | `04fb474` `74b5196` `77443c4` `b8b7ea5` `c5ea890` `047c49f` | 4 capturas + `tools/capturar_armazon.py` |
| F3 Login | cerrada | `78b119c` | 3 tests + 2 capturas |
| F4 Sinóptico | cerrada | `b34decc` `f8f89c8` `06942c0` `b1ce3b2` `509633f` | 5 cortes · capturas claro/oscuro |
| F5 CLI ×3 | cerrada | `bca2163` `fe0121b` `cc488b1` `902c95a` | 0 literales en los tres · 90 tests CLI |
| F6 Auditoría | cerrada | `de36003` | 0 literales · 113 tests · captura en la herramienta |
| F7…F9 | pendientes | — | — |

Suite al cerrar F3: **834 passed** (`-m "not slow"`), `EXIT=0`.


**L10** — F4, F5 y F6 cerradas. Los tres patrones que aparecieron, en orden de frecuencia:
reemplazar por color en vez de por función; envolver la hoja antes de tokenizarla (o al
revés) y dejar `$rol` crudos que Qt descarta en silencio; y —el más peligroso— **mirar un
PNG reducido y creerle**. En F6 informé tres defectos de contraste que no existían: el
muestreo de píxeles dio `#ffffff`, `#ffbf80` y `#ffffff` donde yo "veía" texto oscuro. El
método que sí decide es leer el píxel o comparar el rol resuelto, no el ojo sobre una
captura escalada.

**L11** — La captura de Auditoría muestra sólo el estado vacío: la herramienta usa un
directorio temporal sin árbol `synop/`, así que no hay estaciones, ni días, ni formulario de
observación. El drill-down y `audit_observation.py` (la superficie más grande de la fase)
quedan tokenizados y con tests, pero **sin verificación visual**. Para cerrarlo la
herramienta tiene que sembrar una estación y un día antes de capturar.
