# Auditoría Judgment Day — OMS / Neo Arca

**Fecha**: 2026-10-27 · **Alcance**: `oms_core/`, `oms_ui/`, `oms_calc/`, `tests/`, `pyproject.toml`, `LICENSE`
**Método**: dual review ciego — `jd-judge-a` y `jd-judge-b`, mismas criterias y mismas skills inyectadas
(`pyside6-engineer`, `refactoring-ui`, `visual-design-foundations`, `maturin-debugger`, `xlsx`), sin
contacto entre sí. El controlador verificó contra el código los hallazgos de máxima severidad antes de
congelar el ledger.

**Ledger**: 61 filas crudas (31 de A + 30 de B) → 14 duplicados corroborados → **46 hallazgos canónicos**.
0 refutados. 1 ubicación corregida por el controlador (ver SEG-02).

**Convención de evidencia**: `D` = determinista (probado leyendo o ejecutando) · `I` = inferencial.

---

## 1. Resumen ejecutivo

El programa está sano en lo que se construyó con disciplina —capa Rust, PRAGMAs de SQLite, coste de
bcrypt, arranque de 140 ms, 776 tests, CI verde— y **falla en las costuras entre piezas**: dónde se llama
una cosa que sólo existe en tests, dónde un `raise` se olvida del `rollback`, dónde el guardado no avisa
al sincronizador.

Seis bloqueantes impiden un piloto honesto:

| # | Qué pasa | Consecuencia |
|---|---|---|
| 1 | El único admin tiene contraseña escrita en el repo y `seed_admin` no lo llama nadie | Instalación nueva: login imposible. Instalación actual: credencial publicada |
| 2 | `emit_dual_after_save` sólo existe en tests | Ningún JSON llega al árbol ni a la cola; la UI dice "Sincronización al día" |
| 3 | `mark_error` hace `raise` sin `rollback` | Correcciones y resúmenes mueren hasta reiniciar la app |
| 4 | `save_hour` commitea por hora | Un día a medias queda guardado y es indetectable después |
| 5 | La auditoría lee del árbol en disco; los días nuevos sólo van a SQLite | El auditor no ve ningún día posterior a la migración |
| 6 | `LICENSE` es CC BY-NC-SA 4.0 (prohíbe uso comercial) y PySide6 es LGPL sin plan | No se puede distribuir ni vender el piloto en los términos actuales |

El eje UI/UX tiene una causa raíz única, no trece problemas sueltos: **no hay capa de tokens**. 89 colores
distintos hardcodeados en 213 llamadas a `setStyleSheet` contra 41 en un QSS de 356 líneas es lo que
produce la sensación de "se ve horrible": cada pantalla se pinta a mano y el mismo control tiene tres
paddings distintos según quién lo escribió. Arreglado eso, la mitad de los hallazgos visuales se caen solos.

---

## 2. Lo que está bien (no tocar)

| Medición | Valor | Por qué importa |
|---|---|---|
| Arranque | core **44 ms** + QApplication **80 ms** + QSS **16 ms** | 140 ms hasta ventana: envidiable para un ERP |
| PRAGMAs | `connection.py:19-21` WAL + `foreign_keys=ON` + `busy_timeout` | Configuración correcta de fábrica |
| bcrypt | coste **12** + hash señuelo para igualar tiempos (`auth.py:39`) | Defensa real contra enumeración de usuarios |
| Frontera Rust | ≈10 µs por hora calculada | El PyO3 está bien dimensionado; la duplicación de E/S es el coste, no la frontera |
| Tests | 776 Python + 54 Rust, `-m "not slow"` en 106 s | Base seria |
| Esquema | v3 congelado con JSON canónico | Activo real: es el contrato de una futura API |
| Cero regresiones de dato | Opción A firmada, cero diferencias de regla | La precisión del dato está protegida |

---

## 3. Eje 1 — Seguridad

