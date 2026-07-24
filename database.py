import sqlite3

def init_db():
    conn = sqlite3.connect('logistica.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Usuario (
            IDUsuario INTEGER PRIMARY KEY AUTOINCREMENT,
            Nombres TEXT NOT NULL,
            Apellidos TEXT NOT NULL,
            Correo TEXT UNIQUE NOT NULL,
            Contrasena TEXT NOT NULL,
            Rol TEXT CHECK( Rol IN ('Administrador', 'Usuario', 'Gerente') ) NOT NULL DEFAULT 'Usuario'
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Empleados (
            ID_Empleado TEXT PRIMARY KEY,
            Nombre TEXT NOT NULL,
            Apellido TEXT NOT NULL,
            Direccion TEXT,
            Telefono TEXT,
            Salario REAL,
            Cargo TEXT,
            Fecha_Ingreso TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Vehiculos (
            ID_Vehiculo TEXT PRIMARY KEY,
            Marca TEXT,
            Modelo TEXT,
            Anio INTEGER,
            Placa TEXT UNIQUE,
            Tipo_Vehiculo TEXT,
            Capacidad_Carga REAL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Rutas (
            ID_Ruta TEXT PRIMARY KEY,
            Origen TEXT,
            Destino TEXT,
            Distancia REAL,
            Tiempo_Entrega TEXT,
            Costo_Transporte REAL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Clientes (
            ID_Cliente TEXT PRIMARY KEY,
            Nombre TEXT NOT NULL,
            Direccion TEXT,
            Telefono TEXT,
            Email TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Cargas (
            ID_Carga TEXT PRIMARY KEY,
            Tipo_Carga TEXT,
            Peso REAL,
            Volumen REAL,
            Valor_Carga REAL,
            ID_Ruta TEXT,
            FOREIGN KEY (ID_Ruta) REFERENCES Rutas (ID_Ruta)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Facturas (
            ID_Factura TEXT PRIMARY KEY,
            Fecha TEXT,
            ID_Cliente TEXT,
            Monto REAL,
            Estado TEXT,
            FOREIGN KEY (ID_Cliente) REFERENCES Clientes (ID_Cliente)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Proveedores (
            ID_Proveedor TEXT PRIMARY KEY,
            Nombre TEXT,
            Direccion TEXT,
            Telefono TEXT,
            Email TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Gastos (
            ID_Gasto TEXT PRIMARY KEY,
            Fecha TEXT,
            Categoria TEXT,
            Monto REAL,
            Proveedor TEXT,
            Estado TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Notificaciones (
            ID_Notificacion INTEGER PRIMARY KEY AUTOINCREMENT,
            ID_Usuario INTEGER,
            Tipo TEXT NOT NULL,
            Titulo TEXT NOT NULL,
            Mensaje TEXT NOT NULL,
            Icono TEXT DEFAULT 'bell',
            Leida INTEGER DEFAULT 0,
            Fecha_Creacion TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (ID_Usuario) REFERENCES Usuario (IDUsuario)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Configuracion (
            ID_Config INTEGER PRIMARY KEY AUTOINCREMENT,
            ID_Usuario INTEGER,
            Clave TEXT NOT NULL,
            Valor TEXT NOT NULL,
            UNIQUE(ID_Usuario, Clave),
            FOREIGN KEY (ID_Usuario) REFERENCES Usuario (IDUsuario)
        )
    ''')
    conn.commit()
    conn.close()
    print("Base de datos y tablas creadas exitosamente.")

if __name__ == "__main__":
    init_db()