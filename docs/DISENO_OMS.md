# Sistema de diseño OMS

Contrato visual del programa. Toda pantalla nueva o modificada se mide contra este
documento; si la implementación discrepa, discrepa la implementación.

Sustituye por completo al tema anterior (356 líneas de QSS, 213 `setStyleSheet` inline,
89 colores distintos). Referencias visuales: `Migración/evidencias/DISENO_NUEVO/`
(`nav-riel-*.png` es la pantalla de trabajo).

## 0. Regla del dueño (por encima de todo)

> «NADA DE DEGRADADO DE COLORES, eso se ve muy IA y muy genérico, es horrible.»

- **Cero degradados** en el programa: ni `qlineargradient`, ni `QLinearGradient`, ni
  fotografías de fondo tras las tablas. Fondo plano de la paleta.
- **Cero mockups inventados**: las imágenes de referencia se capturan de las páginas
  reales (`tools/capturar_pantallas.py`), para que la organización sea idéntica por
  construcción y no por parecido.
- **La organización actual se conserva exactamente**: Sinóptico es formulario en
  columnas con riel derecho (horas, módulos CLI, acciones); los CLI mantienen su grilla
  de 24 filas. El rediseño cambia el trazo, no el orden de las cosas.
- **Los grids no se tocan** (orden del dueño, textual: «deja todo el Grid como está, al
  igual con el Grid de los CLI»). Eso incluye: el orden de las filas y de los grupos, las
  etiquetas de la clave, sus tramos (`Fecha` ocupa 4 columnas), los 24 renglones de cada
  hoja CLI, sus columnas y los carriles de fenómenos. El rediseño sólo cambia cómo se
  pinta cada celda y todo lo que la rodea (título, riel, bandas, botones, cards).

## 1. Decisiones firmes

| Tema | Decisión |
|---|---|
| Estructura | **Maestro-detalle**: libro del día a la izquierda, editor de la hora activa a la derecha |
| Libro | Scrolly horizontal: las 32 columnas de la clave, con la columna de hora **fija** a la izquierda |
| Hora | **Riel de 8 segmentos**: navega y muestra completitud. Fuera los `QPushButton` por hora |
| Día | **Stepper inline** `‹ 08/12/2025 ›`. El calendario queda como salida secundaria para saltos largos |
| CLI | **La hoja se navega a sí misma**: encabezado de hora fijo, la fila activa sigue al cursor |
| Temas | Claro y oscuro conmutables, **mismos tokens**, un solo QSS generado |
| Modo revisar | El mismo Sinóptico con la lente de problemas (antes de guardar) |

Lo que se conserva del diseño anterior: **la distribución de la tabla** del Sinóptico
(8 horas × los grupos en el orden de la clave OMM) y la grilla de los tres CLI. Nada más.

## 2. Tokens

`oms_ui/theme.py` expone `PALETTE`; el QSS se genera con `string.Template` desde ahí.
**Ningún widget usa un color literal.**

| Rol | Claro | Oscuro | Uso |
|---|---|---|---|
| `fondo` | `#f8fafc` | `#0b1220` | Lienzo de la página |
| `superficie` | `#ffffff` | `#111c2e` | Libro, editor, barras |
| `borde` | `#e2e8f0` | `#243044` | Reglas de 1 px, bordes de campo |
| `texto` | `#0f172a` | `#e2e8f0` | Dato y etiqueta fuerte |
| `suave` | `#64748b` | `#94a3b8` | Etiqueta secundaria |
| `tenue` | `#94a3b8` | `#64748b` | Vacío, raya, pista |
| `acento` | `#0e7490` | `#22d3ee` | **Uno solo** en toda la app |
| `acento_suave` | `#e0f2fe` | `#123241` | Fondo de la hora activa, chip |
| `error` | `#b91c1c` | `#f87171` | Borde y mensaje de error |
| `error_suave` | `#fee2e2` | `#3b1416` | Fondo de la celda con error |
| `ok` | `#15803d` | `#4ade80` | Completitud al 100 % |

Prohibido: acento por módulo, gradientes, `opacity` (Qt no la implementa), `abs(hash())`
para colores, y cualquier `setStyleSheet` que no venga de `PALETTE`.

## 3. Escalas

```
espaciado    4 · 8 · 12 · 16 · 24 · 32        (nada fuera de la escala)
tipografía   11 · 12 · 13 · 14 · 18 · 24      (solo esos saltos)
pesos        400 regular · 600 semibold · 800 bold
números      monoespaciado tabular en TODA celda de dato
filas        28 px libro · 32 px campo del editor · 26 px barra
radios       4 px (controles) · 10 px (contenedores) · nada intermedio
```

## 4. Estados (definidos una sola vez, en el QSS)