| ID | Sev. | Ubicación | Ev. | Hallazgo | Arreglo |
|---|---|---|---|---|---|
| **SEG-01** | BLOCKER | `run_dev.py:43-53` · `auth.py:208` | D | `DEV_PASSWORD` hardcodeado y `seed_admin` con **cero llamadores**: instalación nueva sin login posible; la actual protegida por una credencial publicada en el repo | Llamar `seed_admin` desde el entrypoint real, borrar la credencial dev y apuntar el runner a `OMS_DATA_DIR` |
| **SEG-02** | SEVERE | `audit.py:107` | D | `mark_error` hace `INSERT … ON CONFLICT DO NOTHING` y `raise MarkConflictError` **sin `commit` ni `rollback`**: la conexión queda en transacción implícita y el siguiente `BEGIN IMMEDIATE` lanza `cannot start a transaction within a transaction` | `conn.rollback()` antes del `raise`; guardas `if conn.in_transaction` en los `BEGIN IMMEDIATE` |
| **SEG-03** | SEVERE | `synoptic.py:782` | D | El combo de estaciones se llena con todas para cualquier rol y `save_hour` no revalida alcance: un observador edita y guarda estaciones que nunca visita | Filtrar con `access.scope_for()` y revalidar dentro de `save_hour` |
| **SEG-04** | SEVERE | `closure.py:47` · `cli3074.py:709` | D | El cierre del día se aplica en **un solo** call site (`synoptic.py:1996`); el autoguardado de las hojas CLI entra por `save_cli` sin rol, sin fecha y sin justificación | Mover la puerta de cierre a `save_hour`/`save_cli` con rol y justificación |
| **SEG-05** | WARNING | `audit.py:256` | D | Todas las puertas están escritas `if role is not None: <check>`: omitir el argumento **apaga la autorización** en silencio | `role` obligatorio en los mutadores públicos; API interna aparte |
| **SEG-06** | WARNING | `connection.py:18` | D | La DB se crea con el umask: `-rw-r--r--`, con hashes de todos los usuarios y todo el archivo | Crear con 0600 y el directorio con 0700 |
| **SEG-07** | WARNING | `auth.py:231` | D | `primer_inicio.txt` guarda las 4 contraseñas en claro, sin 0600 y nunca se borra | 0600 + borrar tras el primer cambio de contraseña |
| **SEG-08** | WARNING | `users.py:74` | D | No hay UI de usuarios: `update_user_password` tiene cero llamadores; el archivo de arranque promete un panel que no existe | Tarjeta de usuarios en Seguridad (listar/resetear/rol) |
| **SEG-09** | WARNING | `stations.py:33` | D | `create_station` acepta cualquier `id` y se usa como nombre de carpeta: un id `..` o `a/b` escribe fuera de la raíz | Reusar `synoptic.validate_station` antes del INSERT |
| **SEG-10** | WARNING | `audit_report.py:326` | D | El PDF oficial interpola `row['persona']` y las notas en HTML con f-string sin escapar | `html.escape()` en cada valor |
| **SEG-11** | WARNING | `login_window.py:148` | D | bcrypt coste 12 en el hilo de UI, sin retardo ni bloqueo tras fallos: 250-400 ms de ventana congelada y fuerza bruta local gratis | Worker + retardo exponencial tras N fallos |
| **SEG-12** | SUGGESTION | `closure.py:47` | I | Compara `datetime.now()` (local) con un instante naive construido como UTC−4: fuera de ese huso el cierre se adelanta o atrasa horas | Comparar datetimes con tz explícita |

---

## 4. Eje 2 — Eficiencia

