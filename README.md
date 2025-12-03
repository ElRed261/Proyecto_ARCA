# 🚢 Proyecto ARCA
> **Arquitectura de Recursos, Cómputo y Administración**

![Status](https://img.shields.io/badge/Estado-En_Desarrollo-orange?style=for-the-badge)
![Backend](https://img.shields.io/badge/Backend-FastAPI_Python-green?style=for-the-badge)
![Frontend](https://img.shields.io/badge/Frontend-React_Vite-blue?style=for-the-badge)
![Database](https://img.shields.io/badge/Database-PostgreSQL-336791?style=for-the-badge)

---

## 📋 Sobre el Proyecto

**Proyecto ARCA** es un sistema ERP (Enterprise Resource Planning) diseñado bajo una arquitectura de **Monolito Modular**. Su objetivo es centralizar y proteger todos los procesos vitales de una organización en un solo lugar seguro, escalable y eficiente.

A diferencia de los ERPs tradicionales, ARCA está construido con ingeniería moderna, separando estrictamente la lógica de negocio en módulos independientes pero interconectados.

### 🧩 Módulos del Sistema

| Módulo | Estado | Descripción |
| :--- | :---: | :--- |
| **🔐 Auth & Core** | 🟢 Listo | Gestión de identidad, seguridad JWT, Hashing y Roles. |
| **👥 HRM (RRHH)** | 🟡 Estructura | Gestión de empleados, contratos y perfiles. |
| **📦 SCM (Inventario)** | 🟡 Estructura | Logística, Almacenes, Productos y Proveedores. |
| **🤝 CRM (Ventas)** | 🟡 Estructura | Clientes, Oportunidades y Pedidos de Venta. |
| **💰 Accounting** | 🔴 Pendiente | Libro mayor, Impuestos y Facturación. |

---

## 🛠️ Stack Tecnológico y Librerías

El proyecto utiliza un stack de alto rendimiento (High-Performance) con las siguientes tecnologías y librerías clave:

### 🧠 Backend (Python 3.10+)
*   **Framework Web:** `FastAPI` (Alto rendimiento, asíncrono).
*   **Servidor ASGI:** `Uvicorn` (Servidor de aplicaciones).
*   **Base de Datos (ORM):** `SQLAlchemy` (Gestión de modelos relacionales).
*   **Migraciones:** `Alembic` (Control de versiones de BD - *Configurado*).
*   **Validación de Datos:** `Pydantic` (Validación estricta de tipos).
*   **Seguridad:**
    *   `Python-Jose`: Generación y validación de Tokens JWT.
    *   `Passlib[bcrypt]`: Hashing seguro de contraseñas.
*   **Utilidades:** `Python-Dotenv` (Variables de entorno).

### 💻 Frontend (React 18+)
*   **Core:** `React` + `React DOM`.
*   **Build Tool:** `Vite` (Empaquetado ultra rápido).
*   **Estilos:** `Tailwind CSS v4` + `PostCSS` (Diseño Utility-first).
*   **Enrutamiento:** `React Router DOM` (Navegación SPA).
*   **Cliente HTTP:** `Axios` (Conexión con API).
*   **Iconos:** `Lucide React` (Iconografía moderna y ligera).
*   **Linter:** `ESLint` (Calidad de código).

---

## 🗄️ Estructura de Base de Datos

El sistema utiliza **PostgreSQL** con un diseño relacional normalizado. A continuación se detallan las tablas principales por módulo:

### 🔐 Auth (Autenticación)
*   **`users`**: Usuarios del sistema (email, password_hash, is_active).
*   **`roles`**: Roles definidos (Admin, Gerente, Vendedor, etc.).
*   **`user_roles`**: Tabla pivote para relación Muchos-a-Muchos entre Usuarios y Roles.

### 👥 HRM (Recursos Humanos)
*   **`employees`**: Información del personal (cédula, nombres, fecha contratación).
    *   *Relación:* Vinculado 1:1 con `users` (opcional).

### 📦 SCM (Cadena de Suministro)
*   **`categories`**: Categorías de productos.
*   **`products`**: Catálogo maestro (SKU, precios, costos).
*   **`warehouses`**: Bodegas y ubicaciones físicas.
*   **`inventory_movements`**: Kardex de movimientos (Entradas/Salidas/Ajustes).
*   **`suppliers`**: Proveedores.
*   **`purchase_orders`**: Cabecera de órdenes de compra.
*   **`purchase_details`**: Detalle de productos en órdenes de compra.

### 🤝 CRM (Gestión Comercial)
*   **`customers`**: Clientes (RNC/Cédula, contacto).
*   **`sale_orders`**: Cabecera de pedidos de venta/cotizaciones.
*   **`sale_order_details`**: Detalle de productos en ventas.

---

## 📂 Estructura de Archivos y Carpetas

El código sigue una estructura de **Alta Cohesión y Bajo Acoplamiento**, facilitando la escalabilidad.

```text
Proyecto_ARCA/
├── backend/
│   ├── app/
│   │   ├── core/           # Configuración global (DB, Seguridad, Settings)
│   │   ├── modules/        # Módulos de Negocio (Lógica encapsulada)
│   │   │   ├── auth/       # Modelos y Rutas de Autenticación
│   │   │   ├── crm/        # Módulo de Ventas
│   │   │   ├── hrm/        # Módulo de RRHH
│   │   │   ├── scm/        # Módulo de Inventario
│   │   │   └── accounting/ # Módulo Contable (Futuro)
│   │   └── main.py         # Punto de entrada de la API
│   ├── alembic/            # Scripts de migración de BD
│   └── requirements.txt    # Dependencias de Python
│
└── frontend/
    ├── src/
    │   ├── features/       # "Espejo" de los módulos del backend (Vistas y Lógica)
    │   │   ├── auth/       # Páginas de Login y Registro
    │   │   ├── dashboard/  # Panel Principal y Navegación
    │   │   └── ...         # Otros módulos
    │   ├── shared/         # Componentes reutilizables (UI Kit, Hooks, Utils)
    │   ├── App.jsx         # Componente Raíz y Configuración de Rutas
    │   └── main.jsx        # Punto de montaje React
    ├── package.json        # Dependencias de Node.js
    └── vite.config.js      # Configuración de Vite
```

---

## 🚀 Instalación y Despliegue Local

Sigue estos pasos para levantar el ARCA en tu máquina local.

### Prerrequisitos
*   Python 3.10+
*   Node.js 18+
*   PostgreSQL instalado y corriendo.

### 1. Configuración de Base de Datos
```bash
# Entra a tu consola de Postgres
sudo -u postgres psql

# Ejecuta:
CREATE USER admin_arca WITH ENCRYPTED PASSWORD '123456';
CREATE DATABASE arca_db OWNER admin_arca;
```

### 2. Levantar el Backend 🐍

```bash
cd backend

# Crear y activar entorno virtual
python -m venv .venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt

# Iniciar el Servidor
uvicorn app.main:app --reload
```
> El Backend estará disponible en: `http://127.0.0.1:8000`
> Documentación API (Swagger): `http://127.0.0.1:8000/docs`

### 3. Levantar el Frontend ⚛️

```bash
cd frontend

# Instalar dependencias de Node
npm install

# Iniciar servidor de desarrollo
npm run dev
```
> El Frontend estará disponible en: `http://localhost:5173`

---

## 👨‍💻 Autor

Desarrollado por **Stward** como parte de la evolución en Ingeniería de Sistemas y Computación.

> *"Todo lo que entra en el ARCA, sobrevive y prospera."*
