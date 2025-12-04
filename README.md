# 🚢 Proyecto ARCA
> **Arquitectura de Recursos, Cómputo y Administración**

![Status](https://img.shields.io/badge/Estado-En_Desarrollo-orange?style=for-the-badge)
![Version](https://img.shields.io/badge/Version-2.0.0-blue?style=for-the-badge)
![Backend](https://img.shields.io/badge/Backend-FastAPI_Python-green?style=for-the-badge)
![Frontend](https://img.shields.io/badge/Frontend-React_Vite-blue?style=for-the-badge)
![Database](https://img.shields.io/badge/Database-PostgreSQL-336791?style=for-the-badge)

---

## 📋 Sobre el Proyecto

**Proyecto ARCA** es un sistema especializado para la **gestión de datos meteorológicos e hidrológicos**, diseñado bajo una arquitectura de **Monolito Modular**. Su objetivo es centralizar la captura, procesamiento, auditoría y reporte de observaciones climáticas de estaciones meteorológicas.

El sistema facilita:
- 📊 **Registro de observaciones sinópticas** y datos de estaciones CLI
- 📈 **Generación de resúmenes mensuales** consolidados
- 🔍 **Auditoría y corrección** de datos históricos
- 👥 **Gestión de usuarios** con control de acceso basado en roles

### 🧩 Módulos del Sistema

| Módulo | Estado | Descripción |
| :--- | :---: | :--- |
| **🔐 Auth & Core** | 🟢 Listo | Gestión de identidad, seguridad JWT, Hashing y Roles (RBAC). |
| **🌤️ Observación Sinóptica** | 🟢 Activo | Registro y visualización de logs del sistema y datos de estaciones. |
| **📊 Resumen Mensual** | 🟢 Activo | Generación y consulta de resúmenes financieros/operativos mensuales. |
| **🔍 Correcciones y Auditoría** | 🟢 Activo | Logs de auditoría y gestión de solicitudes de corrección de datos. |

---

## 🛠️ Stack Tecnológico

### 🧠 Backend (Python 3.10+)
*   **Framework Web:** `FastAPI` (Alto rendimiento, asíncrono)
*   **Servidor ASGI:** `Uvicorn`
*   **Base de Datos (ORM):** `SQLAlchemy`
*   **Validación de Datos:** `Pydantic`
*   **Seguridad:** `Python-Jose` (JWT) + `Passlib[bcrypt]` (Hashing)

### 💻 Frontend (React 19+)
*   **Core:** `React` + `React DOM`
*   **Build Tool:** `Vite 7`
*   **Estilos:** `Tailwind CSS v4`
*   **Enrutamiento:** `React Router DOM v7`
*   **Cliente HTTP:** `Axios`
*   **Iconos:** `Lucide React`

---

## 🗄️ Estructura de Base de Datos

### 🔐 Auth (Autenticación)
*   **`users`**: Usuarios del sistema (email, password_hash, is_active)
*   **`roles`**: Roles definidos (Admin, Operador, Auditor)
*   **`user_roles`**: Relación Muchos-a-Muchos entre Usuarios y Roles

### 🌤️ Synoptic (Observación Sinóptica)
*   **`system_logs`**: Logs del sistema con timestamp, nivel, módulo y mensaje

### 📊 Summary (Resumen Mensual)
*   **`monthly_summaries`**: Resúmenes con ingresos, gastos y balance neto por periodo

### 🔍 Audit (Correcciones y Auditoría)
*   **`audit_logs`**: Registro de acciones con entidad, acción y detalles
*   **`correction_requests`**: Solicitudes de corrección con estado y descripción

---

## 📂 Estructura de Archivos

```text
Proyecto_ARCA/
├── backend/
│   ├── app/
│   │   ├── core/           # Configuración global (DB, Seguridad)
│   │   ├── modules/        # Módulos de Negocio
│   │   │   ├── auth/       # Autenticación y Usuarios
│   │   │   ├── synoptic/   # Observación Sinóptica
│   │   │   ├── summary/    # Resumen Mensual
│   │   │   └── audit/      # Correcciones y Auditoría
│   │   └── main.py         # Punto de entrada de la API
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── features/       # Módulos del Frontend
│   │   │   ├── auth/       # Login y Admin
│   │   │   ├── dashboard/  # Panel Principal
│   │   │   ├── synoptic/   # Vista de Observaciones
│   │   │   ├── summary/    # Vista de Resúmenes
│   │   │   └── audit/      # Vista de Auditoría
│   │   ├── shared/         # Componentes reutilizables
│   │   └── App.jsx         # Rutas y Configuración
│   └── package.json
│
├── setup_full.sh           # Script de instalación completa
└── run_full.sh             # Script para iniciar el sistema
```

---

## 🚀 Instalación Rápida

### Prerrequisitos
*   Ubuntu/Debian (o Distrobox compatible)
*   Python 3.10+
*   Node.js 18+
*   PostgreSQL

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

---

## 🔑 Credenciales por Defecto

| Rol | Usuario | Contraseña |
|-----|---------|------------|
| Admin | `admin@arca.com` | `123456` |

---

## 📡 Endpoints de la API

| Módulo | Ruta Base | Descripción |
|--------|-----------|-------------|
| Auth | `/api/auth` | Login, Registro |
| Admin | `/api/admin` | Gestión de usuarios |
| Synoptic | `/api/synoptic` | Logs del sistema |
| Summary | `/api/summary` | Resúmenes mensuales |
| Audit | `/api/audit` | Logs y correcciones |

> Documentación Swagger: `http://localhost:8000/docs`

---

## 👨‍💻 Autor

Desarrollado por **Stward** como parte de la evolución en Ingeniería de Sistemas y Computación.

> *"Todo lo que entra en el ARCA, sobrevive y prospera."*
