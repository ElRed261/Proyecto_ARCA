# 🚢 Proyecto ARCA

> **Arquitectura de Recursos, Cómputo y Administración**

<p align="center">
<img src="https://img.shields.io/badge/Estado-Beta-blue?style=for-the-badge" alt="Status"/>
<img src="https://img.shields.io/badge/Version-2.0.0-blue?style=for-the-badge" alt="Version"/>
<img src="https://img.shields.io/badge/Desktop-Tauri_v2-purple?style=for-the-badge" alt="Desktop"/>
<img src="https://img.shields.io/badge/Backend-Rust-red?style=for-the-badge" alt="Backend"/>
<img src="https://img.shields.io/badge/Frontend-React_Vite-blue?style=for-the-badge" alt="Frontend"/>
</p>

---

## 📋 Sobre el Proyecto

**Proyecto ARCA** es un sistema especializado para la **gestión de datos meteorológicos e hidrológicos**, diseñado bajo una arquitectura de **Monolito Modular**. Su objetivo es centralizar la captura, procesamiento, auditoría y reporte de observaciones climáticas de estaciones meteorológicas de manera local y offline.

### ✨ Características Principales

| Característica | Descripción |
| :--- | :--- |
| 📊 **Registro Sinóptico** | Formulario WMO completo con cálculos automáticos nativos (Magnus-Tetens, August-Roche) |
| 📁 **Catálogo de Días** | Navegación entre días con guardado automático rápido en JSON estructurado |
| 🔄 **Códigos SYNOP** | Generación automática de grupos 1snTTT, 2snTdTdTd, 4PPPP, 5aPPP, 58/59, 29UUU |
| 📈 **Formulario CLI 3074** | Presión, humedad y viento con cálculos en tiempo real (DIF, CAR automático) |
| ☁️ **Formulario CLI 4074** | Nubosidad y temperatura con parseo y extracción de grupos 8NsChshs y dirección de nubes (0CS/56) |
| 🌧️ **Formulario CLI 5074** | Registro de fenómenos significativos y autocompletado diario/horario de presiones y temperaturas extremas |
| 🔒 **Seguridad y Auth Offline** | Base de datos SQLite local con WAL habilitado y hashing bcrypt para autenticación offline |
| 🔍 **Auditoría** | Trazabilidad y logs de auditoría para la corrección de datos históricos |

---

## 🌤️ Módulo Sinóptico

### 🧮 Cálculos Automáticos

El sistema realiza automáticamente los siguientes cálculos meteorológicos:

```
┌─────────────────────────────────────────────────────────────┐
│                    CÁLCULOS DE ESTACIÓN                      │
├─────────────────────────────────────────────────────────────┤
│ 📌 Punto de Rocío (Pr)    → Fórmula de Magnus-Tetens        │
│ 📌 Tensión de Vapor (Tv)  → Ecuación de August-Roche        │
│ 📌 Humedad Relativa (Hr)  → (e/es) × 100                    │
│ 📌 Presión NMM           → Pres.Est + Correc.Alt            │
│ 📌 Diferencias P3/P24    → Automático con normalización     │
│ 📌 Visibilidad (VV)      → Desde código IrIxHVV             │
│ 📌 Tiempo Presente (ww)  → Desde 7wwW1W2 o Nddff            │
└─────────────────────────────────────────────────────────────┘
```

### 📝 Grupos SYNOP Generados

| Grupo | Contenido | Descripción |
| :---: | :--- | :--- |
| `1snTTT` | Temperatura seca | Signo + temperatura × 10 |
| `2snTdTdTd` | Punto de rocío | Signo + punto de rocío × 10 |
| `4PPPP` | Presión NMM | Presión al nivel del mar |
| `5aPPP` | Tendencia 3h | Característica + cambio presión |
| `58/59 P24` | Cambio 24h | 58=subió, 59=bajó |
| `29UUU` | Humedad | Humedad relativa (%) |
| `8NsChshs` | Nubes | Nubosidad, tipo y altura |

