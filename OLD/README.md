<p align="center">
  <img src="https://img.shields.io/badge/Estado-Beta-blue?style=for-the-badge" alt="Estado" />
  <img src="https://img.shields.io/badge/Version-2.1.0-blue?style=for-the-badge" alt="Versión" />
  <img src="https://img.shields.io/badge/Desktop-Tauri_v2-purple?style=for-the-badge" alt="Desktop" />
  <img src="https://img.shields.io/badge/Backend-Rust-red?style=for-the-badge" alt="Backend" />
  <img src="https://img.shields.io/badge/Frontend-React_Vite-blue?style=for-the-badge" alt="Frontend" />
  <img src="https://img.shields.io/badge/Licenses-lucide_ICS-informational?style=for-the-badge" alt="Iconos" />
</p>

<p align="center">
  <img src="docs/assets/icons/ship.svg" width="72" alt="ARCA" /><br/>
  <em>"Todo lo que entra en el ARCA, sobrevive y prospera."</em>
</p>

# Proyecto ARCA

> **OMS — Observations Management System** · Sistema de Gestión de Observaciones Meteorológicas
>
> Captura conforme al Manual de la OMM (N° 306), correcciones auditadas y control de calidad,
> métricas mensuales, sincronización offline-first entre estaciones y central, y pipeline de
> ingeniería de datos (bronze/silver/gold). Arquitectura de monolito modular.

---

## Sobre el Proyecto

<p align="left">
  <img src="docs/assets/icons/clipboard-list.svg" width="18" alt="" />
  Captura sinóptica conforme al <strong>Manual de la OMM (N° 306)</strong> con cálculo automático
</p>

| Característica | Descripción |
| :--- | :--- |
| **Registro Sinóptico** | Formulario WMO completo con cálculos automáticos nativos (Magnus-Tetens, August-Roche) |
| **Catálogo de Días** | Navegación entre días con guardado automático rápido en JSON estructurado |
| **Códigos SYNOP** | Generación automática de grupos `1snTTT`, `2snTdTdTd`, `4PPPP`, `5aPPP`, `58/59`, `29UUU` |
| **Formulario CLI 3074** | Presión, humedad y viento con cálculos en tiempo real (DIF, CAR automático) |
| **Formulario CLI 4074** | Nubosidad y temperatura con parseo y extracción de grupos `8NsChshs` y dirección de nubes (0CS/56) |
| **Formulario CLI 5074** | Registro de fenómenos significativos y autocompletado diario/horario de presiones y temperaturas extremas |
| **Configuración de Instancia** | Rutas de guardado offline/online configurables por admin; cola de sincronización offline-first |
| **Auditoría y Correcciones** | Trazabilidad completa: errores marcados, correcciones justificadas y export JSON corregido |

---

<img src="docs/assets/icons/sun.svg" width="24" alt="" /> **Módulo Sinóptico — Cálculos Automáticos**

```
┌─────────────────────────────────────────────────────────────┐
│                    CÁLCULOS DE ESTACIÓN                      │
├─────────────────────────────────────────────────────────────┤
│ • Punto de Rocío (Pr)    → Fórmula de Magnus-Tetens          │
│ • Tensión de Vapor (Tv)  → Ecuación de August-Roche          │
│ • Humedad Relativa (Hr)  → (e/es) × 100                      │
│ • Presión NMM            → Pres.Est + Correc.Alt             │
│ • Diferencias P3/P24     → Automático con normalización      │
│ • Visibilidad (VV)       → Desde código IrIxHVV              │
│ • Tiempo Presente (ww)   → Desde 7wwW1W2 o Nddff             │
└─────────────────────────────────────────────────────────────┘
```

### Grupos SYNOP Generados

<img src="docs/assets/icons/file-pen.svg" width="18" alt="" />