| ID | Sev. | Ubicación | Ev. | Hallazgo | Arreglo |
|---|---|---|---|---|---|
| **EFF-01** | BLOCKER | `sync.py:378` | D | `emit_dual_after_save` / `emit_after_save` / `enqueue` **sólo se llaman desde tests**. `save_hour` y `save_cli` escriben únicamente en SQLite: ningún JSON llega al árbol, ninguna fila a `sync_pending` (la DB real tiene 0) | Llamar `emit_dual_after_save` al final del guardado + test de integración que afirme archivo y fila de cola |
| **EFF-02** | SEVERE | `synoptic.py:530` | D | `save_hour` hace `RELEASE` + `conn.commit()` por hora: el savepoint protege una hora, no el día. Un fallo en 05Z deja 06Z-03Z ya persistidas, con el comentario "whole day fails" mintiendo | Transacción externa única alrededor de las 8 horas |
| **EFF-03** | SEVERE | `summary.py:553` | D | `on_generate` muestra la barra y ejecuta `generate_month` en el mismo slot: Qt no llega a pintarla y la ventana se congela | Worker con señales de progreso |
| **EFF-04** | SEVERE | `transformar.py:179` | D | `convertir_carpeta` (rglob + calamine por archivo + un JSON por archivo) corre en el hilo de UI con un solo `processEvents()`, sin cancelar y con el botón re-entrante | Worker + progreso por archivo + stop flag |
| **EFF-05** | SEVERE | `summary.py:657` | D | Una tarjeta estilizada por entrada del historial, sin modelo ni tope: medido **4,93 s** de construcción y **5,95 s** de refresco con 15 estaciones × 10 años | `QListView` + `QAbstractTableModel` (o paginar de a 50) |
| **EFF-06** | WARNING | `dashboard.py:169` | D | 2 queries por estación y el mes entero deserializado para contar fechas distintas; las 7 páginas se construyen al arranque | `SELECT COUNT(DISTINCT fecha)` + páginas perezosas |
| **EFF-07** | WARNING | `synoptic.py:381` | D | Caché de fotos por tamaño exacto, `clear()` al llegar a 24: un arrastre de ventana alterna borrados con re-decodificaciones de **119 ms**; 92 MB a 1366×700 y ~200 MB a 1920×1080 | Clave por hora con tamaño cuantizado + evicción LRU |
| **EFF-08** | WARNING | `synoptic.py:361` | D | `path.exists()` en cada `paintEvent`, antes de mirar la caché: un `stat` en el camino más caliente del paint | Resolver existencia una vez, cachear `None` |
| **EFF-09** | WARNING | `observations.py:100` | D | `substr(fecha,1,7) = ?` no empuja el rango al índice (`EXPLAIN`: sólo `station_id=?`): a 30 años, cada mes escanea ~87k filas | `fecha >= ? AND fecha < ?` |
| **EFF-10** | SUGGESTION | `synoptic.py:452` | D | Cada `save_hour` lee y parsea el mismo documento **dos veces**; el día completo son 16 lecturas, 16 parseos y 8 fsyncs | Leer el doc una vez por día y pasarlo |
| **EFF-11** | SUGGESTION | `sync.py:127` | D | `_sha256_of_file` usa `read_bytes()`: documento entero en memoria para un hash | `hashlib.file_digest()` |

---

## 5. Eje 3 — UI/UX y diseño

**Causa raíz**: UI-01. Los demás son síntomas o deudas que se pagan más caro mientras no exista la capa de tokens.

