---
tags: [arca, prd, requisitos, producto, ingenieria-datos]
---

# PRD — Proyecto ARCA (con extensión de Ingeniería de Datos)

> Product Requirements Document
> Autor: Andry Emiliano (ElRed261)
> Fecha: Agosto 2026
> Estado: Propuesta

## 1. Visión

ARCA (Arquitectura de Recursos, Cómputo y Administración) es un sistema de gestión de datos meteorológicos e hidrológicos, actualmente una app de escritorio (Tauri/Rust + React) para registro, cálculo y auditoría de observaciones sinópticas WMO en modo offline.

Este PRD amplía ARCA para convertirlo también en un **data pipeline automatizado**: ingerir observaciones crudas desde Google Drive, transformarlas con el conversor existente (Excel→JSON), y cargarlas a un warehouse consultable en el VPS, habilitando así capacidades de análisis de datos.

## 2. Problema

- Las observaciones originales llegan en Excel desde Google Drive (fuente externa, manual).
- Hoy el usuario convierte y carga a mano: lento, propenso a error, no reproducible.
- Los datos quedan atrapados en la app local; no hay warehouse consultable para análisis.
- No hay flujo automático: cada ciclo de datos requiere acción humana.

## 3. Objetivos

| # | Objetivo | Medible |
|---|----------|---------|
| O1 | Automatizar ingesta desde Google Drive | Descarga cada X tiempo sin acción manual |
| O2 | Integrar el conversor Excel→JSON en el motor (oculto en UI) | Cero pasos manuales de conversión |
| O3 | Crear warehouse en VPS accesible y consultable | Endpoint/UI de consulta funcional |
| O4 | Orquestar el pipeline completo de forma autónoma | Cron/systemd cada X, con reintentos |
| O5 | Base para análisis de datos meteorológicos | Consultas SQL/dashboard sobre histórico |

## 4. Usuarios

- **Observador meteorológico (primario):** registra y audita observaciones en la app.
- **Analista de datos (nuevo):** consulta el warehouse para tendencias, reportes, dashboard.
- **Administrador (tú):** opera el pipeline, supervisa fallos, gestiona el VPS.

## 5. Alcance

### Incluido (MVP)
- Conector Google Drive API (descarga Excel nuevo).
- Módulo de transformación oculto (reusa script actual).
- Carga a warehouse en VPS (PostgreSQL o SQLite ampliada).
- Orquestación periódica con manejo de errores básico.
- Acceso consultable al warehouse (SQL o UI ligera).

### Fuera de alcance (por ahora)
- Machine learning / predicción.
- Multi-estación en tiempo real (streaming).
- App móvil.
- Compartir warehouse públicamente.

## 6. Funcionalidades (épicas)

### F1 — Ingesta automática
- Conectar Google Drive vía API (OAuth service account o token).
- Detectar archivo Excel nuevo/modificado.
- Descargar a carpeta temporal del VPS.
- Reintentar en fallo de red (backoff).

### F2 — Transformación oculta
- Ejecutar el conversor Excel→JSON existente como módulo interno.
- No exponer al usuario la conversión; corre tras la descarga.
- Validar salida contra esquema esperado (campos WMO).

### F3 — Warehouse consultable
- Esquema de tablas: observaciones, estaciones, auditoría.
- Carga idempotente (no duplicar si se reprocesa).
- Acceso por SQL y/o UI web ligera desde VPS.

### F4 — Orquestación
- Cron/systemd timer cada X (configurable: horas/día).
- Log de cada corrida; alerta en fallo (Telegram o log).
- Estado visible (última corrida, próxima).

### F5 — Análisis (habilitador)
- Consultas históricas (por estación, fecha, variable).
- Base para dashboard (Recharts u otro) sobre el warehouse.

## 7. Éxito

- O1–O5 cumplidos y verificables en VPS.
- Tiempo de ingesta a warehouse < X minutos tras descarga.
- Cero duplicados en reproceso.
- Usuario puede consultar datos sin tocar la app de escritorio.

## 8. Riesgos

| Riesgo | Mitigación |
|--------|-----------|
| Google Drive cambia API | Versionar cliente, tests de conexión |
| Excel con formato inesperado | Validación de esquema + log de rechazados |
| VPS sin espacio | Rotación de logs, monitoreo de disco |
| Credenciales expuestas | Secrets en env/Vault, no en repo |

## 9. Fuera de alcance técnico

El detalle de implementación está en el TRD (`Proyecto_ARCA_TRD.md`).
