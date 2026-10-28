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

**Fuente única: `oms_ui/theme.py`.** Ningún archivo de `oms_ui/` puede escribir un color
literal; lo impone `tests/test_sin_literales.py`. El muestrario navegable es
`docs/diseno/paleta.html`, **generado** desde esa paleta con
`tools/generar_paleta_html.py`: no se edita a mano, así no hay dos verdades.

### 2.1 Criterio, no gusto

El acento es **`#034885`**, el azul que pidió el dueño: un azul profundo y poco saturado,
que no brilla y descansa la vista en jornadas de ocho horas. De ahí se deriva toda la
familia por luminosidad, no por saturación, para que los estados se distingan sin gritar.

Reglas que la paleta respeta y que el generador verifica en cada corrida:

| Tipo de par | Mínimo WCAG 2.2 |
|---|---|
| Texto normal (≤ 18 px) | **4,5:1** |
| Texto grande y elementos de interfaz (bordes, iconos, marcas) | **3:1** |
| Texto sobre el acento | **4,5:1** |

### 2.2 Familia de acento · tema claro

| Rol | Hex | Sobre `superficie` | Uso |
|---|---|---|---|
| `acento` | `#034885` | 9,25:1 | acción primaria, encabezados de grilla |
| `acento_hover` | `#022f57` | 13,58:1 | estado hover del primario |
| `acento_foco` | `#045ba8` | 6,85:1 | anillo de foco |
| `acento_suave` | `#e8eff6` | — | tinte de selección y de pestaña activa |
| `acento_borde` | `#b6cde0` | — | borde de la pestaña activa |
| `acento_texto` | `#02315c` | 13,15:1 | texto de acento sobre el tinte (11,34:1) |
| `acento_fondo` | `#f2f6fa` | — | fondo de bloque destacado |
| `sobre_acento` | `#ffffff` | 9,25:1 sobre `acento` | texto sobre el acento |
| `acento_deshabilitado` | `#9fb6cb` | — | primario deshabilitado |

### 2.3 Familia de acento · tema oscuro

El acento se **aclara** para el fondo oscuro; no se reutiliza el del tema claro.

| Rol | Hex | Sobre `superficie` |
|---|---|---|
| `acento` | `#6fb0e8` | 7,36:1 |
| `acento_hover` | `#94c8f2` | 9,60:1 |
| `acento_foco` | `#8ec4f0` | 9,20:1 |
| `acento_suave` | `#0d2740` | — |
| `acento_borde` | `#1b4a72` | — |
| `acento_texto` | `#a8d3f4` | 10,81:1 |
| `acento_fondo` | `#0a1e30` | — |
| `sobre_acento` | `#06121c` | 8,15:1 sobre `acento` |

**Por qué `sobre_acento` y no `banda_texto`:** en claro el acento es oscuro y su texto va
en blanco; en oscuro el acento es claro y su texto va casi negro. Un solo par de roles no
sirve para los dos temas, y cada vez que se intentó el texto se perdió en uno de los dos.

### 2.4 Neutros

Dos familias, una por tema, con la misma escala de cinco pasos: `texto` (contenido),
`texto_alt` (títulos), `suave`, `suave_alt` (rótulos) y `tenue` (sólo informativo).
`tenue` está calibrado en **4,08:1** en claro y **5,52:1** en oscuro: por debajo de 3:1
no se usa ni para una nota al pie.

### 2.5 Estados y acentos de módulo

`error`, `ok`, `ambar`, `naranja` y `teal` tienen cada uno su familia (base, fuerte, fondo,
borde). Los módulos conservan su identidad —Resumen violeta, 4074 verde, 5074 rojo de
fenómenos— y **no** usan el acento para eso.

## 3. Escalas

Todo tamaño sale de estas escalas. Un valor que no esté acá no se inventa: se elige el
escalón más cercano.

### 3.1 Tipografía

Una sola familia, **Plus Jakarta Sans** empaquetada (400/500/600/700/800), igual en Linux,
Windows y macOS. Las cifras van **siempre** con `tnum` (ver §2.6 de la fase 1): sin él las
columnas no alinean porque la fuente trae cifras proporcionales.

