# Ola 0 — Bloqueantes de la auditoría Judgment Day

`docs/AUDITORIA_JD.md` congeló 46 hallazgos; seis son bloqueantes. Este documento ejecuta los cinco
que son código. El sexto (API-02, licencia CC BY-NC-SA 4.0) es decisión del dueño y no entra aquí.

Origen: dual review ciego `jd-judge-a` + `jd-judge-b`, verificado por el controlador.

## Specs

**S1 — La conexión nunca queda en transacción implícita (SEG-02).**
`mark_error` ejecuta `INSERT … ON CONFLICT DO NOTHING` y, cuando `cur.rowcount == 0`, lanza
`MarkConflictError("Este campo ya está marcado como error")` sin cerrar la transacción. La conexión
queda abierta y el siguiente `BEGIN IMMEDIATE` falla con
`OperationalError: cannot start a transaction within a transaction`. Efectos observables: después de
un `mark_error` que colisiona, `propose_correction` en la **misma conexión** debe funcionar, y
`conn.in_transaction` debe ser `False` en ambos casos (éxito y conflicto). Los llamadores pueden omitir
el `commit` porque el repositorio ya no les deja deuda.

**S2 — Un día se guarda entero o no se guarda (EFF-02).**
`oms_ui/pages/synoptic.py:1988` recorre las ocho horas llamando `save_hour`, y `save_hour`
(`oms_core/services/synoptic.py:530`) hace `RELEASE f4_save_hour` + `conn.commit()` por hora. El
comentario del llamador dice literalmente
`return  # stop on the first failure (oracle: whole day fails)`, y esa promesa hoy es falsa: un fallo
en una hora posterior deja persistidas las anteriores. Efectos observables: con un dato inválido en
una hora cualquiera, al terminar el guardado **ninguna** hora del día está en `observations` y el
conteo de `document_versions` del día no cambió. Con datos válidos, las ocho horas quedan guardadas.

Nota de alcance: `document_versions` sigue registrando una fila por hora (`synoptic 06Z`, …). Coalescer
esas filas a una por día es ESC-02, no esta tarea; aquí sólo se exige que un día fallido no deje
ninguna fila nueva.

**S3 — Instalación nueva con usuarios reales, sin credencial en el repositorio (SEG-01).**
`auth.seed_admin` (`oms_core/services/auth.py:208`) tiene cero llamadores en producción, y el único
camino que crea un usuario es `run_dev.py:43` con `DEV_PASSWORD` escrito en el repositorio e impreso a
stdout. Efectos observables: al arrancar con una base de datos vacía, la tabla `users` queda con los
cuatro usuarios sembrados y existe `primer_inicio.txt` con permisos `0600`; al arrancar con usuarios
existentes no se toca nada (`seed_admin` devuelve `None`). El repositorio no contiene ninguna
contraseña utilizable.

**S4 — Guardar escribe el documento y encola la sincronización (EFF-01).**
`sync.emit_dual_after_save` sólo se invoca desde `tests/test_f7_sync.py`; `save_hour` y `save_cli`
escriben únicamente en SQLite, así que el árbol `synop/` no recibe ningún documento nuevo y
`sync_pending` queda vacía para siempre, mientras el panel muestra "Sincronización al día". Efectos
observables: después de un `save_day`/`save_hour` exitoso, el JSON del día existe en
`<offline_root>/synop/<station>/<year>/<month>/<station><dd><mm><yyyy>.json`; con raíz online configurada
y copia fallida hay una fila en `sync_pending` con `last_error`; sin raíz online el guardado **no falla**
y no encola nada (no-op honesto, igual que el oráculo).

**S5 — El auditor ve los días guardados por la aplicación (ESC-01).**
El navegador de auditoría (`oms_core/services/audit.py:385`) enumera el árbol en disco y parsea los
JSON del mes, mientras las observaciones nuevas sólo se escriben en SQLite: ningún día posterior a la
migración aparece en la auditoría. Efectos observables: un día guardado por `save_hour` aparece en
`browse_days` del mes correspondiente sin que exista el archivo; un mes que sólo existe en disco
(archivo heredado) sigue apareciendo, así que la migración no se rompe.

## Tasks

