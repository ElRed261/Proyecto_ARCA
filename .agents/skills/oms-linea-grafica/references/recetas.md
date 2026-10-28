# Recetas y defectos ya pagados

Cada receta existe porque el error ya ocurrió en este proyecto. No son ejemplos: son las
trampas concretas.

## 1. Resolver una plantilla con la paleta del tema aplicado

```python
def _qss(plantilla: str) -> str:
    from string import Template
    from oms_ui import theme as _theme
    return Template(plantilla).substitute(_theme.palette_actual())


_HEADER_QSS = "background-color: $acento; color: $sobre_acento; font-weight: 800;"
label.setStyleSheet(_qss(_HEADER_QSS))
```

**Trampa:** `theme.palette()` devuelve la preferencia **guardada**, no la aplicada. Al
cambiar de tema sin guardar (las herramientas de captura lo hacen) todo se resuelve con el
tema equivocado y la página queda mezclada. Usá siempre `palette_actual()`.

## 2. Orden de las operaciones

```python
_qss(_HEADER_QSS.format(color=color))     # correcto: format deja el $rol, _qss resuelve
_HEADER_QSS.format(color=_qss(color))     # roto: el $banda_texto llega crudo
```

**Síntoma:** la regla entera se descarta (`Could not parse stylesheet`) y el widget pierde
fondo **y** color de texto a la vez.

## 3. Envolver hojas, con el criterio correcto

Envolvé si el argumento contiene `$`, termina en `_QSS`, empieza con `f"` o referencia un
constructor (`_pill_qss(...)`, `_filled_qss(...)`). **No** cuentes como envuelta una hoja que
sólo contiene un `_qss()` interno: el resto de sus líneas sigue crudo.

```python
ya = arg.strip().startswith("_qss(")   # correcto
ya = "_qss(" in arg                    # roto: da por buena una hoja a medias
```

## 4. Estados con propiedad

```python
button.setProperty("active", "true" if activo else "false")
theme.repolish(button)      # sin esto, Qt no reevalúa el selector
```

```qss
QPushButton[rail="nav"][active="true"] { background-color: $acento_suave; }
```

**Trampa:** cambiar una propiedad no repinta solo. Y si un widget tenía su manejador de clic
propio y se lo movés a un contenedor, el test que llama `mousePressEvent(None)` sobre el
hijo **no falla: segfaultea**.

## 5. Roles que no sirven para los dos temas

```python
"sobre_acento": "#ffffff",   # claro: el acento es oscuro
"sobre_acento": "#06121c",   # oscuro: el acento es claro
```

Todo par "(fondo con color) + (texto encima)" necesita su propio rol de texto si el color se
invierte entre temas. Nació de dos casos: la tarjeta naranja de Auditoría y los encabezados
de grilla.

## 6. Verificar un color: píxeles, no impresiones

```python
imagen = widget.grab().toImage()
print(imagen.pixelColor(x, y).name())          # el valor real
paleta = theme.palette_actual(); print(paleta["texto"])
```

En una captura reducida, gris claro sobre casi negro parece texto oscuro. Se informaron tres
defectos de contraste que no existían por mirar en vez de medir.

## 7. Gate de la suite

```bash
QT_QPA_PLATFORM=offscreen .venv-gil/bin/python -m pytest -q -m "not slow" > /tmp/s.log 2>&1
echo "EXIT=$?"; grep -c "Could not parse" /tmp/s.log
```

Nunca `pytest ... | tail -3 && git commit`: `tail` devuelve 0 y un **segfault** (exit 139)
se commitea como si estuviera verde.

## 8. Si el mockup no coincide, el que se equivoca es el código

Antes de mostrar un mockup, contrastalo contra el `_build()` real. Si al comparar capturas la
app difiere, no lo maquilles: decí **qué elemento** falta y por qué creíste que estaba bien.
En la fase 4 la regla «no toques el grid» se leyó como «no toques las celdas» y durante cinco
cortes las etiquetas siguieron siendo barras rellenas cuando el mockup mostraba texto.

## 9. Cambiar el acento (o cualquier token global)

1. `oms_ui/theme.py`, en **las dos** paletas.
2. `.venv-gil/bin/python tools/generar_paleta_html.py` → si un par baja del mínimo, lo dice.
3. Suite completa con `EXIT`.
4. Captura de las pantallas afectadas en los dos temas.
5. Commit con el hex y el ratio en el mensaje.