| ID | Sev. | Ubicación | Ev. | Hallazgo | Arreglo |
|---|---|---|---|---|---|
| **UI-01** | SEVERE | `theme.qss:5` · `theme.py` | D | Sin capa de tokens: **89 colores distintos** en **213 `setStyleSheet`** contra 41 en el QSS; `theme.py` no expone paleta; el bloque "v2" (`:187`) redefine `QPushButton[primary]` y deja v1 muerto | `PALETTE` en `theme.py` → un `string.Template` de QSS; borrar reglas sombreadas |
| **UI-02** | SEVERE | `theme.qss:5` | D | No hay reglas `:disabled` (sólo 3 en 356 líneas): un input bloqueado se ve idéntico a uno editable (`#1e293b` en ambos) y en el Sinóptico se bloquean celdas en 4 de 8 horas | `QLineEdit/QComboBox/QDateEdit:disabled { background:#f8fafc; color:#94a3b8 }` |
| **UI-03** | WARNING | `theme.qss:200` | D | Dos fallos de contraste: primario deshabilitado **1,85:1** y pestaña activa de Auditoría **2,80:1** (mínimo 4,5:1) | `#7c3aed` sobre `#ede9fe`; pestaña `#c2410c` |
| **UI-04** | WARNING | `theme.qss:77` | D | **1 sola** regla `:focus` en todo el tema y ninguna para `QPushButton`: en una app de Tab-Enter no se ve dónde está el foco (WCAG 2.4.7) | Anillo de foco único desde token |
| **UI-05** | WARNING | `synoptic.py:660` | D | `QPushButton:hover { opacity: 0.95 }`: **Qt no implementa `opacity`**, la declaración se descarta en silencio. El botón Guardar no tiene feedback de hover | Cambiar `background-color` en `:hover` |
| **UI-06** | WARNING | `dashboard.py:47` | D | `abs(hash(code)) % 5`: el hash de `str` está salteado por proceso, así que **el color de cada estación cambia en cada arranque** (verificado: dos corridas dan asignaciones distintas, con colisiones) | `zlib.crc32` o el índice en la lista ordenada |
| **UI-07** | WARNING | `main_window.py:217` | D | El ítem activo del rail se marca **concatenando un string de QSS** en cada navegación, mientras la propiedad `active` que se setea no la usa nadie | `QPushButton[active="true"]` en el QSS + `_repolish` |
| **UI-08** | WARNING | `audit_observation.py:1128` | I | El diálogo de referencia CLI se abre con `resize(1500, 760)`: más ancho que la pantalla de 1366 y más alto que el área útil | Dimensionar desde `availableGeometry()` (0,9×) |
| **UI-09** | WARNING | `theme.qss:38` | D | Escalas ad hoc: paddings 6/7/9/10/14/22 y tipos 13/16/18 sin pasos intermedios: es la razón por la que cada página reinventa sus paddings | Escala de 4 px y de tipos 12/14/16/18/20 en los tokens |
| **UI-10** | WARNING | `maintenance.py:318` | D | El panel de estructura lista `synop/resumenes/exportaciones/respaldos` y **omite `correcciones`**, que el programa sí escribe | Generar la lista desde `paths.SECTIONS` |
| **UI-11** | WARNING | `main_window.py:232` | D | `assigned_station` se lee de `app_config` y no lo escribe nadie: observador y encargado ven "Sin estación asignada" para siempre | Columna en `users` + UI en Seguridad + onboarding |
| **UI-12** | SUGGESTION | `maintenance.py:415` | D | El botón de migración legacy renombra **miles de carpetas** del archivo sin confirmación, sin previsualización y en el hilo de UI | Confirmación con el plan de renombres + worker |
| **UI-13** | SUGGESTION | `login_screen.py:55` | D | Tres implementaciones de login (`login_screen`, `login_window`, `login_dialog`), dos muertas | Borrar las muertas y migrar sus tests |

---

## 6. Eje 4 — Escalamiento

| ID | Sev. | Ubicación | Ev. | Hallazgo | Arreglo |
|---|---|---|---|---|---|
| **ESC-01** | SEVERE | `audit.py:385` | D | El navegador de auditoría enumera el **árbol en disco** y parsea cada JSON del mes, mientras las observaciones nuevas sólo se escriben en SQLite: **ningún día posterior a la migración es visible al auditor** | Navegar desde `summary_logs (kind='diario')`, árbol como respaldo |
| **ESC-02** | SEVERE | `versions.py:19` | D | `document_versions` sin retención ni coalescencia, alimentada por cada autosave de 700 ms y por las 8 horas del día: ya hay **5.172 filas para 2.554 documentos** | Versionar transiciones (cierre/corrección/guardado explícito) |
| **ESC-03** | SEVERE | `paths.py:97` | D | `summaries_dir` y `backups_max_age_days` se validan, se guardan y se ofrecen en la UI, pero **ningún código las lee**; `respaldos/` se crea vacío y los 14,7 MB no tienen respaldo | Implementar escritura y poda, o quitar los controles |
| **ESC-04** | WARNING | `migrations.py:150` | D | Documento-día como blob JSON de **4,79 KB** reescrito entero en cada guardado, sin compresión ni delta (12,2 MB de blobs ya) | Filas para el día vivo; blob sólo al cerrar, comprimido |
| **ESC-05** | WARNING | `connection.py:20` | I | Sólo journal/busy_timeout/foreign_keys: sin `synchronous=NORMAL`, `cache_size` ni `mmap_size`, así que cada autosave paga un fsync | Añadir PRAGMAs y re-medir el autosave |