### 🔄 Reglas de Exclusión Mutua

| Grupo | Excluye | Motivo |
| :---: | :---: | :--- |
| `0CS DL DM DH` | `56 DL DM DH` | Ambos codifican nubes con dirección. El sistema desactiva el otro al completar uno. |

### 📁 Almacenamiento JSON

Los datos se guardan en estructura jerárquica:
```
Documents/ARCA/{modulo}/{year}/{month}/{station_code}{DDMMYYYY}.json
```

Ejemplos:
- Sinóptico: `Documents/ARCA/synoptic/2026/04/7846015042026.json`
- CLI 3074: `Documents/ARCA/cli3074/2026/04/78460_2026-04-15_cli3074.json`
- CLI 4074: `Documents/ARCA/cli4074/2026/04/78460_2026-04-15_cli4074.json`
- CLI 5074: `Documents/ARCA/cli5074/2026/04/78460_2026-04-15_cli5074.json`

---

## 📈 CLI 3074 - Observaciones de Superficie

### 🎯 Campos Automáticos

| Campo | Fuente | Cálculo |
| :--- | :--- | :--- |
| **DIF** | pres_est - p3 | Formato "00.0" (truncado) |
| **CAR** | Código WMO 0266 | 0-8 según magnitud y signo |
| **Visibilidad** | IrIxHVV → VV | Tabla WMO Code 4377 |
| **Tiempo Presente** | 7wwW1W2 | Comparación Nddff si vacío |

---

## ☁️ CLI 4074 - Nubosidad y Temperatura

### 🎯 Parseo de Grupos 8 y Dirección

El sistema parsea automáticamente los grupos `8NsChshs` y calcula alturas:
- CB (Cumulonimbus): Código `9`
- CL (Bajas): Códigos `8, 7, 6`
- CM (Medias): Códigos `5, 4, 3`
- CH (Altas): Códigos `2, 1, 0`

Adicionalmente, se autocompleta la dirección de las nubes (bajas, medias, altas) desde los grupos `56DLDMDH` o `0CSDLDMDH`, la precipitación (`LL`) y las temperaturas extremas (`Tmax`/`Tmin`).

---

## 🌧️ CLI 5074 - Fenómenos Significativos

Este módulo recopila los fenómenos meteorológicos significativos del día y gestiona las observaciones horarias de presiones, tendencias, y correcciones de altitud. Se alimenta del backend Rust para autocompletar la presión a nivel medio del mar y las temperaturas extremas de la jornada.

---

## 🧩 Módulos del Sistema

| Módulo | Estado | Descripción |
| :--- | :---: | :--- |
| **🌤️ Observación Sinóptica** | 🟢 Activo | Formulario WMO con cálculos automáticos (Rust Engine) |
| **🔧 CLI 3074** | 🟢 Activo | Presión, humedad y viento con extracción y DIF/CAR |
| **☁️ CLI 4074** | 🟢 Activo | Nubosidad y temperatura con parseo de grupos 8, lluvia y suelo |
| **🌧️ CLI 5074** | 🟢 Activo | Registro de fenómenos significativos y presiones horarias |
| **🔍 Correcciones y Auditoría** | 🟢 Activo | Registro local y auditoría de eventos de modificaciones |
| **📊 Resumen Mensual** | 🟢 Activo | Cálculo mensual, historial y visualización gráfica interactiva (Recharts) de variables meteorológicas |

---

## 🛠️ Stack Tecnológico

<table>
<tr>
<td width="50%">

### 🧠 Backend Nativo (Rust & Tauri v2)

| Tecnología | Uso |
|:---|:---|
| `Rust` | Lenguaje de programación de alto rendimiento y seguridad |
| `Tauri v2` | Framework para aplicación de escritorio nativa liviana |
| `SQLite` | Base de datos local transaccional con modo WAL |
| `Bcrypt` | Hashing seguro de credenciales de usuario offline |
| `Serde` | Serialización/Deserialización ultrarrápida de JSON |

</td>
<td width="50%">