| Grupo | Contenido | Descripción |
| :---: | :--- | :--- |
| `1snTTT` | Temperatura seca | Signo + temperatura × 10 |
| `2snTdTdTd` | Punto de rocío | Signo + punto de rocío × 10 |
| `4PPPP` | Presión NMM | Presión al nivel del mar |
| `5aPPP` | Tendencia 3h | Característica + cambio presión |
| `58/59 P24` | Cambio 24h | 58 = subió, 59 = bajó |
| `29UUU` | Humedad | Humedad relativa (%) |
| `8NsChshs` | Nubes | Nubosidad, tipo y altura |

**Reglas de exclusión mutua:** `0CS DL DM DH` excluye `56 DL DM DH` (ambos codifican nubes con
dirección; el sistema desactiva el otro al completar uno).

### Almacenamiento JSON

Ruta configurable desde el módulo **Configuración** (por defecto):

```
Documents/ARCA/{modulo}/{estacion}/{year}/{month}/{station}{DDMMYYYY}.json
```

---

## CLI 3074 — Observaciones de Superficie

<img src="docs/assets/icons/trending-up.svg" width="18" alt="" />

| Campo | Fuente | Cálculo |
| :--- | :--- | :--- |
| **DIF** | `pres_est - p3` | Formato `"00.0"` (truncado) |
| **CAR** | Código WMO 0266 | 0-8 según magnitud y signo |
| **Visibilidad** | `IrIxHVV` → VV | Tabla WMO Code 4377 |
| **Tiempo Presente** | `7wwW1W2` | Comparación `Nddff` si vacío |

---

## CLI 4074 — Nubosidad y Temperatura

<img src="docs/assets/icons/cloud.svg" width="18" alt="" />

Parseo automático de grupos `8NsChshs` y cálculo de alturas:

- **CB** (Cumulonimbus): código `9`
- **CL** (Bajas): códigos `8, 7, 6`
- **CM** (Medias): códigos `5, 4, 3`
- **CH** (Altas): códigos `2, 1, 0`

Además autocompleta dirección de nubes (bajas, medias, altas) desde `56DLDMDH`/`0CSDLDMDH`,
la precipitación (`LL`) y las temperaturas extremas (`Tmax`/`Tmin`).

---

## CLI 5074 — Fenómenos Significativos

<img src="docs/assets/icons/cloud-rain.svg" width="18" alt="" />

Recopila los fenómenos meteorológicos significativos del día y gestiona las observaciones
horarias de presiones, tendencias y correcciones de altitud. Se alimenta del backend Rust para
autocompletar la presión a nivel medio del mar y las temperaturas extremas de la jornada.

---

## Módulos del Sistema

<img src="docs/assets/icons/puzzle.svg" width="18" alt="" />

| Módulo | Estado | Descripción |
| :--- | :---: | :--- |
| Observación Sinóptica | <img src="docs/assets/icons/dot-active.svg" width="10" /> Activo | Formulario WMO con cálculos automáticos (Rust Engine) |
| CLI 3074 | <img src="docs/assets/icons/dot-active.svg" width="10" /> Activo | Presión, humedad y viento con extracción y DIF/CAR |
| CLI 4074 | <img src="docs/assets/icons/dot-active.svg" width="10" /> Activo | Nubosidad y temperatura con parseo de grupos 8, lluvia y suelo |
| CLI 5074 | <img src="docs/assets/icons/dot-active.svg" width="10" /> Activo | Registro de fenómenos significativos y presiones horarias |
| Correcciones y Auditoría | <img src="docs/assets/icons/dot-active.svg" width="10" /> Activo | Marcado de errores, correcciones con justificación y export JSON corregido |
| Resumen Mensual | <img src="docs/assets/icons/dot-active.svg" width="10" /> Activo | Cálculo mensual, historial y gráficos interactivos (Recharts) |
| Configuración & Sync | <img src="docs/assets/icons/dot-active.svg" width="10" /> Activo | Rutas offline/online, carpeta Drive Desktop, cola de sincronización y reintento |

---

## Configuración de Instancia y Sincronización

