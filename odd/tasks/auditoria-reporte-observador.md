# Reporte de errores por observador (Auditoría, ronda 25)

El módulo de Auditoría sirve para marcar, corregir y contabilizar los errores de
una observación. El reporte del oráculo cuenta **al auditor que marcó**, y las
tasas no existen. El dueño define que el reporte tiene que contar **al
observador que se equivocó**, con cantidades y tasas, agrupando los errores por
tipo y por grupo del dato, y publicarse en pantalla y en PDF.

## Specs

S1. «Quiero que primero en el Orden en el que aparece en el programa sea justo
    después de Synop.» — El menú queda: Inicio · Sinóptico · **Auditoría** ·
    Resumen · Configuración · Seguridad. Hecho en `f53d685`.

S2. El reporte cuenta «Al observador que hizo la observación»: cada marca se
    atribuye al observador de **su hora** (`nombre_observador`), con
    `meta.observador` como respaldo y «Desconocido» cuando no hay ninguno.

S3. «Cantidad, tasa por observación y por campos»: el reporte muestra, por
    observador, **errores**, **observaciones auditadas**, **tasa por
    observación** (errores ÷ observaciones auditadas) y **campos auditados** con
    su tasa (errores ÷ campos auditados).

S4. Taxonomía: «Tipo + grupo del dato afectado». Los tipos siguen siendo los
    cinco del oráculo —`Sintaxis`, `Cálculo`, `Consistencia`, `Falta de datos`,
    `Otro`— y ahora son una lista cerrada y validada; el **grupo** (presión,
    temperatura, humedad, viento, nubosidad, fenómenos, visibilidad, tiempo
    presente, observador, instrumentales, CLIs) se **deriva** del campo marcado
    con la tabla única de mapeo, nunca se escribe a mano.

S5. Publicación: «Pantalla más PDF» — el reporte se ve en pantalla y se exporta
    un PDF armado por la aplicación (encabezado, período, filtros, tablas y
    totales) con `QPdfWriter`/`QTextDocument` de Qt, sin dependencias nuevas.

S6. Se conserva todo lo del oráculo que el módulo ya implementa: el original
    nunca se reescribe (capa de marcas y correcciones aparte), una marca por
    (estación, fecha, hora, campo) con `uq_error_marks_slot`, quitar la marca
    arrastra sus correcciones, el export escribe una **copia**
    `<EST><DDMMAAAA>_cor.json`, y la marca automática «Falta nombre de
    observador» por «Sistema de Calidad» sigue siendo idempotente.

S7. «Usado para marcar, corregir, y crear una Observación lo más correcta
    posible»: el día auditado tiene que poder darse por **terminado** (hoy
    «Sin auditar» se deduce de *no tener marcas*, así que un día revisado sin
    errores aparece como no auditado y no hay denominador honesto para las
    tasas).

## Tasks

- [ ] T1 (S4) migración: columna `grupo` en `error_marks` + `group_for_field()` derivado de `document_map`
- [ ] T2 (S4) tipos de error cerrados y validados en el servicio y en el diálogo
- [ ] T3 (S2/S3) `get_observer_summary()` con errores, observaciones y campos auditados + tasas; `get_error_report()` con observador y grupo
- [ ] T4 (S7) cierre de auditoría por día (`audit_days`) para el denominador y el badge «Sin auditar» honesto
- [ ] T5 (S2/S3) pantalla del reporte: pestañas «Por observador» / «Detalle» / «Actividad del auditor», filtros y totales
- [ ] T6 (S5) export PDF del reporte
- [ ] T7 (S6) regresión del oráculo: marcar/desmarcar, cascada, export `_cor.json`, marca automática

## Log

L1 (dueño, verbatim): «Ok, pasemos al módulo de Auditoría, Quiero que primero en
el Orden en el que aparece en el programa sea justo después de Synop, Luego
Analiza a detalle el OLD para que entiendas cómo se ve y Cómo funciona el Módulo
de audioría. El fin de este módulo es corregir y contabilizar los errores,
haciendo un reoporte por Observador de la cantidad de errores que posee, para su
posterior publicación y reforzamiento de conocimientos en Observaciones. Por lo
que este módulo será usado para marcar, corregir, y crear una Observación lo más
correcta posible.»

L2 (oráculo, evidencia del mapa): tres pantallas (`/audit` embudo de 4 pasos,
`/audit/observation/:estacion/:fecha` espejo de sólo lectura con dos modales,
`/audit/report` con dos pestañas); auditoría como capa SQLite
(`error_marks`/`corrections`) sobre un JSON que nunca se reescribe; correcciones
aprobadas aplicadas en memoria y exportadas a `correcciones/*_cor.json`; cinco
tipos de error en texto libre más la marca automática «Falta nombre de
observador»; `GROUP BY marcado_por` en el resumen; permisos admin y
control_calidad en Rust; «Sin auditar» deducido de no tener marcas.

L3 (dueño, respuestas): cuenta «Al observador que hizo la observación»; conteo
«Cantidad, tasa por observación y por campos»; taxonomía «Tipo + grupo del dato
afectado»; publicación «Pantalla más PDF».