| Estado | Claro | Oscuro |
|---|---|---|
| normal | borde `borde`, fondo `superficie` | ídem |
| hover | borde `acento` 1 px, sin cambiar el fondo | borde `acento` |
| foco | anillo de 2 px `acento`, **siempre visible** (WCAG 2.4.7) | ídem |
| deshabilitado | fondo `fondo`, texto `tenue`, borde `borde` punteado | ídem |
| error | borde `error`, fondo `error_suave` en la celda, mensaje debajo | ídem |

Un control deshabilitado **no puede verse igual que uno editable**: es la regla que hoy
no existe y por la que el observador no distingue las celdas bloqueadas.

## 5. Componentes

### 5.1 `BarraContexto` — el único navegador

Una sola barra, misma posición y mismos controles en Sinóptico y en los tres CLI:

```
[78486 · Central ▾]  [‹ 08/12/2025 ›]  [riel 8 horas]  [18/21]  …  [Observador]
```

- Estación: desplegable con todas las del alcance del rol.
- Día: stepper; `←/→` cuando tiene el foco; **1 tecla por día**.
- Riel: ver 5.2.
- Completitud: `n/21` del día, o el conteo del CLI.
- Barra inferior: `Descartar` + `Guardar día · Ctrl+S` con el estado a la izquierda.

### 5.2 `Riel` — navegar y ver el avance

Ocho segmentos clicables: `06Z 09Z 12Z 15Z 18Z 21Z 00Z 03Z`.

- Segmento completo: punto lleno `ok`. Incompleto: punto hueco `borde`.
- Segmento activo: fondo `acento_suave`, texto `acento`, borde `acento`.
- `Alt+1..8` y `↑↓` en el libro hacen exactamente lo mismo.
- Con 24 horas (CLI) el riel no se usa: la hoja navega (5.3).

### 5.3 `Libro` — la grilla del Sinóptico

- Columnas: los grupos de la clave en su orden, encabezado de grupo y unidad.
- **Columna de hora fija** al hacer scroll horizontal (`QHeaderView` con la primera
  sección no desplazable; en `QTableView`/`QTableWidget` se logra congelando la columna).
- Medidor de completitud de 2 px al pie de cada fila + `n/21` a la derecha.
- Clic en una fila: activa esa hora en el editor. `↑↓`: ídem.
- Celda con error: fondo `error_suave`, borde `error`, y el mensaje **debajo del campo**
  en el editor (no en un toast).

### 5.4 `Editor` — la hora activa

- Un bloque por familia: `TEMPERATURA · PRESIÓN Y TENDENCIA · VIENTO Y VISIBILIDAD ·
  CIELO Y NUBOSIDAD · TIEMPO PRESENTE · LLUVIA Y FENÓMENOS`.
- Dos columnas; campo de 32 px; etiqueta arriba en 8 pt/600.
- **Derivado fantasma** a la derecha del campo (`HR 74.2`, `rocío 24.9`, `NMM 1011.4`):
  mono 8 pt, color `tenue`, nunca editable.
- Mensaje de error inmediatamente debajo del campo culpable.
- `Tab` recorre los campos de la familia y pasa a la siguiente.

### 5.5 `InspectorCLI` — grupo decodificado

En los CLI, el detalle a la derecha muestra el grupo de la celda activa:
`82618` → `N=4/8 · dd=260° · ff=18`. Incluye los 10 carriles de fenómenos como chips.

### 5.6 `Meteograma` — la pestaña Gráficas del Resumen

Un meteograma es una **serie temporal meteorológica dibujada como paneles apilados que
comparten el eje de tiempo**: la misma fecha cae en la misma vertical en todos. Referencia
canónica: el meteograma de MetPy (Unidata), que apila viento, temperatura con rocío,
humedad relativa y presión.

El Resumen Mensual son datos **diarios** (1..31), así que cada panel es una serie de 31
puntos con un solo eje de días al pie.

| Fila | Dibujo | Variables del Resumen |
|---|---|---|
| Temperatura (°C) | banda de máx/mín + línea de la media | Mayor temperatura máxima · Menor temperatura minima · Media temperatura |
| Humedad (%) | banda máx/mín + línea de la media | Humedad maxima · Humedad minima · Humedad media |
| Presión NMM (hPa) | banda máx/mín + línea de la media; la de estación punteada | MAxima/Minima/Media presión nivel medio del mar · Media presion en la estación |
| Viento (m/s) · dirección | barras de la media, puntos del máximo diario y **flechas en franja propia arriba** | Velocidad media · Velocidad máxima y direccion · Dirección del viento |
| Lluvia (mm) | barras | Lluvia |

Reglas:

- **Nada de degradados.** Los rellenos van planos con alfa sobre el color del rol (38/255
  en las bandas, 150/255 en las barras).
- La etiqueta de cada fila va a la izquierda, en `suave` 9 px; la rejilla horizontal, en
  `borde` punteado.
- **Las flechas de dirección nunca van al pie del panel**: las tapan las barras. Van en su
  propia franja, arriba.