### 💻 Frontend (React 19+)

| Tecnología | Uso |
|:---|:---|
| `React` | Interfaz de usuario declarativa y componentizada |
| `Vite 7` | Servidor de desarrollo y build tool rápido |
| `Tailwind CSS v4` | Estilos atómicos y modernos |
| `React Router v7` | Enrutamiento SPA protegido |
| `Lucide React` | Iconografía vectorizada |
| `Recharts` | Visualización interactiva de datos y gráficos |

</td>
</tr>
</table>

---

## 📂 Estructura de Archivos

```
Proyecto_ARCA/
├── frontend/
│   ├── src-tauri/
│   │   ├── capabilities/           # 🔒 Políticas de seguridad granulares
│   │   └── src/
│   │       ├── adapters/           # 🔌 Adaptadores (SqliteAuditRepository, SqliteUserRepository)
│   │       ├── ports/              # 🔌 Traits de repositorios (hexagonal ports)
│   │       ├── infrastructure/     # 🔌 Error handling (AppError con thiserror)
│   │       ├── repositories/       # 🔌 Station repository + shared domain types
│   │       ├── audit/              # 🔍 Auditoría (commands + service + adapters)
│   │       ├── monthly_summary/    # 📊 Resumen mensual (commands + excel + pipeline)
│   │       ├── json_handler/       # 🚀 Persistencia JSON (CLI + Synoptic)
│   │       ├── calculations.rs     # 🚀 Motor matemático WMO
│   │       ├── db.rs               # 🚀 SQLite manager (WAL + migraciones + FKs)
│   │       ├── auth.rs             # 🚀 Autenticación (bcrypt + SessionStore)
│   │       ├── app_config.rs       # 🚀 Configuración de la app
│   │       └── lib.rs              # 🚀 Registro de comandos Tauri
│   │
│   └── src/
│       ├── shared/                 # 🧩 Componentes comunes (ErrorBoundary, StationHeader, auth utils)
│       └── features/
│           ├── synoptic/           # 🌤️ Módulo sinóptico (SynopticPage + CLI 3074/4074/5074)
│           ├── summary/            # 📊 Resúmenes mensuales con Recharts
│           ├── audit/              # 🔍 Auditoría de observaciones
│           ├── auth/               # 🔒 Panel de seguridad y gestión de usuarios
│           └── dashboard/          # 📋 Panel principal
│
├── .github/workflows/ci.yml        # 🔧 CI (lint + tests + clippy + build)
├── scripts/run_full.sh             # 🚀 Script de desarrollo (dev + Tauri)
├── docs/                           # 📚 Documentos (guías, plan, arquitectura, changelog)
└── frontend/                       # 🖥️ Aplicación (React + Tauri/Rust)
```

---

## 🚀 Desarrollo

### Prerrequisitos

```bash
✅ Rust (rustup)
✅ Node.js 18+
✅ Tauri CLI v2
```

### Iniciar en Desarrollo

```bash
# Instalar dependencias
cd frontend && npm install

# Iniciar frontend y backend simultáneamente en Tauri
npm run tauri:dev
```

---

## 📡 Comandos Tauri Principales

| Comando | Uso |
|:---|:---|
| `invoke('save_observation_json', ...)` | Guarda y estructura la observación sinóptica |
| `invoke('get_observation', ...)` | Recupera observación y campos calculados por fecha |
| `invoke('save_cli4074_json', ...)` | Guarda planilla CLI 4074 |
| `invoke('login_user', ...)` | Valida credenciales en base de datos local |
| `invoke('calculate_observations', ...)` | Motor meteorológico local |

---

## 👨‍💻 Autor

<p align="center">
  Desarrollado por <strong>Stward</strong><br/>
  Ingeniería de Sistemas y Computación
</p>

<p align="center">
  <em>"Todo lo que entra en el ARCA, sobrevive y prospera."</em> 🚢
</p>

---

<p align="center">
  <sub>📅 Última actualización: Julio 2026</sub>
</p>
