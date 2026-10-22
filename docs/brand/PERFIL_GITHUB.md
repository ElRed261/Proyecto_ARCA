# Perfil de GitHub — bloque del banner

El perfil (`github.com/ElRed261`) no se puede editar desde este repositorio: hay
que pegar el bloque en el `README.md` del repositorio especial
`ElRed261/ElRed261`. El banner ya está versionado en
[`oms-banner.svg`](oms-banner.svg) y sirve por URL cruda.

## Bloque para pegar

```markdown
<p align="center">
  <img src="https://raw.githubusercontent.com/ElRed261/Proyecto_ARCA/neo-arca/docs/brand/oms-banner.svg" alt="OMS — Observations Management System" width="100%">
</p>

### OMS — Observations Management System

Sistema de gestión de observaciones meteorológicas de superficie, conforme al
Manual N°306 de la OMM (FM 12 SYNOP). PySide6 para la aplicación, Rust para los
cálculos, SQLite para el dato y archivo JSON por estación y día. Operación
offline-first con sincronización a la central, correcciones auditadas y reporte
de errores por observador.

Ingeniería de Sistemas — República Dominicana.
```

## Si preferís la versión ancha para el perfil

El mismo SVG admite un ancho de 100 %; si querés una variante más baja (relación
4:1 en lugar de 4:1 actual ampliada), se genera desde el mismo archivo cambiando
`width="1200" height="300"` en la cabecera del SVG.

## Texto corto para la descripción del repositorio

> OMS — Observations Management System: gestor de observaciones meteorológicas
> offline-first (captura OMM N°306, CLI 3074/4074/5074, resumen mensual,
> auditoría con reporte por observador y sincronización estación a central).
> PySide6 + Rust + SQLite.
