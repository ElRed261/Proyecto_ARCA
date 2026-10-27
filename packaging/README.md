# Empaquetado por OS (F8). Ver PRD §7-F8 y ADR-05.
# Primario: Briefcase. Plan B: PyInstaller. Firmado Win + notarización macOS obligatorios.

## Datos del paquete (assets)

`oms_ui/assets/` viaja **dentro** del paquete: son los fondos por hora
(`assets/hours/<HORA>.webp`, 1920×1080, WebP q82, 569 KB en total).

- **Briefcase**: incluye el paquete Python completo; no hace falta nada extra.
- **PyInstaller**: agregar `--add-data "oms_ui/assets:oms_ui/assets"`
  (en Windows el separador es `;`).
- Si un asset falta, la página cae al gradiente por hora: nunca rompe.

---

## Cumplimiento de la LGPL de PySide6

El código de OMS es **MIT** (`LICENSE`), pero PySide6 6.12 se distribuye como
`LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0` y lo usamos por la vía **LGPL**. Eso impone
cuatro obligaciones al instalador que salga de este repositorio. Sin las cuatro, el
paquete no se puede distribuir.

| # | Obligación | Cómo se cumple |
|---|---|---|
| 1 | **Enlace dinámico, nunca estático** | Qt viaja como `.so`/`.dll`/`.dylib` separados del binario. Nada de `--onefile` que empaquete las libs dentro del ejecutable. |
| 2 | **El usuario puede reemplazar la LGPL** | Las librerías Qt quedan en un directorio propio y legible del paquete, sin firmar ni verificar su hash, así que se pueden sustituir por otra compilación de la misma versión. |
| 3 | **Aviso de copyright y texto de licencia** | `PySide6` y el texto completo de la LGPL-3.0 se incluyen en `Licencias/` dentro del instalador, junto con la lista de librerías Qt realmente empaquetadas (QtCore, QtGui, QtWidgets, QtCharts cuando entre). |
| 4 | **Sin modificar Qt** | No se parchea ni recompila Qt. Si algún día hay que hacerlo, la LGPL exige publicar esos cambios. |

**Consecuencia práctica de elegir empaquetador:**

- **Briefcase (primario)**: cumple por construcción — instala Python, el paquete y las
  dependencias como archivos normales en disco, con las libs Qt separadas.
- **PyInstaller (plan B)**: hay que construir en modo `--onedir` (nunca `--onefile`),
  dejar `PySide6/Qt/lib/` como directorio real y no aplicar UPX a esas librerías. Si el
  empaquetado las mete dentro del binario, deja de cumplir el punto 1.

**Firma**: firmar el ejecutable propio es compatible con la LGPL; firmar las librerías Qt
también, siempre que el sistema no impida reemplazarlas (en macOS la notarización cubre el
bundle completo, así que la sustitución se hace sobre una copia desbloqueada del bundle y
se documenta así en las notas de instalación).

**Lo que NO se relicencia**: los datos del archivo meteorológico (son del ONAMET), el
manual de claves OMM N°306 que vive en `docs/`, y cualquier manual de terceros. El MIT
cubre el software de este repositorio.
