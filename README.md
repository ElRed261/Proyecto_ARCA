# 🚢 Proyecto ARCA

> **Arquitectura de Recursos, Cómputo y Administración**

<p align="center">
<img src="https://img.shields.io/badge/Estado-En_Desarrollo-orange?style=for-the-badge" alt="Status"/>
<img src="https://img.shields.io/badge/Version-3.1.0-blue?style=for-the-badge" alt="Version"/>
<img src="https://img.shields.io/badge/Desktop-Tauri_v2-purple?style=for-the-badge" alt="Desktop"/>
<img src="https://img.shields.io/badge/Backend-Rust-red?style=for-the-badge" alt="Backend"/>
<img src="https://img.shields.io/badge/Frontend-React_Vite-blue?style=for-the-badge" alt="Frontend"/>
</p>

---

## 📋 Sobre el Proyecto

**Proyecto ARCA** es un sistema especializado para la **gestión de datos meteorológicos e hidrológicos**, diseñado bajo una arquitectura de **Monolito Modular**. Su objetivo es centralizar la captura, procesamiento, auditoría y reporte de observaciones climáticas de estaciones meteorológicas.

### ✨ Características Principales

| Característica | Descripción |
| :--- | :--- |
| 📊 **Registro Sinóptico** | Formulario WMO completo con cálculos automáticos nativos |
| 📁 **Catálogo de Días** | Navegación entre días con guardado automático rápido en JSON |
| 🔄 **Códigos SYNOP** | Generación automática de grupos 1snTTT, 4PPPP, 5aPPP, 58/59, 29UUU |
| 📈 **Formulario CLI 3074** | Presión, humedad y viento con cálculos en tiempo real (DIF, CAR automático) |
| ☁️ **Formulario CLI 4074** | Nubosidad y temperatura con parseo automático de grupos 8NsChshs |
| 🔍 **Auditoría** | Trazabilidad y corrección de datos históricos |

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
| `0CS DL DM DH` | `56 DL DM DH` | Ambos codifican nubes con dirección |

### 📁 Almacenamiento JSON

Los datos se guardan en estructura jerárquica:
```
Documents/ARCA/{modulo}/{year}/{month}/{station}{DDMMYYYY}.json
```

Ejemplos:
- Sinóptico: `Documents/ARCA/synoptic/2026/04/7846015042026.json`
- CLI 3074: `Documents/ARCA/cli3074/2026/04/78460_2026-04-15_cli3074.json`
- CLI 4074: `Documents/ARCA/cli4074/2026/04/78460_2026-04-15_cli4074.json`

---

## 📈 CLI 3074 - Observaciones de Superficie

### 🎯 Campos Automáticos

| Campo | Fuente | Cálculo |
| :--- | :--- | :--- |
| **DIF** | pres_est - p3 | Formato "00.0" (truncado) |
| **CAR** | Código WMO 0266 | 0-8 según magnitud y signo |
| **Visibilidad** | IrIxHVV → VV | Tabla WMO Code 4377 |
| **Tiempo Presente** | 7wwW1W2 | Comparación Nddff si vacío |

### 📊 Estructura del Formulario

```
┌───────────────────────────────────────────────────────────────────────┐
│ HORA │ PRESIÓN (hPa) │ 3H TEND │ TEMP │ HUMEDAD │ VIENTO │ VIS │ FEN │
├──────┼───────────────┼─────────┼──────┼─────────┼────────┼─────┼─────┤
│  1   │ Est NMM Alti  │ CAR DIF │ SEC  │ PTO TV  │ DIR VEL│ km  │ ww  │
└───────────────────────────────────────────────────────────────────────┘
```

---

## ☁️ CLI 4074 - Nubosidad y Temperatura

### 🎯 Parseo de Grupos 8

El sistema parsea automáticamente los grupos `8NsChshs`:

| Código | Tipo de Nube | Categoría |
| :---: | :--- | :--- |
| `9` | Cumulonimbus | CB |
| `8, 7, 6` | Nubes Bajas | CL |
| `5, 4, 3` | Nubes Medias | CM |
| `2, 1, 0` | Nubes Altas | CH |

### 📏 Conversión de Altura (hshs)

| Tipo | Códigos | Rango Pies | Rango Metros |
| :--- | :---: | :--- | :--- |
| Bajas | 3-50 | 300-5000 | 91-1524 |
| Medias | 56-68 | 6000-18000 | 1828-5486 |
| Altas | 69-80 | 19000-30000 | 5791-9144 |

**Nota:** Conversión truncada (sin redondeo): 6000 pies = 1828 m

