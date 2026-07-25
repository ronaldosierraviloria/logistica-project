-- ============================================================
-- LOGI-SINC: Schema PostgreSQL para Supabase
-- Ejecuta este script en el SQL Editor de Supabase
-- ============================================================

CREATE TABLE IF NOT EXISTS Usuario (
    IDUsuario SERIAL PRIMARY KEY,
    Nombres TEXT NOT NULL,
    Apellidos TEXT NOT NULL,
    Correo TEXT UNIQUE NOT NULL,
    Contrasena TEXT NOT NULL,
    Rol TEXT CHECK (Rol IN ('Administrador', 'Usuario', 'Gerente')) NOT NULL DEFAULT 'Usuario'
);

CREATE TABLE IF NOT EXISTS Empleados (
    ID_Empleado TEXT PRIMARY KEY,
    Nombre TEXT NOT NULL,
    Apellido TEXT NOT NULL,
    Direccion TEXT,
    Telefono TEXT,
    Salario REAL,
    Cargo TEXT,
    Fecha_Ingreso TEXT
);

CREATE TABLE IF NOT EXISTS Vehiculos (
    ID_Vehiculo TEXT PRIMARY KEY,
    Marca TEXT,
    Modelo TEXT,
    Anio INTEGER,
    Placa TEXT UNIQUE,
    Tipo_Vehiculo TEXT,
    Capacidad_Carga REAL
);

CREATE TABLE IF NOT EXISTS Rutas (
    ID_Ruta TEXT PRIMARY KEY,
    Origen TEXT,
    Destino TEXT,
    Distancia REAL,
    Tiempo_Entrega TEXT,
    Costo_Transporte REAL
);

CREATE TABLE IF NOT EXISTS Clientes (
    ID_Cliente TEXT PRIMARY KEY,
    Nombre TEXT NOT NULL,
    Direccion TEXT,
    Telefono TEXT,
    Email TEXT
);

CREATE TABLE IF NOT EXISTS Cargas (
    ID_Carga TEXT PRIMARY KEY,
    Tipo_Carga TEXT,
    Peso REAL,
    Volumen REAL,
    Valor_Carga REAL,
    ID_Ruta TEXT,
    FOREIGN KEY (ID_Ruta) REFERENCES Rutas (ID_Ruta)
);

CREATE TABLE IF NOT EXISTS Facturas (
    ID_Factura TEXT PRIMARY KEY,
    Fecha TEXT,
    ID_Cliente TEXT,
    Monto REAL,
    Estado TEXT,
    FOREIGN KEY (ID_Cliente) REFERENCES Clientes (ID_Cliente)
);

CREATE TABLE IF NOT EXISTS Proveedores (
    ID_Proveedor TEXT PRIMARY KEY,
    Nombre TEXT,
    Direccion TEXT,
    Telefono TEXT,
    Email TEXT
);

CREATE TABLE IF NOT EXISTS Gastos (
    ID_Gasto TEXT PRIMARY KEY,
    Fecha TEXT,
    Categoria TEXT,
    Monto REAL,
    Proveedor TEXT,
    Estado TEXT
);

CREATE TABLE IF NOT EXISTS Notificaciones (
    ID_Notificacion SERIAL PRIMARY KEY,
    ID_Usuario INTEGER,
    Tipo TEXT NOT NULL,
    Titulo TEXT NOT NULL,
    Mensaje TEXT NOT NULL,
    Icono TEXT DEFAULT 'bell',
    Leida BOOLEAN DEFAULT FALSE,
    Fecha_Creacion TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (ID_Usuario) REFERENCES Usuario (IDUsuario)
);

CREATE TABLE IF NOT EXISTS Configuracion (
    ID_Config SERIAL PRIMARY KEY,
    ID_Usuario INTEGER,
    Clave TEXT NOT NULL,
    Valor TEXT NOT NULL,
    UNIQUE(ID_Usuario, Clave),
    FOREIGN KEY (ID_Usuario) REFERENCES Usuario (IDUsuario)
);
