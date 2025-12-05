# 🚢 Proyecto ARCA

> **Arquitectura de Recursos, Cómputo y Administración**

<p align="center">
  <img src="https://img.shields.io/badge/Estado-En_Desarrollo-orange?style=for-the-badge" alt="Status"/>
  <img src="https://img.shields.io/badge/Version-2.1.0-blue?style=for-the-badge" alt="Version"/>
  <img src="https://img.shields.io/badge/Backend-FastAPI_Python-green?style=for-the-badge" alt="Backend"/>
  <img src="https://img.shields.io/badge/Frontend-React_Vite-blue?style=for-the-badge" alt="Frontend"/>
  <img src="https://img.shields.io/badge/Database-PostgreSQL-336791?style=for-the-badge" alt="Database"/>
</p>

---

## 📋 Sobre el Proyecto

**Proyecto ARCA** es un sistema especializado para la **gestión de datos meteorológicos e hidrológicos**, diseñado bajo una arquitectura de **Monolito Modular**. Su objetivo es centralizar la captura, procesamiento, auditoría y reporte de observaciones climáticas de estaciones meteorológicas.

### ✨ Características Principales

| Característica | Descripción |
| :--- | :--- |
| 📊 **Registro Sinóptico** | Formulario WMO completo con cálculos automáticos |
| � **Códigos SYNOP** | Generación automática de grupos 1snTTT, 4PPPP, 5aPPP, 58/59, 29UUU |
| 📈 **Resúmenes Mensuales** | Consolidación de datos por período |
| 🔍 **Auditoría** | Trazabilidad y corrección de datos históricos |
| 👥 **Multi-usuario** | Control de acceso basado en roles (RBAC) |

---

## 🌤️ Módulo Sinóptico (Nuevo)

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

### 🎨 Interfaz de Usuario

- **Temas Dinámicos**: El color cambia según la hora de observación (06Z-03Z)
- **Normalización de Presión**: Ingresa `15.3` → se convierte a `1015.3`
- **Enter Aplica Cambios**: Presiona Enter para aplicar y calcular
- **Tooltips WMO**: Descripciones breves al pasar el mouse
- **Campos Condicionales**: 6RRR y 7ww se habilitan según Ir/iX

---

## 🧩 Módulos del Sistema

| Módulo | Estado | Descripción |
| :--- | :---: | :--- |
| **🔐 Auth & Core** | 🟢 Listo | Gestión de identidad, seguridad JWT, Hashing y Roles (RBAC) |
| **🌤️ Observación Sinóptica** | 🟢 Activo | Formulario WMO con cálculos automáticos y códigos SYNOP |
| **📊 Resumen Mensual** | 🟢 Activo | Generación y consulta de resúmenes mensuales |
| **🔍 Correcciones y Auditoría** | 🟢 Activo | Logs de auditoría y corrección de datos |
| **🔧 CLI (3074/4074/5074)** | 🟡 Próximo | Módulos de mantenimiento de estaciones |

---

## 🛠️ Stack Tecnológico

<table>
<tr>
<td width="50%">

### 🧠 Backend (Python 3.10+)

| Tecnología | Uso |
|:---|:---|
| `FastAPI` | Framework Web asíncrono |
| `Uvicorn` | Servidor ASGI |
| `SQLAlchemy` | ORM para PostgreSQL |
| `Pydantic` | Validación de datos |
| `Python-Jose` | Tokens JWT |
| `Passlib` | Hashing bcrypt |

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
├── backend/
│   ├── app/
│   │   ├── core/               # Configuración global (DB, Seguridad)
│   │   ├── modules/
│   │   │   ├── auth/           # 🔐 Autenticación y Usuarios
│   │   │   ├── synoptic/       # 🌤️ Observación Sinóptica
│   │   │   │   ├── calculations.py   # Cálculos WMO
│   │   │   │   ├── schemas.py        # Validación Pydantic
│   │   │   │   └── routes.py         # Endpoints API
│   │   │   ├── summary/        # 📊 Resumen Mensual
│   │   │   └── audit/          # 🔍 Auditoría
│   │   └── main.py
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── features/
│   │   │   ├── auth/           # Login y Admin
│   │   │   ├── dashboard/      # Panel Principal
│   │   │   ├── synoptic/       # 🌤️ Formulario Sinóptico
│   │   │   ├── summary/        # Vista de Resúmenes
│   │   │   ├── audit/          # Vista de Auditoría
│   │   │   └── maintenance/    # 🔧 Página CLI (próximo)
│   │   └── App.jsx
│   └── package.json
│
├── Base para modulos/          # 📚 Manuales WMO de referencia
├── setup_full.sh               # Instalación automática
└── run_full.sh                 # Iniciar el sistema
```

---

## 🚀 Instalación Rápida

### Prerrequisitos

```bash
✅ Ubuntu/Debian (o Distrobox compatible)
✅ Python 3.10+
✅ Node.js 18+
✅ PostgreSQL
```

### Instalación Automática

```bash
# Dar permisos y ejecutar
chmod +x setup_full.sh
./setup_full.sh
```

### Iniciar el Sistema

```bash
./run_full.sh
```

> 🌐 **Frontend**: `http://localhost:5173`  
> 🔌 **API Docs**: `http://localhost:8000/docs`

---

## 🔑 Credenciales por Defecto

| Rol | Usuario | Contraseña |
|:---:|:---|:---|
| 👑 Admin | `admin@arca.com` | `123456` |

---

## 📡 Endpoints de la API

| Módulo | Ruta Base | Descripción |
|:---|:---|:---|
| 🔐 Auth | `/api/auth` | Login, Registro, Tokens |
| 👥 Admin | `/api/admin` | Gestión de usuarios y roles |
| 🌤️ Synoptic | `/api/synoptic` | Cálculos y observaciones |
| 📊 Summary | `/api/summary` | Resúmenes mensuales |
| 🔍 Audit | `/api/audit` | Logs y correcciones |

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
  <sub>📅 Última actualización: Diciembre 2024</sub>
</p>
