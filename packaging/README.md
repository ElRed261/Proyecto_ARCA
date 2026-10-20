# Empaquetado por OS (F8). Ver PRD §7-F8 y ADR-05.
# Primario: Briefcase. Plan B: PyInstaller. Firmado Win + notarización macOS obligatorios.

## Datos del paquete (assets)

`oms_ui/assets/` viaja **dentro** del paquete: son los fondos por hora
(`assets/hours/<HORA>.webp`, 1920×1080, WebP q82, 569 KB en total).

- **Briefcase**: incluye el paquete Python completo; no hace falta nada extra.
- **PyInstaller**: agregar `--add-data "oms_ui/assets:oms_ui/assets"`
  (en Windows el separador es `;`).
- Si un asset falta, la página cae al gradiente por hora: nunca rompe.