| ID | Spec | Route | Estado |
|---|---|---|---|
| T1 | S1 | `oms_core/db/repositories/audit.py` + `tests/test_audit_transaction.py` | hecho · `b86f039` |
| T2 | S2 | `synoptic.save_day` + `save_hour(commit=)` + `oms_ui/pages/synoptic.py` + `tests/test_synoptic_day_transaction.py` | hecho |
| T3 | S3 | `run_dev.py`, `oms_core/services/auth.py`, `tests/test_auth_first_run.py` | hecho |
| T4 | S4 | `synoptic._publicar_en_arbol` + `tests/test_sync_after_save.py` | hecho |
| T5 | S5 | `oms_core/services/audit.py` + tests | pendiente |

Cada tarea: test en rojo primero, arreglo mínimo, verde, y commit propio porque cada una toca un ítem
de riesgo alto (datos, seguridad o integridad).

## Log

**L1** — «Inicia con la Ola 0»

**L2** — Exploración previa a la primera escritura: `mark_error` en `audit.py:88-110`;
`BEGIN IMMEDIATE` en `audit.py:206` (`propose_correction`), `summary.py:804` y `:1024`,
`importer.py:137`; `save_hour` con `RELEASE`/`commit` en `synoptic.py:529-530`; `do_save` en
`oms_ui/pages/synoptic.py:1988`; `seed_admin` en `auth.py:208`; `_SEED_USERS`, `primer_inicio.txt`.

**L3 — T1 (S1) cerrado.** RED real: `sqlite3.OperationalError: cannot start a transaction within a
transaction` al proponer una corrección después de un conflicto de marca. Arreglo: `conn.rollback()`
antes del `raise` en `mark_error`. GREEN: 4 tests nuevos + 78 de `test_a20_audit_report.py`. Commit
`b86f039`.

**L4 — T2 (S2) cerrado.** Se añade `synoptic.save_day()` (una `BEGIN IMMEDIATE` externa alrededor de
las ocho horas, `save_hour(commit=False)` dentro) y `do_save` pasa a usarla. `save_hour` conserva su
semántica de fábrica (`commit=True`) para `observation_picker.py:405`. Dos hallazgos durante la
ejecución: (a) `validate_fecha` espera ISO, así que dos tests pasaban por el motivo equivocado hasta
corregir la fecha a `2025-12-08`; (b) los dobles de `test_f4_ui.py` parcheaban `save_hour` y ahora
apuntan a `save_day`, sin tocar ninguna aserción.

**L5 — Nota de entrega.** La rama `neo-arca` acumula ~30.900 líneas desde `origin/main` (es el peso de
la migración, no de esta ola). Por eso cada tarea de la Ola 0 va en su propio commit: son unidades de
riesgo alto y así el review nativo puede tomarlas por separado. La estrategia de entrega de la rama se
decide al abrir el PR.

**L6 — T3 (S3) cerrado.** `run_dev.py` ya no define `DEV_EMAIL`/`DEV_PASSWORD` ni `ensure_dev_user`;
llama a `auth.seed_admin(conn, DEV_DIR)` y sólo imprime credenciales cuando acaba de sembrar.
`seed_admin` deja `primer_inicio.txt` en `0600`. Un test lee `run_dev.py` y falla si vuelve a aparecer
la contraseña. Suite completa: 785 passed.

**L7 — T4 (S4) cerrado, y el hallazgo era mayor de lo que decía el informe.** `emit_after_save` copia
**desde** el árbol offline; nadie escribía el documento en ese árbol, así que conectar el emisor no
bastaba: había que crear la escritura. Se añade `_publicar_en_arbol()` en `synoptic.py` (escribe
`<offline_root>/synop/<station>/<year>/<month>/<station><dd><mm><yyyy>.json` con reemplazo atómico y
después llama `emit_dual_after_save`), invocada en el nivel más externo de commit: `save_hour` cuando
`commit=True` y `save_day` tras su commit, para no emitir ocho veces por día.

**L8 — Incidente durante T4, y la lección que importa.** El primer test de "sin árbol configurado"
resolvió al `~/Documentos/OMS` real y escribió un día vacío en el archivo del dueño: borrado. Regla
nueva del fixture: `default_documents_root` se monkeypatchea a `tmp_path`, así que **ningún test puede
tocar el archivo real**. Segundo tropiezo del mismo test: el monkeypatch tenía la firma mal
(`default_documents_root(env_map)`) y el `except Exception` de `_publicar_en_arbol` lo tragaba en
silencio, dando tres rojos confusos — el `except` amplio es correcto en producción y peligroso en
test, así que la barrera es el fixture, no el `except`.
