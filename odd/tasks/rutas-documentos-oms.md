# Rutas de guardado por defecto en Documentos (ronda 15)

Objetivo del dueño: que **exista una ruta por defecto** aunque se pueda
cambiar en la configuración, que viva en **Documentos** y que **dentro esté
seccionada de forma eficiente**.

Estado actual (a corregir): la raíz por defecto es `~/Documents/ARCA` y la
estructura interna es solo `{raíz}/synop` — sin secciones. Además
`oms_core/services/audit.py::default_base_dir()` **duplica** la ruta
hardcodeada (`Path.home()/"Documents"/"ARCA"/"synop"`) en vez de usar
`oms_core.paths`, así que la ruta configurada por el admin no lo afecta.

## Specs

- **S1** Raíz por defecto: `~/Documents/OMS` (siempre `Documents`, con el
  fallback histórico a `HOME`). Debe existir de verdad: al arrancar la app
  la estructura se crea si falta (`mkdir(parents=True, exist_ok=True)`).
- **S2** Secciones internas, eficientes y explícitas bajo esa raíz:
  - `synop/<ESTACION>/<AÑO>/<MES>/` — observaciones sinópticas y CLI
    (la capa `{modulo}` actual, semántica intacta: `DEFAULT_MODULE="synop"`).
  - `resumenes/<ESTACION>/<AÑO>/<MES>/` — resúmenes mensuales.
  - `exportaciones/` — Excel/PDF exportados.
  - `respaldos/` — respaldos de base/JSON.
- **S3** Configurable: la página Maintenance sigue permitiendo fijar la
  raíz (perfil `PathProfile`) con su sonda de escritura honesta; el valor
  por defecto que muestra pasa a ser el nuevo. La cadena de resolución
  `ARCA_BASE_DIR` > perfil > default **no cambia** (contrato del oráculo).
- **S4** Una sola fuente de verdad: `default_base_dir()` (audit) deriva de
  `oms_core.paths`, sin rutas hardcodeadas duplicadas.
- **S5** Idempotencia y seguridad: crear la estructura nunca sobrescribe ni
  borra nada, y una raíz no escribible falla con el mensaje honesto del
  probe, no con un traceback.

## Tasks

| ID | Specs | Archivos | Estado |
|---|---|---|---|
| T1 | S1,S2 | `oms_core/paths.py` (raíz + secciones + `section_dir` + `ensure_directories`) | hecho |
| T2 | S1 | `oms_ui/startup.py` + `run_dev.py` (crear estructura al arrancar) | hecho |
| T3 | S3 | `oms_ui/pages/maintenance.py` (default nuevo + mostrar secciones) | hecho |
| T4 | S4 | `oms_core/services/audit.py` + `oms_ui/main_window.py` (derivar de paths) | hecho |
| T5 | S1-S5 | tests (`tests/test_f1_paths.py` y nuevos) + evidencia | hecho |

## Log

- **L1** (verbatim) «Quisiera también trabajar con las rutas, quiero que
  defoult exista una ruta auque se pueda cambiar en la configuración, que
  sea en Documentos y dentro se seccione de forma eficiente.»

- **L2** Delegación al writer falló dos veces («repository preparation was
  unavailable»): implementado inline, como en las rondas previas del OBS.
- **L3** Ronda 15 implementada: raíz `~/Documents/OMS`, secciones `synop/`,
  `resumenes/`, `exportaciones/`, `respaldos/`, creación al arrancar,
  estructura visible en Maintenance, y `audit.default_base_dir()` derivando
  de `oms_core.paths` (con `resolve_base_dir(conn)` siguiendo el perfil).
  Suite 440 verde; `tests/test_f15_paths_structure.py` fija las reglas.