---

## 7. Eje 5 — API y globalización

| ID | Sev. | Ubicación | Ev. | Hallazgo | Arreglo |
|---|---|---|---|---|---|
| **API-01** | WARNING | `pyproject.toml:17` | D | Con `build-backend=maturin` y sin `python-source`, la wheel contiene **sólo** `oms_calc` — ni `oms_core`, ni `oms_ui`, ni assets; PySide6 es extra opcional y no hay `[project.scripts]` ni lockfile | `python-source="."` + `python-packages` + PySide6 real + entrypoint + lock |
| **API-02** | WARNING | `LICENSE:1` | D | La licencia es **CC BY-NC-SA 4.0**: prohíbe el uso comercial. PySide6 es LGPLv3 y `packaging/README.md` no dice nada del cumplimiento | Elegir licencia de software y escribir el plan LGPL antes del primer instalador |
| **API-03** | SEVERE | `paths.py:218` | D | La autorización vive **sólo en los widgets**: `create_station`, `delete_station`, `save_hour`, `save_cli`, `generate_month` no reciben identidad | Enhebrar sesión/rol por los servicios mutadores |
| **API-04** | WARNING | `sync_thread.py:27` | D | `oms_core` importa PySide6 de forma dura: `import oms_core.services.sync_thread` falla sin Qt instalado | Mover `SyncWorker` a `oms_ui` o a un módulo opcional |
| **API-05** | WARNING | `main_window.py:41` | D | Todas las cadenas son literales en español, sin `tr()` ni catálogo, incluidos los mensajes de error que los tests afirman | Un catálogo `i18n.tr(clave)` con el español como clave |

### Qué haría falta para tener API de verdad

El esquema v3 congelado ya es la mitad del trabajo: es un contrato estable y versionado. Falta lo demás.

1. **Desacoplar el núcleo de Qt** (API-04): hoy `oms_core` no se puede importar en un servidor sin PySide6.
2. **Mover la autorización a los servicios** (API-03, SEG-03, SEG-05): mientras los permisos vivan en
   widgets, una API HTTP tendría que reimplementarlos en un segundo lugar, y eso es garantizar que
   diverjan. Con sesión/rol en el servicio, la UI y la API usan la misma puerta.
3. **Guardado único y transaccional** (EFF-02, EFF-01): una API no puede aceptar un día a medias.
4. **Una sola fuente de verdad** (ESC-01): hoy hay dos almacenes que dicen ser el archivo — árbol y SQLite.
5. **Empaquetado real** (API-01): sin wheel que contenga la app no hay instalación, ni piloto, ni terceros.
6. **Licencia** (API-02): sin resolverlo, todo lo anterior no se puede publicar.
7. **Idioma** (API-05): un tablero multi-estación en el Caribe necesita al menos español e inglés.

Ruta sugerida: `oms_core` headless → API local (FastAPI sobre los mismos servicios) → multi-estación →
web. Cada paso usa el anterior; ninguno exige reescribir el cálculo, que ya está en Rust y es la pieza
más portable del sistema.

---

## 8. Plan por olas

### Ola 0 — antes de cualquier piloto (6 arreglos)

| Orden | ID | Por qué primero | Esfuerzo |
|---|---|---|---|
| 1 | SEG-01 | Sin esto no hay instalación limpia ni seguridad creíble | 1-2 h |
| 2 | SEG-02 | Una línea; desbloquea correcciones y resúmenes | 15 min |
| 3 | EFF-02 | Transacción externa alrededor del loop existente | 1-2 h |
| 4 | EFF-01 | Conecta el guardado con el árbol y la cola | 2-4 h |
| 5 | ESC-01 | El auditor tiene que ver los días nuevos | 2-4 h |
| 6 | API-02 | Decisión de licencia: es del dueño, no del agente | decisión |

### Ola 1 — confianza en el dato (2-3 días)

