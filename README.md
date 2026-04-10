# 🚢 Proyecto ARCA

> **Arquitectura de Recursos, Cómputo y Administración**

<p align="center">
  <img src="https://img.shields.io/badge/Estado-En_Desarrollo-orange?style=for-the-badge" alt="Status"/>
  <img src="https://img.shields.io/badge/Version-3.0.0-blue?style=for-the-badge" alt="Version"/>
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
| 📈 **Formulario CLI 3074** | Extracción Sinóptica Profunda (Viento m/s, Visibilidad, Tendencia) |
| 🔍 **Auditoría** | Trazabilidad y corrección de datos históricos |

---

## 🌤️ Módulo Sinóptico

### 🧮 Cálculos Automáticos

El sistema realiza automáticamente los siguientes cálculos meteorológicos:

```
┌─────────────────────────────────────────────────────────────┐
│  CÁLCULOS DE ESTACIÓN                                       │
├─────────────────────────────────────────────────────────────┤
│  📌 Punto de Rocío (Pr)     → Fórmula de Magnus-Tetens      │
│  📌 Tensión de Vapor (Tv)   → Ecuación de August-Roche      │
│  📌 Humedad Relativa (Hr)   → (e/es) × 100                  │
│  📌 Presión NMM             → Pres.Est + Correc.Alt         │
│  📌 Diferencias P3/P24      → Automático con normalización  │
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

### 📁 Almacenamiento JSON

Los datos se guardan en estructura jerárquica:
```
data/{station_code}/{year}/{month}/{station}{DDMMYYYY}.json
```

Ejemplo: `data/78484/2025/12/7848406122025.json`

### 🎨 Interfaz de Usuario

- **Temas Dinámicos**: El color cambia según la hora de observación (06Z-03Z)
- **Navegación Catálogo**: Botones ← Ant. / Sig. → con guardado automático
- **Campos Condicionales**: T_max/T_min bloqueados en horas impares (03Z, 09Z, 15Z, 21Z)
- **Normalización de Presión**: Ingresa `15.3` → se convierte a `1015.3`
- **Tooltips WMO**: Descripciones breves al pasar el mouse

### 📅 Navegación entre Días

| Botón | Función | Validaciones |
| :---: | :--- | :--- |
| **← Ant.** | Cargar día anterior | No permite ir antes del primer día registrado |
| **Sig. →** | Guardar y avanzar | Requiere datos de temperatura (Ts o Th) |

---

## 🧩 Módulos del Sistema

| Módulo | Estado | Descripción |
| :--- | :---: | :--- |
| **🌤️ Observación Sinóptica** | 🟢 Activo | Formulario WMO con cálculos automáticos (Rust Engine) |
| **🔧 CLI 3074** | 🟢 Activo | Formulario sinóptico de superficie con extracción profunda de Nddff y 5appp |
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
| `Rust` | Lenguaje de programación de alto rendimiento (Motor de Cálculos) |
| `Tauri v2` | Framework para aplicación de escritorio nativa multiplataforma |
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
| `Axios` | Cliente HTTP |
| `Lucide React` | Iconografía |

</td>
</tr>
</table>

---

## 📂 Estructura de Archivos

```
Proyecto_ARCA/
├── src-tauri/
│   ├── src/
│   │   ├── calculations.rs   # 🚀 Motor matemático en Rust puro (WMO)
│   │   ├── json_handler.rs   # 🚀 Sistema de persistencia ultrarrápido
│   │   ├── commands.rs       # Interface Tauri con el Frontend
│   │   └── main.rs
│   └── tauri.conf.json
│
├── frontend/
│   ├── src/
│   │   ├── features/
│   │   │   ├── synoptic/     # 🌤️ Formulario Sinóptico Principal
│   │   │   ├── cli3074/      # 🔧 Formulario Sinóptico CLI 3074
│   │   │   ├── summary/      # 📊 Vista de Resúmenes
│   │   │   └── dashboard/    # Panel Principal
│   │   └── App.jsx
│   └── package.json
│
├── docs/                     # 📚 Documentación y Excel original
└── data/                     # 📁 Almacenamiento local JSON
```

---

## 🚀 Desarrollo

### Prerrequisitos

```bash
✅ Rust (rustup)
✅ Node.js 18+
```

### Iniciar en Desarrollo

El proyecto ahora utiliza **Tauri v2** para brindar una experiencia nativa de escritorio pura.

```bash
# Iniciar frontend y backend simultáneamente en modo dev
npm run tauri dev
```

---

## 📡 Comunicación Frontend-Backend

En lugar de usar HTTP/REST (`Axios`), toda la comunicación ahora ocurre mediante **Tauri IPC** (Inter-Process Communication), ofreciendo una latencia de `~0.5ms`.

| Comando Tauri | Uso |
|:---|:---|
| `invoke('save_json', ...)` | Guarda la observación en disco |
| `invoke('load_json_date_range', ...)` | Carga todas las horas del día |
| `invoke('get_or_create_observation', ...)` | Verifica si existe observación |
| `invoke('calculate_observations', ...)` | Lógica sinóptica desde `calculations.rs` |

---

## 📸 Vista Previa

### Formulario Sinóptico
```
┌──────────────────────────────────────────────────────────────────────────┐
│  AAXX  │  YYGG Iw  │  IIiii    │  Fecha                                 │
├──────────────────────────────────────────────────────────────────────────┤
│ IriXHVV│  N dd ff  │  1snTTT   │  2snTdTd  │  4PPPP  │  5aPPP  │  7ww   │
├──────────────────────────────────────────────────────────────────────────┤
│ 8NhCL  │    333    │  0CSDL    │  1snTx    │  2snTn  │  3Ejjj  │  5EEE  │
├──────────────────────────────────────────────────────────────────────────┤
│ 5nFn   │  56DLDM   │  58/59P24 │  6RRRtr   │  7R24   │  8NsCh  │  8NsCh │
├──────────────────────────────────────────────────────────────────────────┤
│ ...    │    ...    │    ...    │    ...    │   ...   │   555   │ 29UUU  │
└──────────────────────────────────────────────────────────────────────────┘
```

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
