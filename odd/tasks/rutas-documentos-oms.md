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

## Ronda 16 — ingesta de las observaciones reales

- **L4** (verbatim) «en mi dispositivo hay muchos Json que son de
  observaciones, buscalas y por favor mueve esos Json a la carpeta de
  observaciones, pero antes de moverlos valida si tiene la estructura
  correcta de el Json.»
- **Hallazgo 1**: `default_documents_root()` ignoraba la carpeta localizada.
  En esta máquina `XDG_DOCUMENTS_DIR="$HOME/Documentos"`, así que apuntar a
  `~/Documents` creaba una carpeta paralela. Ahora se resuelve por
  `XDG_DOCUMENTS_DIR` (env) → `user-dirs.dirs` → `~/Documents`, y el `env`
  inyectado llega también al default.
- **Hallazgo 2**: los JSON que la app escribía son `{meta, horas{dict},
  cli3074...}` (`modules/synoptic/storage.rs`), NO `{meta, horarias[lista]}`
  que es lo que consume el importador (formato del pipeline mensual). Los
  archivos se organizan, pero para importarlos hay que aceptar el mapa
  `horas` (pendiente).
- **Nuevo servicio** `oms_core/services/ingest.py` (21 tests): valida el
  documento real y planifica/mueve sin sobrescribir nunca.
- **Ejecución** (contra `~/Documentos/Trabajo-INDOMET/Soporte/ARCA/synop`):
  2554 movidos a `~/Documentos/OMS/synop/<EST>/<AÑO>/<MES>/`; 8 dejados en
  su lugar porque el destino ya tenía una versión MÁS NUEVA del mismo
  documento; 2 rechazados por estructura (fecha 2324 y 31 de febrero).
  Manifiesto: `~/Documentos/OMS/respaldos/movimiento_json_*.log`.
