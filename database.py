import os
import sqlite3

def get_db_url():
    return os.environ.get('DATABASE_URL')

def get_db_connection():
    """Returns a database connection. Uses PostgreSQL if DATABASE_URL is set, otherwise SQLite."""
    db_url = get_db_url()
    if db_url:
        import psycopg2
        import psycopg2.extras
        # Ensure sslmode=require for cloud PostgreSQL (like Supabase) if not provided
        if "sslmode=" not in db_url:
            separator = "&" if "?" in db_url else "?"
            db_url = f"{db_url}{separator}sslmode=require"
        conn = psycopg2.connect(db_url)
        conn.autocommit = False
        return conn
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(base_dir, 'logistica.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

def execute_query(conn, query, params=None, fetch='all'):
    """Execute a query and return results. Handles SQLite vs PostgreSQL differences."""
    cursor = conn.cursor()
    cursor.execute(query, params or ())
    
    if fetch == 'one':
        return cursor.fetchone()
    elif fetch == 'all':
        return cursor.fetchall()
    elif fetch == 'none':
        conn.commit()
        return cursor
    return cursor

def row_to_dict(row, cursor=None):
    """Convert a database row to a dictionary."""
    if row is None:
        return None
    if get_db_url() and cursor:
        col_names = [desc[0] for desc in cursor.description]
        return dict(zip(col_names, row))
    elif hasattr(row, 'keys'):
        return dict(row)
    return row

def rows_to_dicts(rows, cursor=None):
    """Convert multiple database rows to a list of dictionaries."""
    if get_db_url() and cursor:
        col_names = [desc[0] for desc in cursor.description]
        return [dict(zip(col_names, r)) for r in rows]
    return [dict(r) if hasattr(r, 'keys') else r for r in rows]

def init_db():
    """Initialize SQLite database (local development only)."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, 'logistica.db')
    conn = sqlite3.connect(db_path)
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
    print("Base de datos SQLite creada exitosamente.")

if __name__ == "__main__":
    init_db()