SEG-03, SEG-04, SEG-05, SEG-06, SEG-07, SEG-08, SEG-09, SEG-10, SEG-12, ESC-03.

### Ola 2 — eficiencia percibida (3-4 días)

EFF-03, EFF-04, EFF-05, EFF-06, EFF-07, EFF-08, EFF-09, EFF-10, EFF-11, ESC-05.

### Ola 3 — sistema de diseño (2-3 días)

1. `docs/DISENO_OMS.md` con tokens (espaciado 4/8/12/16/24/32, tipos 12/14/16/18/20, pesos 400/600/800,
   radios 6/10, cinco estados).
2. UI-01: `PALETTE` + QSS generado; bajar de 213 `setStyleSheet` a un puñado con rol.
3. UI-02, UI-03, UI-04, UI-05, UI-07, UI-09: estados y contraste desde el token.
4. UI-06, UI-08, UI-10, UI-13: los sueltos.

### Ola 4 — camino a API (semanas, con el dueño decidiendo)

API-01, API-03, API-04, API-05, y luego el plan de 7 pasos de la sección 7.

---

## 9. Ledger de origen

| Canónico | Juez A | Juez B | Verificado por el controlador |
|---|---|---|---|
| SEG-01 | A-001, A-003 | B-001 | Sí (grep + `ls -l`) |
| SEG-02 | — | B-004 | Sí (ubicación corregida a `audit.py:107`) |
| SEG-03 | — | B-010 | No (aceptada por el juez) |
| SEG-04 | A-004 | B-022 | Parcial |
| SEG-05 | A-027 | — | No |
| SEG-06 | A-016 | — | Sí |
| SEG-07 | A-017 | B-002 | Sí |
| SEG-08 | — | B-002 | Sí |
| SEG-09 | — | B-019 | No |
| SEG-10 | A-010 | — | Sí |
| SEG-11 | — | B-026 | Sí (coste 12 leído en código) |
| SEG-12 | — | B-022 | No |
| EFF-01 | A-002 | B-011 | Sí (grep) |
| EFF-02 | A-009 | B-003 | Sí |
| EFF-03 | A-007 | B-007 | No |
| EFF-04 | A-008 | B-008 | Sí |
| EFF-05 | — | B-006 | No (medición del juez) |
| EFF-06 | A-015 | B-017, B-020 | Parcial |
| EFF-07 | — | B-009 | No |
| EFF-08 | — | B-024 | No |
| EFF-09 | — | B-018 | No |
| EFF-10 | — | B-023 | Sí |
| EFF-11 | A-029 | — | No |
| UI-01 | A-021 | B-014 | Sí (89/213/41) |
| UI-02 | — | B-013 | Sí (3 reglas) |
| UI-03 | — | B-015 | No |
| UI-04 | A-018 | — | Sí (1 regla) |
| UI-05 | A-019 | — | Sí |
| UI-06 | A-012 | — | Sí (dos procesos) |
| UI-07 | A-020 | B-029 | Sí |
| UI-08 | — | B-016 | No |
| UI-09 | — | B-025 | Sí |
| UI-10 | A-022 | — | No |
| UI-11 | A-026 | B-012 | Sí |
| UI-12 | A-030 | — | No |
| UI-13 | — | B-030 | No |
| ESC-01 | A-014 | — | No |
| ESC-02 | A-011 | — | Sí (5.172 filas) |
| ESC-03 | A-013 | — | Sí (grep) |
| ESC-04 | A-023 | — | Parcial |
| ESC-05 | A-028 | — | No |
| API-01 | A-024 | B-021 | No |
| API-02 | A-025 | — | Sí (LICENSE) |
| API-03 | A-005 | — | Sí |
| API-04 | — | B-027 | No |
| API-05 | A-031 | B-028 | Sí |

**Nota metodológica**: 776 tests verdes no detectaron EFF-01 porque `tests/test_f7_sync.py` ejercita
`emit_after_save` **en aislamiento**. Un test que pruebe el camino real de guardado —archivo escrito y
fila de cola creada después de `save_hour`— es la regla que faltaba, y va con el arreglo.