| Rol | px | Peso | Uso |
|---|---|---|---|
| Título de página | 22 | 700 | una vez por pantalla |
| Título de sección | 16 | 800 | cabecera de tarjeta |
| Cuerpo | 13 | 500 | texto corriente |
| Rótulo de campo | 12 | 600 | encima de cada campo |
| Encabezado de grilla | 12 | 800 | cuadro de color, letra sobre acento |
| Dato en tabla | 12 | 500 | cifras |
| Metadato | 11 | 500 | fechas, ayudas |

### 3.2 Espaciado

Escala de 4: **4 · 8 · 12 · 16 · 24 · 32**. Márgenes de pantalla 24; separación entre
tarjetas 16; dentro de una tarjeta 12; entre un rótulo y su campo 4.

### 3.3 Radios

**3** para campos y celdas (cuadradas, no rectangulares), **6** para botones y tarjetas
internas, **12** para tarjetas, **16** para paneles grandes.

### 3.4 Medidas fijas

Riel de navegación 200 expandido / 76 colapsado; tarjeta de login 440; alto de campo 34;
ancho de riel del Sinóptico 284; carriles de fenómenos del CLI 34.

### 3.5 Verificación

`tools/generar_paleta_html.py` publica la tabla de contraste de cada tema y **falla en voz
alta** si un par baja del mínimo. Un color nuevo entra por `theme.py`, se regenera el
muestrario y se mira: si no pasa el contraste, no entra.

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

### 5.6 `PanelGraficas` — la pestaña Gráficas del Resumen

**Esquema de OLD**, que es el que quedó aprobado tras descartar tres variantes propias: el
meteograma de bandas apiladas, las bandas por unidad y los cuatro mockups por variable.
Tres piezas:

1. **Sidebar de variables** (izquierda): seis entradas — Temperatura, Presión Atmosférica,
   Humedad y Rocío, Precipitación, Viento, Nubosidad — con la activa en el acento; al pie,
   `Exportar PDF`.
2. **Tres tarjetas de estadísticas** del grupo activo: máximo, mínimo y promedio del mes,
   cada una con su unidad y el color de su serie.
3. **Una caja de gráfico**: título `GRÁFICO DE <VARIABLE> (<UNIDAD>)`, eje de días 1..31,
   eje izquierdo con su unidad y **eje derecho cuando el grupo mezcla unidades**, y leyenda
   al pie con el punto de color de cada serie.

Series por grupo, conservadas de OLD:

| Grupo | Series | Forma |
|---|---|---|
| Temperatura | Máx · Mín · Media | área + área + línea |
| Presión | NMM máx · NMM mín · NMM media · Estación | cuatro líneas (estación punteada) |
| Humedad y Rocío | HR media · HR máx · HR mín · **Rocío** | área + línea + línea + punteada; rocío en el **eje derecho (°C)** |
| Precipitación | Lluvia diaria | barras |
| Viento | Velocidad · Recorrido | línea + punteada; recorrido en el **eje derecho (km)** |
| Nubosidad | Media · Día · Tarde | área + línea + línea, dominio 0..8 |

Reglas de dibujo:

- **Una unidad por eje.** Cuando el grupo mezcla unidades (rocío en °C dentro de humedad en
  %, recorrido en km junto a velocidad en km/h), la serie distinta va al eje derecho con su
  propia escala. Nunca se comparten escalas de unidades distintas.
- **Ninguna serie se distingue sólo por color** (S13): forma (área, sólida, punteada,
  barra) **y** color **y** eje.
- **Paleta conmutable**: `normal` y `accesible` (Okabe–Ito) desde Configuración →
  Apariencia. Los colores salen de `theme.series_palette()`, nunca literales.
- Relleno **plano con alfa** (26 en área, 180 en barras): sin degradados.
- Los cortes del eje se calculan con números redondos según el rango: un rango chico
  (19–22 °C) no puede repetir la misma etiqueta cinco veces — defecto **L7** del plan.
- Ejes: `tenue` para etiquetas y líneas de guía, `suave_alt` para los títulos de eje.
- Sin tooltips flotantes: los valores del día se leen en la tabla y en el resumen, no
  persiguiendo el mouse.


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