<img src="docs/assets/icons/settings-2.svg" width="18" alt="" />

El módulo **Configuración** (Dashboard → Configuración & Sync) permite al **administrador**:

1. Definir la **raíz offline** (local) donde viven los JSON de observaciones.
2. Definir la **raíz online**: una carpeta local sincronizada por **Google Drive Desktop**;
   ARCA no habla con la API de Drive, solo escribe archivos en esa carpeta.
3. Probar cada ruta con un **probe real** (escritura/lectura/borrado) antes de guardarla.
4. Ejecutar la **migración one-shot** de carpetas de meses legacy (idempotente).

El guardado es **offline-first**: la observación siempre queda guardada localmente; si la carpeta
online está disponible se emite una copia; si no, la fila queda en la cola `sync_pending` en
SQLite y el sistema reintenta automáticamente (backoff `2^intentos` minutos, tope 60) o con el
botón **Reintentar ahora**. Contenido idéntico no se re-submite (comparación por sha256).

---

## Arquitectura y Rutas de Guardado

<img src="docs/assets/icons/folder-open.svg" width="18" alt="" />

- Raíz con resolución: `ARCA_BASE_DIR` (tests) > configuración del admin > `Documents/ARCA` (default).
- Escrituras atómicas: archivo temporal + `fsync` + `rename` bajo lock por archivo, con
  `schema_version` donde solo la última escritura sobrevive y ninguna vista se interrumpe.
- Backups con retención (dedupe por sha256, edad y cap de bytes) en `app_data/.backups/{estacion}`.
- Los nombres de carpetas de estación se normalizan a minúsculas (compatibilidad Windows/macOS).

---

## Pipeline de Ingeniería de Datos

<img src="docs/assets/icons/database.svg" width="18" alt="" />

`pipeline/` implementa una arquitectura **Medallion** (bronze → silver → gold) en PostgreSQL 16:

- **Ingesta**: Google Drive o carpeta local (`SOURCE_DIR`) con detección de novedad por checksum.
- **Transformación**: núcleo puro Excel→JSON con fixture dorada de prueba.
- **Validación**: rangos físicos WMO con pandera; archivos inválidos → cola `rejected/`.
- **Carga**: UPSERT idempotente por `(station_code, fecha, hora, source_sha256)`.
- **API de consulta**: FastAPI con 5 endpoints (`/health`, `/state`, `/stations/{code}/observations`,
  `/stations/{code}/kpis`, `/rejected`).

Detalle operativo en [`pipeline/README.md`](pipeline/README.md) y el plan en
[`docs/DATA_PIPELINE_PLAN.md`](docs/DATA_PIPELINE_PLAN.md).

---

## Stack Tecnológico

<img src="docs/assets/icons/wrench.svg" width="18" alt="" />

<table>
<tr>
<td width="50%">

### Backend Nativo (Rust & Tauri v2)

| Tecnología | Uso |
|:---|:---|
| `Rust` | Lenguaje de alto rendimiento y seguridad |
| `Tauri v2` | Framework de aplicación de escritorio liviano |
| `SQLite` + `WAL` | Base de datos local transaccional |
| `Bcrypt` | Hashing seguro de credenciales offline |
| `Serde` | Serialización/deserialización de JSON |
| `rusqlite_migration` | Migraciones versionadas |
| `r2d2` | Pool de conexiones SQLite |

</td>
<td width="50%">

### Frontend (React 19+)

| Tecnología | Uso |
|:---|:---|
| `React` | UI declarativa y componentizada |
| `Vite 7` | Servidor de desarrollo y build rápido |
| `Tailwind CSS v4` | Estilos atómicos |
| `React Router v7` | Enrutamiento SPA protegido |
| `Lucide` | Iconografía vectorial (código) |
| `Recharts` | Visualización interactiva de datos |
| `Vitest` + `WebDriverIO` | Tests unitarios y e2e |

</td>
</tr>
</table>

---