### 📊 Estructura del Formulario

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│HORA│N│ CÚMULONIMBOS │ NUBES BAJAS │TOTAL│ NUBES MEDIAS │TOTAL│ NUBES ALTAS │TOTAL│LLUV│TEMPS│EST│OBS│
├────┼─┼──────────────┼─────────────┼─────┼──────────────┼─────┼─────────────┼─────┼────┼─────┼───┼───┤
│ 1  │ │Cant Tipo Alt │Cant Tipo Alt│  Σ  │Cant Tipo Alt │  Σ  │Cant Tipo Alt│  Σ  │6h  │Máx Mín│   │   │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🧩 Módulos del Sistema

| Módulo | Estado | Descripción |
| :--- | :---: | :--- |
| **🌤️ Observación Sinóptica** | 🟢 Activo | Formulario WMO con cálculos automáticos (Rust Engine) |
| **🔧 CLI 3074** | 🟢 Activo | Presión, humedad y viento con extracción profunda |
| **☁️ CLI 4074** | 🟢 Activo | Nubosidad y temperatura con parseo de grupos 8 |
| **📊 Resumen Mensual** | 🟡 Próximo | Generación y consulta de resúmenes mensuales |
| **🔍 Correcciones y Auditoría** | 🟡 Próximo | Logs de auditoría y corrección de datos |

---

## 🛠️ Stack Tecnológico

<table>
<tr>
<td width="50%">

### 🧠 Backend Nativo (Rust & Tauri v2)

| Tecnología | Uso |
|:---|:---|
| `Rust` | Lenguaje de programación de alto rendimiento |
| `Tauri v2` | Framework para aplicación de escritorio multiplataforma |
| `Serde` | Serialización/Deserialización ultrarrápida de JSON |
| `Lazy Static` | Caché en memoria para constantes (Estaciones) |

</td>
<td width="50%">

### 💻 Frontend (React 19+)

| Tecnología | Uso |
|:---|:---|
| `React` | Interfaz de usuario |
| `Vite 7` | Build tool rápido |
| `Tailwind CSS v4` | Estilos utility-first |
| `React Router v7` | Enrutamiento SPA |
| `Lucide React` | Iconografía |

</td>
</tr>
</table>

---

## 📂 Estructura de Archivos

```
Proyecto_ARCA/
├── src-tauri/
│   └── src/
│       ├── calculations.rs      # 🚀 Motor matemático WMO
│       ├── json_handler.rs      # 🚀 Persistencia JSON + CLI handlers
│       ├── cli_autofill.rs      # 🚀 Autofill CLI 3074
│       ├── visibility.rs        # 🚀 Tabla de visibilidad
│       ├── audit.rs             # 🚀 Auditoría
│       ├── summary.rs           # 🚀 Resúmenes mensuales
│       └── lib.rs               # 🚀 Registro de comandos Tauri
│
├── frontend/
│   └── src/
│       └── features/
│           ├── synoptic/
│           │   ├── pages/           # 🌤️ SynopticPage
│           │   ├── components/      # Sidebar
│           │   ├── cli3074/         # 🔧 CLI 3074
│           │   │   └── pages/       # Cli3074Page
│           │   └── cli4074/         # ☁️ CLI 4074
│           │       └── pages/       # Cli4074Page
│           ├── summary/             # 📊 Resúmenes
│           ├── audit/               # 🔍 Auditoría
│           └── dashboard/           # Panel Principal
│
├── docs/                           # 📚 Documentación y referencias
│   ├── CLI 3074.png
│   ├── CLI 4074.png
│   ├── CLI 4074.csv
│   └── Tabla de nubes y Visibilidad codificada.csv
│
└── Documents/ARCA/                 # 📁 Almacenamiento JSON
    ├── synoptic/{year}/{month}/
    ├── cli3074/{year}/{month}/
    └── cli4074/{year}/{month}/
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

# Iniciar frontend y backend simultáneamente
npm run tauri dev
```

---

## 📡 Comandos Tauri

| Comando | Uso |
|:---|:---|
| `invoke('save_observation_json', ...)` | Guarda observación sinóptica |
| `invoke('get_observation', ...)` | Carga observación por fecha |
| `invoke('save_cli3074_json', ...)` | Guarda formulario CLI 3074 |
| `invoke('load_cli3074_json', ...)` | Carga CLI 3074 |
| `invoke('save_cli4074_json', ...)` | Guarda formulario CLI 4074 |
| `invoke('load_cli4074_json', ...)` | Carga CLI 4074 |
| `invoke('calculate_observations', ...)` | Cálculos meteorológicos |

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
<sub>📅 Última actualización: Abril 2026</sub>
</p>

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
<sub>📅 Última actualización: Abril 2026</sub>
</p>

<p align="center">
  <em>"Todo lo que entra en el ARCA, sobrevive y prospera."</em> 🚢
</p>

---

<p align="center">
  <sub>📅 Última actualización: Abril 2026</sub>
</p>
