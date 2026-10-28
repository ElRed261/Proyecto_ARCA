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

**S3 — Números en monoespaciada.** Se empaqueta una familia monoespaciada (OFL) y todo
dato numérico —celdas de tabla, campos, valores de tarjeta— la usa con figuras
tabulares; las etiquetas siguen en Jakarta. Verificable: un test que comprueba la familia
asignada por el helper `mono()` y que los archivos de fuente están en
`oms_ui/assets/fonts/`.

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
(área/línea/barra, eje gemelo en viento, dominio 0–8 en nubosidad). Verificable:
`test_f6_summary` y los tests del servicio verdes; una captura por variable y tema.

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
| F1 | **Base de estilo** | S2, S3: roles de datos en `theme.py`, fuente mono empaquetada, helper `mono()`/`estilo()` que devuelve la hoja por rol, retirar los roles transicionales | Bajo | 3 h |
| F2 | **Armazón** | S4: `main_window.py` (rail, activo por propiedad, barra de estado), `theme.qss` con `QPushButton[active]` | Bajo | 4 h |
| F3 | **Login** | S10: `login_window.py`, sacar el emoji, alinear la tarjeta al mockup | Bajo | 2 h |
| F4 | **Sinóptico** | S5: 40 inline fuera, etiquetas de texto, campos de 34 px, riel derecho, fuera `HOUR_THEMES` del fondo, título en tinta | **Alto** | 12 h |
| F5 | **CLI** | S6: 67 inline entre los tres, `OBS.` uniforme, carriles fijos, títulos legibles | Medio | 8 h |
| F6 | **Auditoría** | S7: 35 inline en `audit_observation.py` + las otras tres vistas; cola, historial y estado por campo | **Alto** | 10 h |
| F7 | **Resumen** | S8: tabla, historial con modelo y las seis gráficas con widget propio | **Alto** | 12 h |
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

## Decisiones que necesito antes de F1

1. **Fuente monoespaciada**: empaquetar **JetBrains Mono** (OFL, 4 pesos ≈ 200 KB) o usar la
   mono del sistema. Empaquetarla es lo único que da el mismo ancho de cifra en Windows,
   macOS y Linux; la del sistema cambia en cada máquina y rompe la alineación de columnas.
2. **Gráficas**: widget propio con `QPainter` (cero dependencias, y el código del mockup ya
   lo resuelve) o **QtCharts** (trae ejes, tooltips y leyenda, pero suma superficie LGPL y
   su estilizado es limitado). Recomendación: widget propio.
3. **La escala mixta de OLD**: su gráfico de humedad pone **%** y **°C** (rocío) en el mismo
   eje. Dejarlo tal cual porque es OLD, o mover el rocío a un eje derecho como el recorrido
   del viento. Recomendación: eje derecho, para no invitar a leer una correlación falsa.

## Log

**L1** — «Ahora pasemos a planificar la implementación, Haz un plan detallado de cómo
implementar estas modificaciones.»

**L2** — Mediciones del punto de partida: 213 `setStyleSheet` inline, 27 asserts con hex,
una sola familia tipográfica empaquetada.

**L3** — El trabajo de diseño previo dejó listo: `PALETTE` con 42 roles en cada tema,
`theme.qss` sin literales, los cuatro estados, el conmutador de tema, cero degradados y
cero propiedades que Qt ignora. Las fases de este plan asumen eso como base, no lo repiten.