## Estructura de Archivos

```
Proyecto_ARCA/
├── frontend/
│   ├── src-tauri/
│   │   ├── capabilities/           # Políticas de seguridad granulares
│   │   └── src/
│   │       ├── infrastructure/     # storage + write_guard + paths_config + sync_queue
│   │       ├── domain/             # contratos de datos y errores (fuente única)
│   │       ├── modules/            # synoptic, cli, auth
│   │       ├── ports/              # traits de repositorios (hexagonal)
│   │       ├── adapters/           # implementaciones SQLite de los ports
│   │       ├── audit/              # auditoría (commands + service + adapters)
│   │       ├── monthly_summary/    # resumen mensual (commands + excel + pipeline)
│   │       ├── json_handler/       # capa de persistencia JSON (CLI + Sinóptico)
│   │       ├── calculations.rs     # motor matemático WMO
│   │       ├── db.rs               # SQLite manager (WAL + migraciones + FKs)
│   │       ├── auth.rs             # autenticación (bcrypt + SessionStore)
│   │       └── lib.rs              # registro de comandos Tauri
│   ├── src/
│   │   ├── shared/                 # componentes comunes (ErrorBoundary, auth utils)
│   │   └── features/
│   │       ├── synoptic/           # módulo sinóptico (SynopticPage + CLI 3074/4074/5074)
│   │       ├── summary/            # resúmenes mensuales con Recharts
│   │       ├── audit/              # auditoría de observaciones
│   │       ├── auth/               # panel de seguridad y gestión de usuarios
│   │       ├── maintenance/        # configuración de rutas + estado de sync
│   │       └── dashboard/          # panel principal
│   └── e2e/                        # smoke e2e con WebDriverIO + tauri-driver
├── pipeline/                       # pipeline Python medallion (bronze/silver/gold)
├── docs/                           # documentación (PRD, TRD, plan, arquitectura, changelog, iconos)
└── .github/                        # CI (ci.yml + pipeline.yml) + dependabot (mensual agrupado)
```

---

## Desarrollo

<img src="docs/assets/icons/rocket.svg" width="18" alt="" />

### Prerrequisitos

```bash
# Rust (rustup), Node.js 18+, Tauri CLI v2
```

### Iniciar en Desarrollo

```bash
# Instalar dependencias
cd frontend && npm install

# Iniciar frontend y backend simultáneamente en Tauri
npm run tauri:dev
```

### Pipeline de datos

```bash
cd pipeline
docker compose up -d           # PostgreSQL 16
cp .env.template .env          # configurar SOURCE_DIR o credenciales de Drive
pip install -e ".[dev]"
alembic upgrade head
python -m arca_pipeline.orchestrate.runner
```

---

## Comandos Tauri Principales

<img src="docs/assets/icons/satellite.svg" width="18" alt="" />

| Comando | Uso |
| :--- | :--- |
| `invoke('save_observation_json', ...)` | Guarda y estructura la observación sinóptica (offline + emisión dual online) |
| `invoke('get_observation', ...)` | Recupera observación y campos calculados por fecha |
| `invoke('get_path_config' / 'set_path_config')` | Configuración central de rutas (admin) |
| `invoke('get_sync_status' / 'retry_pending_sync')` | Estado y reintento de la cola de sincronización |
| `invoke('audit_mark_error' / 'audit_propose_correction')` | Auditoría y correcciones con justificación |
| `invoke('ms_generate_summary', ...)` | Resumen mensual desde los JSON del mes |
| `invoke('login_user', ...)` | Valida credenciales en base de datos local |
| `invoke('calculate_observations', ...)` | Motor meteorológico local |

---

## Autor

<img src="docs/assets/icons/user.svg" width="18" alt="" />

Desarrollado por **Stward** — Ingeniería de Sistemas y Computación.

<p align="center">
  <img src="docs/assets/icons/calendar.svg" width="14" alt="" />
  Última actualización: documentación v2.1.0
</p>
