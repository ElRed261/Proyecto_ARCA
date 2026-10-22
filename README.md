<p align="center">
  <img src="docs/brand/oms-banner.svg" alt="OMS — Observations Management System" width="100%">
</p>

# OMS — Observations Management System

Sistema de gestión de observaciones meteorológicas para estaciones de superficie,
construido sobre las normas de la OMM (Manual N°306, FM 12 SYNOP) y pensado para
operar **offline-first** en una red de estaciones que luego sincroniza con la
central.

| | |
|---|---|
| **Aplicación** | PySide6 (Qt Widgets), un solo lenguaje de aplicación |
| **Cálculos OMM** | Rust vía PyO3 — fórmulas verificadas contra el oráculo de la estación |
| **Datos** | SQLite en modo WAL, con versionado por documento |
| **Archivo** | Documentos JSON por estación y día, exportables e importables |
| **Plataformas** | Linux, Windows y macOS |

---

## Módulos

| Módulo | Qué resuelve |
|---|---|
| **Sinóptico** | Observación de las ocho horas sinópticas: 24 grupos 9Sp, cálculos psicrométricos y de presión, coherencia con las tablas de cifrado de la OMM |
| **Observaciones CLImatológicas** | CLI 3074 (horario), 4074 (nubes y fenómenos) y 5074 (extremos, suelo, evaporación) |
| **Resumen mensual** | Consolidación del mes, tabla de datos, gráficos y exportación a Excel |
| **Auditoría** | Marcado y corrección de errores por campo, marcado automático de datos obligatorios faltantes, cierre de la revisión y **reporte por observador** con tasas de error, exportable a PDF |
| **Configuración** | Rutas, mantenimiento del archivo, importación y respaldos |
| **Seguridad** | Roles (administrador, control de calidad, encargado, observador), sesiones y administración de estaciones |

---

## Principios de diseño del dato

1. Se guarda **todo lo que el observador digita**; ningún valor calculado se almacena.
2. Cada dato tiene **un solo dueño**: el grupo sinóptico manda y lo demás deriva.
3. El día cierra a las **06Z del día siguiente** (02:00 local); después solo se corrige con justificación auditada.
4. Los JSON del día son la unidad de archivo; la base es la unidad de trabajo.

---

## Documentación

| Documento | Contenido |
|---|---|
| [`docs/ARQUITECTURA_DATOS.md`](docs/ARQUITECTURA_DATOS.md) | Modelo del dato, reglas, cierre del día y rutas por sistema operativo |
| [`docs/CONTRATO_ORACULO.md`](docs/CONTRATO_ORACULO.md) | Reglas verificadas contra el sistema anterior y desviaciones firmadas |
| [`docs/CRONOLOGIA.md`](docs/CRONOLOGIA.md) | Historia completa del proyecto, fase por fase |
| [`docs/CHANGELOG.md`](docs/CHANGELOG.md) | Cambios por versión |
| [`Migración/PLAN_MIGRACION_NEoARCA.md`](Migración/PLAN_MIGRACION_NEoARCA.md) | Plan maestro (PRD) |

---

## Arranque rápido (desarrollo)

El proyecto usa dos entornos virtuales porque el intérprete *free-threaded*
(3.14t) se usa para el núcleo y los cálculos, y el intérprete con GIL para la
interfaz (PySide6 se distribuye con GIL).

```bash
# núcleo y cálculos (venv free-threaded)
python3.14t -m venv .venv
.venv/bin/python -m pip install -e .
(cd oms_calc && ../.venv/bin/python -m maturin develop)

# interfaz (venv con GIL)
python3.14 -m venv .venv-gil
.venv-gil/bin/python -m pip install -e ".[ui]"
(cd oms_calc && ../.venv-gil/bin/python -m maturin build --release -o /tmp/wheels)
uv pip install --python .venv-gil/bin/python --no-deps --force-reinstall /tmp/wheels/*.whl

# ejecutar
.venv-gil/bin/python run_dev.py
```

Pruebas:

```bash
QT_QPA_PLATFORM=offscreen .venv-gil/bin/python -m pytest -q -m "not slow"   # ciclo diario
(cd oms_calc && cargo test)                                                  # cálculos en Rust
```

La suite completa son **más de 760 pruebas** de Python y 54 de Rust.

---

## Estructura

```
oms_core/        núcleo: base, servicios de dominio, rutas, registro
oms_calc/        crate de Rust (PyO3): fórmulas y tablas de la OMM
oms_ui/          interfaz PySide6: pantallas, tema, iconos
docs/            documentación técnica
odd/tasks/       especificaciones de cada feature trabajada
tests/           suite de pruebas
packaging/       empaquetado multiplataforma
```

---

## Licencia

Los términos heredados del proyecto original (CC BY-NC-SA) están en
[`LICENSE`](LICENSE); la estrategia de licenciamiento se revisa antes del
empaquetado final.