- Fuera de esta primera versión, por decisión del dueño: nubosidad día/noche/media, punto
  de rocío y tensión de vapor. Entran después como líneas o banda fina sin cambiar el panel set.

## 6. Reglas por pantalla

| Pantalla | Regla |
|---|---|
| **Sinóptico** | D2 + riel + stepper. Modo «Revisar» conmuta el maestro por la tabla de problemas |
| **CLI 3074 / 4074 / 5074** | Grilla única a pantalla completa, encabezado de hora fijo, fila activa resaltada, inspector de grupo a la derecha |
| **Resumen** | Tabla, no tarjetas. Historial con modelo (`QAbstractTableModel`), nunca una tarjeta por entrada |
| **Auditoría** | Tabla de días con las dos fuentes (`summary_logs` + disco); estados de marca en `error`/`ok` |
| **Transformar** | Reporte como tabla con chips de resultado; nunca bloquear la UI (worker) |
| **Mantenimiento** | Formulario de una columna, secciones por `paths.SECTIONS` (incluye `correcciones`) |
| **Login** | Una tarjeta centrada, 380 px, sin fondo animado |

## 7. Mapa de teclado

| Atajo | Acción |
|---|---|
| `Ctrl+S` | Guardar día |
| `Alt+1..8` | Ir a la hora N |
| `↑ ↓` | Hora anterior / siguiente (con el libro enfocado) |
| `Tab` / `Shift+Tab` | Campo siguiente / anterior |
| `Ctrl+←` / `Ctrl+→` | Día anterior / siguiente |
| `Ctrl+Home` | Volver a hoy |
| `F1` | Ayuda de la clave en el campo activo |

## 8. Anti-reglas (lo que ya no se hace)

0. **Degradados**: ningún `qlineargradient`/`QLinearGradient` y ninguna imagen de fondo
   en una pantalla de trabajo. El cielo por hora se veía «muy IA» y competía con el dato.
1. `setStyleSheet` inline con literales de color → **todo viene de `PALETTE`**.
2. `opacity` en QSS: Qt la descarta en silencio.
3. Colores derivados de `hash()`: cambian en cada arranque.
4. Una tarjeta por elemento de una lista: modelo + vista.
5. Marcar el ítem activo concatenando un string al stylesheet: propiedad + regla QSS.
6. Bloques de familia con padding distinto por pantalla: escala única.
7. Estado seleccionado sin contraste ≥ 4.5:1.
8. Trabajo de disco o cálculo pesado en el hilo de UI.

## 9. Plan de implementación

| Fase | Alcance | Riesgo | Verificación |
|---|---|---|---|
| **1. Tokens** | `PALETTE` en `theme.py`, QSS generado por `Template`, conmutador claro/oscuro en Configuración | Bajo: no cambia ninguna pantalla, sólo colores y escala | Las capturas actuales se regeneran; ningún test de UI debe cambiar de expectativa |
| **2. Estados** | `:focus`, `:disabled`, `:hover`, `:error` en el QSS único; borrar los 213 inline | Medio: puede destapar widgets que dependían de su hoja propia | Test que verifique un `QLineEdit` deshabilitado con texto `tenue` |
| **3. BarraContexto + Riel** | Componente compartido; sustituye botones de hora y el modal de fecha en Sinóptico | Medio-alto: toca navegación con atajos ya probados | Los tests de `Alt+1..8` y del picker siguen verdes o se migran con equivalencia |
| **4. Libro con scroll horizontal** | Columna de hora fija, 32 columnas, medidor por fila | Alto: es el widget más grande (2.187 líneas) | Suite `test_f4_ui` completa + captura |
| **5. Editor por familias** | Reagrupar los 32 campos, derivados fantasma, error inline | Medio | `test_f4_ui` + captura |
| **6. CLI** | Encabezado fijo, fila activa, inspector de grupo | Medio | `test_f5_ui` / CLI |
| **7. Resto de pantallas** | Resumen con modelo, Auditoría, Transformar, Login | Medio | Capturas + tests propios |
| **8. Limpieza** | Borrar `theme.qss` viejo, el fondo por hora y los iconos no usados | Bajo | `grep` de literales de color en cero |

Cada fase es un commit propio en `neo-arca`; las fases 3-4 no se mezclan porque son
las que más revisión necesitan.

## 10. Referencias

- Capturas de las páginas reales: `tools/capturar_pantallas.py` →
  `Migración/evidencias/DISENO_NUEVO/pantalla-*.png` (Sinóptico + los tres CLI, en ambos temas)
- `fase1-estados-claro.png` · `fase1-estados-oscuro.png` — estados de los controles
- Los mockups inventados (D1-D4, navegación) se borraron: no coincidían con la
  organización real y confundían más de lo que ayudaban.
- Auditoría que origina estos cambios: `docs/AUDITORIA_JD.md` (UI-01 … UI-13)
