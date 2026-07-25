from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, jsonify
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import os
import json
from datetime import datetime
import io
import xlsxwriter

base_dir = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, 
            template_folder=os.path.join(base_dir, 'FrontEnd', 'Templates'), 
            static_folder=os.path.join(base_dir, 'FrontEnd', 'Static'))
app.secret_key = "supersecretkey"

# --- DATABASE LAYER ---
DATABASE_URL = os.environ.get('DATABASE_URL')
IS_POSTGRES = bool(DATABASE_URL)

class CaseInsensitiveDict(dict):
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.update(*args, **kwargs)
    def __setitem__(self, key, value):
        super().__setitem__(key.lower(), value)
    def __getitem__(self, key):
        return super().__getitem__(key.lower())
    def __contains__(self, key):
        return super().__contains__(key.lower())
    def get(self, key, default=None):
        return super().get(key.lower(), default)

if IS_POSTGRES:
    import psycopg2
    import psycopg2.extras
    import pandas as pd
else:
    import sqlite3
    import pandas as pd

def get_db_connection():
    """Returns a database connection. PostgreSQL if DATABASE_URL is set, else SQLite."""
    if IS_POSTGRES:
        db_url = DATABASE_URL
        if "sslmode=" not in db_url:
            separator = "&" if "?" in db_url else "?"
            db_url = f"{db_url}{separator}sslmode=require"
        conn = psycopg2.connect(db_url)
        conn.autocommit = False
        return conn
    else:
        db_path = os.path.join(base_dir, 'logistica.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

def db_execute(conn, query, params=None, fetch='all'):
    """Execute a query handling both PostgreSQL and SQLite."""
    cursor = conn.cursor()
    q = query
    p = params
    if not IS_POSTGRES and params:
        q = query.replace('%s', '?')
    if p:
        cursor.execute(q, p)
    else:
        cursor.execute(q)
    
    if fetch == 'one':
        row = cursor.fetchone()
        if row is None:
            return None
        if IS_POSTGRES:
            col_names = [desc[0] for desc in cursor.description]
            return CaseInsensitiveDict(zip(col_names, row))
        return row
    elif fetch == 'all':
        rows = cursor.fetchall()
        if IS_POSTGRES:
            col_names = [desc[0] for desc in cursor.description] if cursor.description else []
            return [CaseInsensitiveDict(zip(col_names, r)) for r in rows]
        return rows
    elif fetch == 'count':
        row = cursor.fetchone()
        return row[0] if row else 0
    elif fetch == 'none':
        conn.commit()
        return cursor
    return cursor

def db_execute_raw(conn, query, params=None):
    """Execute a query and return raw cursor (for compatibility with existing code)."""
    cursor = conn.cursor()
    q = query
    p = params
    if not IS_POSTGRES and params:
        q = query.replace('%s', '?')
    if p:
        cursor.execute(q, p)
    else:
        cursor.execute(q)
    return cursor

def raw_row_to_list(row):
    """Convert a row to a list of values."""
    if row is None:
        return []
    if IS_POSTGRES:
        return list(row)
    return list(row)

def sql_compat(query, params=None):
    """Translate query for SQLite compatibility when needed."""
    if IS_POSTGRES:
        return query, params
    return query.replace('%s', '?'), params

# --- CUSTOM JINJA2 FILTERS ---
@app.template_filter('format_currency')
def format_currency(value):
    if value is None:
        return '$0'
    try:
        val = float(value)
        return f'${int(val):,}'
    except (ValueError, TypeError):
        return str(value)

@app.template_filter('format_number')
def format_number(value):
    if value is None:
        return '0'
    try:
        val = float(value)
        if val == int(val):
            return f'{int(val):,}'
        return f'{val:,.2f}'
    except (ValueError, TypeError):
        return str(value)

@app.template_filter('is_list')
def is_list(value):
    return isinstance(value, list)

UPLOAD_FOLDER = '/tmp' if IS_POSTGRES else os.path.join('FrontEnd', 'Static', 'Uploads')

if not IS_POSTGRES:
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

# --- DASHBOARD Y GESTIÓN DE TABLAS ---
@app.route('/')
def index():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    tabla_seleccionada = request.args.get('tabla')
    conn = get_db_connection()
    
    totales = {
        'empleados': db_execute_safe(conn, 'SELECT COUNT(*) FROM Empleados', fetch='count', default=0),
        'vehiculos': db_execute_safe(conn, 'SELECT COUNT(*) FROM Vehiculos', fetch='count', default=0),
        'rutas': db_execute_safe(conn, 'SELECT COUNT(*) FROM Rutas', fetch='count', default=0),
        'clientes': db_execute_safe(conn, 'SELECT COUNT(*) FROM Clientes', fetch='count', default=0)
    }

    if not tabla_seleccionada:
        row = db_execute_safe(conn, "SELECT SUM(Monto) FROM Facturas WHERE Estado='Pagada'", fetch='one')
        ingresos_total = 0
        if row:
            val = row['sum'] if IS_POSTGRES else (row[0] if hasattr(row, '__getitem__') else None)
            if val is not None:
                try:
                    ingresos_total = float(val)
                except (ValueError, TypeError):
                    ingresos_total = 0

        cargas_raw = db_execute_safe(conn, 'SELECT Tipo_Carga, COUNT(*) as cant FROM Cargas GROUP BY Tipo_Carga', fetch='all', default=[])
        if IS_POSTGRES:
            chart_cargas = {'labels': [r['tipo_carga'] for r in cargas_raw], 'values': [r['cant'] for r in cargas_raw]}
        else:
            chart_cargas = {'labels': [r['Tipo_Carga'] for r in cargas_raw], 'values': [r['cant'] for r in cargas_raw]}

        facturas_raw = db_execute_safe(conn, 'SELECT Fecha, SUM(Monto) as total FROM Facturas GROUP BY Fecha ORDER BY Fecha ASC', fetch='all', default=[])
        if IS_POSTGRES:
            chart_ingresos = {'labels': [r['fecha'] for r in facturas_raw], 'values': [r['total'] for r in facturas_raw]}
        else:
            chart_ingresos = {'labels': [r['Fecha'] for r in facturas_raw], 'values': [r['total'] for r in facturas_raw]}

        recientes = db_execute_safe(conn, '''
            SELECT f.ID_Factura, c.Nombre, f.Monto, f.Estado 
            FROM Facturas f 
            JOIN Clientes c ON f.ID_Cliente = c.ID_Cliente 
            ORDER BY f.ID_Factura DESC LIMIT 4
        ''', fetch='all', default=[])
        if not IS_POSTGRES and recientes:
            recientes = [dict(r) for r in recientes]

        excel_filename = session.get('excel_filename')
        excel_uploaded = excel_filename and os.path.exists(os.path.join(UPLOAD_FOLDER, excel_filename))

        conn.close()
        return render_template('index.html', vista='dashboard',
                               es_dashboard=True, totales=totales, ingresos=ingresos_total,
                               recientes=recientes, chart_cargas=json.dumps(chart_cargas),
                               chart_ingresos=json.dumps(chart_ingresos), tabla_activa='Centro de Control',
                               excel_uploaded=excel_uploaded, excel_filename=excel_filename)

    else:
        datos_tabla = []
        columnas = []
        try:
            cursor = db_execute_raw(conn, f'SELECT * FROM {tabla_seleccionada}')
            datos_tabla = [list(row) for row in cursor.fetchall()]
            columnas = [desc[0] for desc in cursor.description]
        except Exception as e: print(f"Error: {e}")
        
        conn.close()
        return render_template('index.html', es_dashboard=False, datos_tabla=datos_tabla, 
                               columnas=columnas, totales=totales, tabla_activa=tabla_seleccionada)

# --- PROCESAMIENTO DE ARCHIVOS EXCEL XLSX Y CSV ---
@app.route('/upload_file', methods=['POST'])
def upload_file():
    file = request.files.get('file')
    if file and file.filename != '':
        filepath = os.path.join(UPLOAD_FOLDER, secure_filename(file.filename))
        file.save(filepath)
        try:
            excel_data = pd.read_excel(filepath, sheet_name=None)
            if IS_POSTGRES:
                engine = pd.io.sql.SQLDatabase(pd.io.sql.SQLTable(
                    'temp', pd.io.sql.SQLDatabase(DATABASE_URL), None
                ) if False else None)
                import sqlalchemy
                engine = sqlalchemy.create_engine(DATABASE_URL)
                tablas_validas = ['Usuario', 'Empleados', 'Vehiculos', 'Rutas', 'Clientes', 'Cargas', 'Facturas', 'Proveedores', 'Gastos']
                for hoja, df in excel_data.items():
                    if hoja.strip() in tablas_validas:
                        df.to_sql(hoja.strip(), engine, if_exists='append', index=False)
                engine.dispose()
            else:
                conn = sqlite3.connect(os.path.join(base_dir, 'logistica.db'))
                tablas_validas = ['Usuario', 'Empleados', 'Vehiculos', 'Rutas', 'Clientes', 'Cargas', 'Facturas', 'Proveedores', 'Gastos']
                for hoja, df in excel_data.items():
                    if hoja.strip() in tablas_validas:
                        df.to_sql(hoja.strip(), conn, if_exists='append', index=False)
                conn.commit()
                conn.close()
            session['excel_filename'] = secure_filename(file.filename)
            crear_notificacion('upload', 'Carga de datos', f'Archivo "{file.filename}" importado correctamente a la base de datos.', 'upload')
            flash('¡Base de datos alimentada correctamente!', 'success')
        except Exception as e: flash(f'Error: {str(e)}', 'danger')
    return redirect(url_for('index'))

@app.route('/descargar_excel')
def descargar_excel():
    if 'user_id' not in session: return redirect(url_for('login'))
    filename = session.get('excel_filename')
    if not filename:
        flash('No hay archivo Excel para descargar', 'warning')
        return redirect(url_for('index'))
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(filepath):
        flash('El archivo Excel ya no está disponible', 'warning')
        session.pop('excel_filename', None)
        return redirect(url_for('index'))
    return send_file(filepath, as_attachment=True, download_name=filename)

@app.route('/exportar_datos')
def exportar_datos():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = get_db_connection()
    tablas = ['Empleados', 'Vehiculos', 'Rutas', 'Clientes', 'Cargas', 'Facturas', 'Proveedores', 'Gastos']
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        for tabla in tablas:
            try:
                if IS_POSTGRES:
                    df = pd.read_sql_query(f'SELECT * FROM {tabla}', conn)
                else:
                    df = pd.read_sql_query(f'SELECT * FROM {tabla}', conn)
                df.to_excel(writer, sheet_name=tabla, index=False)
            except Exception as e:
                print(f"Error exportando {tabla}: {e}")
    
    conn.close()
    output.seek(0)
    
    fecha_actual = datetime.now().strftime('%Y%m%d')
    return send_file(output, download_name=f"Sincelejo_Datos_{fecha_actual}.xlsx", as_attachment=True)

# --- LOGIN / LOGOUT ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo, password = request.form.get('correo'), request.form.get('password')
        conn = get_db_connection()
        user = db_execute(conn, 'SELECT * FROM Usuario WHERE Correo = %s', (correo,), fetch='one')
        conn.close()
        if user and check_password_hash(user['Contrasena'], password):
            session.update({'user_id': user['IDUsuario'], 'user_name': f"{user['Nombres']} {user['Apellidos']}", 'user_role': user['Rol']})
            crear_notificacion('acceso', 'Inicio de sesión', f'{user["Nombres"]} {user["Apellidos"]} ha iniciado sesión en el sistema.', 'log-in', user['IDUsuario'])
            return redirect(url_for('index'))
        flash('Credenciales inválidas', 'danger')
    return render_template('Auth/login.html')

# ---- REGISTRO ----
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nombres = request.form.get('nombres')
        apellidos = request.form.get('apellidos')
        correo = request.form.get('correo')
        password = request.form.get('password')
        rol = request.form.get('rol', 'Usuario')

        if not correo or not password:
            flash('Correo y contraseña son obligatorios', 'danger')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        try:
            existe = db_execute(conn, 'SELECT IDUsuario FROM Usuario WHERE Correo = %s', (correo,), fetch='one')
            if existe:
                flash('El correo ya está registrado', 'warning')
                return redirect(url_for('register'))
                        
            db_execute(conn, '''
                INSERT INTO Usuario (Nombres, Apellidos, Correo, Contrasena, Rol) 
                VALUES (%s, %s, %s, %s, %s)
            ''', (nombres, apellidos, correo, hashed_password, rol), fetch='none')
            
            new_user = db_execute(conn, 'SELECT IDUsuario FROM Usuario WHERE Correo = %s', (correo,), fetch='one')
            crear_notificacion('registro', 'Nuevo usuario registrado', f'{nombres} {apellidos} se ha registrado en el sistema con rol {rol}.', 'user-plus', new_user['IDUsuario'])
            
            flash('Cuenta creada con éxito. ¡Ahora puedes iniciar sesión!', 'success')
            return redirect(url_for('login'))
        
        except Exception as e:
            print(f"Error en registro: {e}")
            flash('Error interno al crear la cuenta', 'danger')
        finally:
            conn.close()

    return render_template('Auth/register.html')
            
#---- PERFIL DE USUARIO ---
@app.route('/perfil', methods=['GET', 'POST'])
def perfil():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = get_db_connection()
    user = db_execute(conn, 'SELECT * FROM Usuario WHERE IDUsuario = %s', (session['user_id'],), fetch='one')
    
    if request.method == 'POST':
        accion = request.form.get('accion')
        
        if accion == 'actualizar_perfil':
            nombres = request.form.get('nombres', '').strip()
            apellidos = request.form.get('apellidos', '').strip()
            correo = request.form.get('correo', '').strip()
            
            if nombres and apellidos and correo:
                try:
                    db_execute(conn, 'UPDATE Usuario SET Nombres = %s, Apellidos = %s, Correo = %s WHERE IDUsuario = %s',
                                (nombres, apellidos, correo, session['user_id']), fetch='none')
                    session['user_name'] = f"{nombres} {apellidos}"
                    flash('Perfil actualizado correctamente', 'success')
                except Exception as e:
                    flash(f'Error al actualizar: {str(e)}', 'danger')
            else:
                flash('Todos los campos son obligatorios', 'warning')
        
        elif accion == 'cambiar_contrasena':
            actual = request.form.get('contrasena_actual', '')
            nueva = request.form.get('contrasena_nueva', '')
            confirmar = request.form.get('contrasena_confirmar', '')
            
            if not check_password_hash(user['Contrasena'], actual):
                flash('La contraseña actual no es correcta', 'danger')
            elif len(nueva) < 6:
                flash('La nueva contraseña debe tener al menos 6 caracteres', 'warning')
            elif nueva != confirmar:
                flash('Las contraseñas nuevas no coinciden', 'warning')
            else:
                try:
                    hashed = generate_password_hash(nueva)
                    db_execute(conn, 'UPDATE Usuario SET Contrasena = %s WHERE IDUsuario = %s',
                                (hashed, session['user_id']), fetch='none')
                    flash('Contraseña actualizada correctamente', 'success')
                except Exception as e:
                    flash(f'Error al cambiar contraseña: {str(e)}', 'danger')
        
        conn.close()
        return redirect(url_for('perfil'))
    
    conn.close()
    return render_template('perfil.html', vista='perfil', usuario=user, tabla_activa='Mi Perfil')

#---- CONFIGURACION DEL SISTEMA ---
@app.route('/configuracion', methods=['GET', 'POST'])
def configuracion():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = get_db_connection()
    user_id = session['user_id']
    
    if request.method == 'POST':
        accion = request.form.get('accion')
        
        try:
            if accion == 'guardar_config':
                preferencias = {
                    'tema': request.form.get('tema', 'dark'),
                    'sidebar_colapsado': request.form.get('sidebar_colapsado', 'false'),
                    'notif_upload': request.form.get('notif_upload', 'true'),
                    'notif_eliminar': request.form.get('notif_eliminar', 'true'),
                    'notif_registro': request.form.get('notif_registro', 'true'),
                    'filas_tabla': request.form.get('filas_tabla', '10'),
                    'animaciones': request.form.get('animaciones', 'true')
                }
                for clave, valor in preferencias.items():
                    if IS_POSTGRES:
                        db_execute(conn, '''
                            INSERT INTO Configuracion (ID_Usuario, Clave, Valor) VALUES (%s, %s, %s)
                            ON CONFLICT(ID_Usuario, Clave) DO UPDATE SET Valor = EXCLUDED.Valor
                        ''', (user_id, clave, valor), fetch='none')
                    else:
                        db_execute(conn, '''
                            INSERT INTO Configuracion (ID_Usuario, Clave, Valor) VALUES (?, ?, ?)
                            ON CONFLICT(ID_Usuario, Clave) DO UPDATE SET Valor = excluded.Valor
                        ''', (user_id, clave, valor), fetch='none')
                flash('Configuracion guardada correctamente', 'success')
            
            elif accion == 'limpiar_notificaciones':
                db_execute(conn, 'DELETE FROM Notificaciones WHERE ID_Usuario = %s', (user_id,), fetch='none')
                flash('Notificaciones eliminadas', 'success')
            
            elif accion == 'limpiar_db':
                if session.get('user_role') == 'Administrador':
                    tablas = ['Empleados', 'Vehiculos', 'Rutas', 'Clientes', 'Cargas', 'Facturas', 'Proveedores', 'Gastos']
                    for t in tablas:
                        db_execute(conn, f'DELETE FROM {t}', fetch='none')
                    flash('Base de datos limpiada exitosamente', 'success')
                else:
                    flash('Solo administradores pueden limpiar la base de datos', 'danger')
        except Exception as e:
            print(f"Error en configuracion POST: {e}")
            flash('Error al guardar la configuracion', 'danger')
        
        conn.close()
        return redirect(url_for('configuracion'))
    
    # GET - cargar configuracion actual
    config_rows = db_execute(conn, 'SELECT Clave, Valor FROM Configuracion WHERE ID_Usuario = %s', (user_id,), fetch='all')
    if IS_POSTGRES:
        config = {row['clave']: row['valor'] for row in config_rows}
    else:
        config = {row['Clave']: row['Valor'] for row in config_rows}
    
    # Estadisticas de la base de datos
    stats = {}
    for t in ['Empleados', 'Vehiculos', 'Rutas', 'Clientes', 'Cargas', 'Facturas', 'Proveedores', 'Gastos']:
        stats[t] = db_execute(conn, f'SELECT COUNT(*) FROM {t}', fetch='count')
    max_count = max(stats.values()) if stats.values() else 1
    total_notifs = db_execute(conn, 'SELECT COUNT(*) FROM Notificaciones WHERE ID_Usuario = %s', (user_id,), fetch='count')
    total_usuarios = db_execute(conn, 'SELECT COUNT(*) FROM Usuario', fetch='count')
    
    conn.close()
    
    if not config:
        config = {'tema': 'dark', 'sidebar_colapsado': 'false', 'notif_upload': 'true',
                  'notif_eliminar': 'true', 'notif_registro': 'true', 'filas_tabla': '10', 'animaciones': 'true'}
    
    return render_template('configuracion.html', vista='configuracion', config=config, 
                           stats=stats, max_count=max_count, total_notifs=total_notifs, total_usuarios=total_usuarios,
                           tabla_activa='Configuracion')

#---- CERRAR SESION ---
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

 # --- PAGINA EMPLEADOS Y VEHICULOS ---           
@app.route('/activos_internos')
def activos_internos():
    if 'user_id' not in session: 
        return redirect(url_for('login'))
    
    tipo = request.args.get('tipo', 'personal')
    page = int(request.args.get('page', 1))
    per_page = 10
    offset = (page - 1) * per_page
    conn = get_db_connection()
    datos_tabla = []
    columnas_tabla = []
    total_records = 0

    res_emp = db_execute(conn, "SELECT Cargo, COUNT(*) as cnt FROM Empleados GROUP BY Cargo", fetch='all')
    if IS_POSTGRES:
        chart_emp = {"labels": [r['cargo'] for r in res_emp], "values": [r['cnt'] for r in res_emp]}
    else:
        chart_emp = {"labels": [r[0] for r in res_emp], "values": [r[1] for r in res_emp]}

    res_veh = db_execute(conn, "SELECT Marca, COUNT(*) as cnt FROM Vehiculos GROUP BY Marca", fetch='all')
    if IS_POSTGRES:
        chart_veh = {"labels": [r['marca'] for r in res_veh], "values": [r['cnt'] for r in res_veh]}
    else:
        chart_veh = {"labels": [r[0] for r in res_veh], "values": [r[1] for r in res_veh]}

    try:
        if tipo == 'personal':
            total_records = db_execute(conn, 'SELECT COUNT(*) FROM Empleados', fetch='count')
            cursor = db_execute_raw(conn, 'SELECT ID_Empleado, Nombre, Apellido, Cargo, Telefono FROM Empleados LIMIT %s OFFSET %s', (per_page, offset))
            columnas_tabla = ["Nombre", "Apellido", "Cargo", "Teléfono"]
        else:
            total_records = db_execute(conn, 'SELECT COUNT(*) FROM Vehiculos', fetch='count')
            cursor = db_execute_raw(conn, 'SELECT ID_Vehiculo, Placa, Marca, Modelo, Tipo_Vehiculo, Anio, Capacidad_Carga FROM Vehiculos LIMIT %s OFFSET %s', (per_page, offset))
            columnas_tabla = ["Placa", "Marca", "Modelo", "Tipo Vehículo", "Año","Capacidad De Carga"]
        
        datos_tabla = [list(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

    total_pages = (total_records + per_page - 1) // per_page
    
    numero_indices = []
    moneda_indices = []
    if tipo == 'vehiculos':
        numero_indices = [5]
    
    return render_template('activos_internos.html', 
                           vista='activos', tipo=tipo, 
                           datos=datos_tabla, columnas=columnas_tabla,
                           numero_indices=numero_indices, moneda_indices=moneda_indices,
                           page=page, total_pages=total_pages, total_records=total_records,
                           chart_emp=chart_emp, chart_veh=chart_veh)
            
#--- BOTON DE ELIMINAR ---
@app.route('/eliminar_activo/<tipo>/<id>')
def eliminar_activo(tipo, id):
    if 'user_id' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    
    mapeo = {
        'personal': ('Empleados', 'ID_Empleado'),
        'vehiculos': ('Vehiculos', 'ID_Vehiculo'),
        'clientes': ('Clientes', 'ID_Cliente'),
        'cargas': ('Cargas', 'ID_Carga'),
        'rutas': ('Rutas', 'ID_Ruta')
    }

    if tipo in mapeo:
        tabla, columna_id = mapeo[tipo]
        try:
            db_execute(conn, f'DELETE FROM {tabla} WHERE {columna_id} = %s', (id,), fetch='none')
            crear_notificacion('eliminar', 'Registro eliminado', f'Se eliminó un registro de {tipo} con ID {id}.', 'trash-2')
            flash(f'Registro de {tipo} eliminado con éxito', 'success')
        except Exception as e:
            flash(f'Error al eliminar: {e}', 'danger')
    
    conn.close()
    if tipo in ['clientes', 'cargas', 'rutas']:
        return redirect(url_for('operaciones', tipo=tipo))
    return redirect(url_for('activos_internos', tipo=tipo))
            
#--- PAGINA DE OPERACIONES CLIENTES, RUTAS ---
@app.route('/operaciones')
def operaciones():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    tipo = request.args.get('tipo', 'rutas')
    page = int(request.args.get('page', 1))
    per_page = 10
    offset = (page - 1) * per_page
    conn = get_db_connection()
    
    # --- KPIs ---
    total_rutas = db_execute(conn, 'SELECT COUNT(*) FROM Rutas', fetch='count')
    total_cargas = db_execute(conn, 'SELECT COUNT(*) FROM Cargas', fetch='count')
    total_clientes = db_execute(conn, 'SELECT COUNT(*) FROM Clientes', fetch='count')
    
    peso_total = db_execute(conn, 'SELECT SUM(Peso) FROM Cargas', fetch='one')
    peso_total = peso_total['sum'] if (IS_POSTGRES and peso_total) else (peso_total[0] if peso_total and peso_total[0] else 0)
    
    valor_total = db_execute(conn, 'SELECT SUM(Valor_Carga) FROM Cargas', fetch='one')
    valor_total = valor_total['sum'] if (IS_POSTGRES and valor_total) else (valor_total[0] if valor_total and valor_total[0] else 0)
    
    distancia_promedio = db_execute(conn, 'SELECT AVG(Distancia) FROM Rutas', fetch='one')
    distancia_promedio = distancia_promedio['avg'] if (IS_POSTGRES and distancia_promedio) else (distancia_promedio[0] if distancia_promedio and distancia_promedio[0] else 0)
    
    distancia_total = db_execute(conn, 'SELECT SUM(Distancia) FROM Rutas', fetch='one')
    distancia_total = distancia_total['sum'] if (IS_POSTGRES and distancia_total) else (distancia_total[0] if distancia_total and distancia_total[0] else 0)
    
    costo_total = db_execute(conn, 'SELECT SUM(Costo_Transporte) FROM Rutas', fetch='one')
    costo_total = costo_total['sum'] if (IS_POSTGRES and costo_total) else (costo_total[0] if costo_total and costo_total[0] else 0)
    
    # --- Charts ---
    cargas_raw = db_execute(conn, 'SELECT Tipo_Carga, COUNT(*) as cant FROM Cargas GROUP BY Tipo_Carga ORDER BY cant DESC', fetch='all')
    if IS_POSTGRES:
        chart_cargas = {'labels': [r['tipo_carga'] for r in cargas_raw], 'values': [r['cant'] for r in cargas_raw]}
    else:
        chart_cargas = {'labels': [r['Tipo_Carga'] for r in cargas_raw], 'values': [r['cant'] for r in cargas_raw]}

    valor_raw = db_execute(conn, 'SELECT Tipo_Carga, SUM(Valor_Carga) as total FROM Cargas GROUP BY Tipo_Carga ORDER BY total DESC', fetch='all')
    if IS_POSTGRES:
        chart_valor_categoria = {'labels': [r['tipo_carga'] for r in valor_raw], 'values': [r['total'] for r in valor_raw]}
    else:
        chart_valor_categoria = {'labels': [r['Tipo_Carga'] for r in valor_raw], 'values': [r['total'] for r in valor_raw]}

    rutas_costo = db_execute(conn, 'SELECT Destino, Costo_Transporte FROM Rutas ORDER BY Costo_Transporte DESC LIMIT 5', fetch='all')
    if IS_POSTGRES:
        chart_rutas = {'labels': [r['destino'] for r in rutas_costo], 'values': [r['costo_transporte'] for r in rutas_costo]}
    else:
        chart_rutas = {'labels': [r['Destino'] for r in rutas_costo], 'values': [r['Costo_Transporte'] for r in rutas_costo]}

    if IS_POSTGRES:
        rutas_dist = db_execute(conn, "SELECT Origen || ' → ' || Destino as ruta, Distancia FROM Rutas ORDER BY Distancia DESC LIMIT 8", fetch='all')
        chart_dist_rutas = {'labels': [r['ruta'] for r in rutas_dist], 'values': [r['distancia'] for r in rutas_dist]}
    else:
        rutas_dist = db_execute(conn, 'SELECT Origen || " → " || Destino as ruta, Distancia FROM Rutas ORDER BY Distancia DESC LIMIT 8', fetch='all')
        chart_dist_rutas = {'labels': [r['ruta'] for r in rutas_dist], 'values': [r['Distancia'] for r in rutas_dist]}

    clientes_cargas = db_execute(conn, '''
        SELECT c.Nombre, COUNT(ca.ID_Carga) as cant 
        FROM Clientes c 
        LEFT JOIN Cargas ca ON c.ID_Cliente = ca.ID_Cliente 
        GROUP BY c.Nombre 
        ORDER BY cant DESC LIMIT 6
    ''', fetch='all')
    if IS_POSTGRES:
        chart_clientes_cargas = {'labels': [r['nombre'] for r in clientes_cargas], 'values': [r['cant'] for r in clientes_cargas]}
    else:
        chart_clientes_cargas = {'labels': [r['Nombre'] for r in clientes_cargas], 'values': [r['cant'] for r in clientes_cargas]}

    datos_tabla = []
    columnas_tabla = []
    total_records = 0
    moneda_indices = []
    numero_indices = []
    
    if tipo == 'clientes':
        total_records = db_execute(conn, 'SELECT COUNT(*) FROM Clientes', fetch='count')
        cursor = db_execute_raw(conn, 'SELECT ID_Cliente AS id, Nombre, Email, Telefono FROM Clientes LIMIT %s OFFSET %s', (per_page, offset))
        columnas_tabla = ["Cliente", "Email", "Teléfono"]
    elif tipo == 'cargas':
        total_records = db_execute(conn, 'SELECT COUNT(*) FROM Cargas', fetch='count')
        cursor = db_execute_raw(conn, 'SELECT ID_Carga AS id, Tipo_Carga, Peso, Valor_Carga FROM Cargas LIMIT %s OFFSET %s', (per_page, offset))
        columnas_tabla = ["Tipo de Carga", "Peso (kg)", "Valor ($)"]
        numero_indices = [1]
        moneda_indices = [2]
    else:
        total_records = db_execute(conn, 'SELECT COUNT(*) FROM Rutas', fetch='count')
        cursor = db_execute_raw(conn, 'SELECT ID_Ruta AS id, Origen, Destino, Distancia, Costo_Transporte FROM Rutas LIMIT %s OFFSET %s', (per_page, offset))
        columnas_tabla = ["Origen", "Destino", "Distancia", "Costo"]
        numero_indices = [2]
        moneda_indices = [3]
    datos_tabla = [list(row) for row in cursor.fetchall()]
    total_pages = (total_records + per_page - 1) // per_page
    
    rutas_mapa = []
    if tipo == 'rutas':
        for row in datos_tabla[:20]:
            rutas_mapa.append({
                'id': row[0],
                'origen': row[1],
                'destino': row[2],
                'distancia': row[3],
                'costo': row[4]
            })
    conn.close()

    return render_template('operaciones.html', 
                           vista='operaciones', tipo=tipo,
                           chart_cargas=json.dumps(chart_cargas),
                           chart_rutas=json.dumps(chart_rutas),
                           chart_valor_categoria=json.dumps(chart_valor_categoria),
                           chart_dist_rutas=json.dumps(chart_dist_rutas),
                           chart_clientes_cargas=json.dumps(chart_clientes_cargas),
                           total_rutas=total_rutas, total_cargas=total_cargas,
                           total_clientes=total_clientes,
                           peso_total=peso_total, valor_total=valor_total,
                           distancia_promedio=distancia_promedio,
                           distancia_total=distancia_total, costo_total=costo_total,
                           datos=datos_tabla, columnas=columnas_tabla,
                           moneda_indices=moneda_indices, numero_indices=numero_indices,
                           rutas_mapa=rutas_mapa,
                           page=page, total_pages=total_pages, total_records=total_records)

#--- PAGINA COMERCIAL ---
@app.route('/gestion_comercial')
def gestion_comercial():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    mes_filtro = request.args.get('mes')
    anio_filtro = request.args.get('anio')
    trimestre_filtro = request.args.get('trimestre')
    conn = get_db_connection()

    conditions = []
    params = []
    
    if mes_filtro and anio_filtro:
        conditions.append("Fecha LIKE %s")
        params.append(f"{anio_filtro}-{mes_filtro}%")
    elif mes_filtro:
        conditions.append("substr(Fecha,1,4) = %s")
        params.append("2024")
        conditions.append("substr(Fecha,6,2) = %s")
        params.append(mes_filtro)
    elif anio_filtro:
        conditions.append("Fecha LIKE %s")
        params.append(f"{anio_filtro}%")
    
    if trimestre_filtro:
        trimestre_meses = {'1': ('01','02','03'), '2': ('04','05','06'), '3': ('07','08','09'), '4': ('10','11','12')}
        if trimestre_filtro in trimestre_meses:
            meses_t = trimestre_meses[trimestre_filtro]
            placeholders = ','.join(['%s' for _ in meses_t])
            conditions.append(f"substr(Fecha,6,2) IN ({placeholders})")
            params.extend(meses_t)
    
    query_where = "WHERE " + " AND ".join(conditions) if conditions else ""
    params = tuple(params)

    # --- KPIs principales ---
    row_ing = db_execute(conn, f'SELECT SUM(Monto) FROM Facturas {query_where}', params if params else None, fetch='one')
    ingresos = row_ing['sum'] if (IS_POSTGRES and row_ing) else (row_ing[0] if row_ing and row_ing[0] else 0)
    
    row_gas = db_execute(conn, f'SELECT SUM(Monto) FROM Gastos {query_where}', params if params else None, fetch='one')
    gastos = row_gas['sum'] if (IS_POSTGRES and row_gas) else (row_gas[0] if row_gas and row_gas[0] else 0)
    
    utilidad = ingresos - gastos
    margen = (utilidad / ingresos * 100) if ingresos > 0 else 0
    
    total_facturas = db_execute(conn, f'SELECT COUNT(*) FROM Facturas {query_where}', params if params else None, fetch='count')
    
    if query_where:
        pagadas_params = params + ("Pagada",) if params else ("Pagada",)
        total_facturas_pagadas = db_execute(conn, f'SELECT COUNT(*) FROM Facturas {query_where} AND Estado=%s', pagadas_params, fetch='count')
    else:
        total_facturas_pagadas = db_execute(conn, "SELECT COUNT(*) FROM Facturas WHERE Estado='Pagada'", fetch='count')
    
    total_gastos_reg = db_execute(conn, f'SELECT COUNT(*) FROM Gastos {query_where}', params if params else None, fetch='count')
    avg_ticket = (ingresos / total_facturas) if total_facturas > 0 else 0
    
    # --- Crecimiento de ingresos ---
    crecimiento_ingresos = 0
    if mes_filtro and anio_filtro:
        mes_anterior = f"{int(mes_filtro)-1:02d}" if int(mes_filtro) > 1 else None
        if mes_anterior:
            ing_mes_ant = db_execute(conn, 'SELECT SUM(Monto) FROM Facturas WHERE Fecha LIKE %s', (f"{anio_filtro}-{mes_anterior}%",), fetch='one')
            ing_mes_ant = ing_mes_ant['sum'] if (IS_POSTGRES and ing_mes_ant) else (ing_mes_ant[0] if ing_mes_ant and ing_mes_ant[0] else 0)
            crecimiento_ingresos = ((ingresos - ing_mes_ant) / ing_mes_ant * 100) if ing_mes_ant > 0 else 0
    elif mes_filtro:
        mes_anterior = f"{int(mes_filtro)-1:02d}" if int(mes_filtro) > 1 else None
        if mes_anterior:
            ing_mes_ant = db_execute(conn, "SELECT SUM(Monto) FROM Facturas WHERE substr(Fecha,1,4) = '2024' AND substr(Fecha,6,2) = %s", (mes_anterior,), fetch='one')
            ing_mes_ant = ing_mes_ant['sum'] if (IS_POSTGRES and ing_mes_ant) else (ing_mes_ant[0] if ing_mes_ant and ing_mes_ant[0] else 0)
            crecimiento_ingresos = ((ingresos - ing_mes_ant) / ing_mes_ant * 100) if ing_mes_ant > 0 else 0
    else:
        meses_data = db_execute(conn, '''
            SELECT substr(Fecha,1,7) as mes, SUM(Monto) as total 
            FROM Facturas GROUP BY mes ORDER BY mes DESC LIMIT 2
        ''', fetch='all')
        if len(meses_data) >= 2:
            t0 = meses_data[0]['total'] if IS_POSTGRES else meses_data[0]['total']
            t1 = meses_data[1]['total'] if IS_POSTGRES else meses_data[1]['total']
            crecimiento_ingresos = ((t0 - t1) / t1 * 100) if t1 > 0 else 0

    # --- Charts ---
    cobranza = db_execute(conn, f'SELECT Estado, SUM(Monto) as total FROM Facturas {query_where} GROUP BY Estado', params if params else None, fetch='all')
    if IS_POSTGRES:
        chart_cobranza = {'labels': [r['estado'] for r in cobranza], 'values': [r['total'] for r in cobranza]}
    else:
        chart_cobranza = {'labels': [r['Estado'] for r in cobranza], 'values': [r['total'] for r in cobranza]}

    top_clientes = db_execute(conn, f'''
        SELECT c.Nombre, SUM(f.Monto) as total FROM Facturas f 
        JOIN Clientes c ON f.ID_Cliente = c.ID_Cliente 
        {query_where} GROUP BY c.Nombre ORDER BY total DESC LIMIT 6
    ''', params if params else None, fetch='all')
    if IS_POSTGRES:
        chart_top_clientes = {'labels': [r['nombre'] for r in top_clientes], 'values': [r['total'] for r in top_clientes]}
    else:
        chart_top_clientes = {'labels': [r['Nombre'] for r in top_clientes], 'values': [r['total'] for r in top_clientes]}

    ingresos_mensuales = db_execute(conn, '''
        SELECT substr(Fecha,1,7) as mes, SUM(Monto) as total 
        FROM Facturas GROUP BY mes ORDER BY mes
    ''', fetch='all')
    gastos_mensuales = db_execute(conn, '''
        SELECT substr(Fecha,1,7) as mes, SUM(Monto) as total 
        FROM Gastos GROUP BY mes ORDER BY mes
    ''', fetch='all')
    
    meses_dict = {}
    for r in ingresos_mensuales:
        m = r['mes'] if IS_POSTGRES else r['mes']
        t = r['total'] if IS_POSTGRES else r['total']
        meses_dict[m] = {'ingresos': t, 'gastos': 0}
    for r in gastos_mensuales:
        m = r['mes'] if IS_POSTGRES else r['mes']
        t = r['total'] if IS_POSTGRES else r['total']
        if m in meses_dict:
            meses_dict[m]['gastos'] = t
        else:
            meses_dict[m] = {'ingresos': 0, 'gastos': t}
    
    meses_ordenados = sorted(meses_dict.keys())
    meses_nombres_corto = {'01':'Ene','02':'Feb','03':'Mar','04':'Abr','05':'May','06':'Jun','07':'Jul','08':'Ago','09':'Sep','10':'Oct','11':'Nov','12':'Dic'}
    chart_trend = {
        'labels': [meses_nombres_corto.get(m.split('-')[1], m.split('-')[1]) for m in meses_ordenados],
        'ingresos': [meses_dict[m]['ingresos'] for m in meses_ordenados],
        'gastos': [meses_dict[m]['gastos'] for m in meses_ordenados]
    }

    gastos_cat = db_execute(conn, '''
        SELECT Categoria, SUM(Monto) as total 
        FROM Gastos GROUP BY Categoria ORDER BY total DESC
    ''', fetch='all')
    if IS_POSTGRES:
        chart_gastos_cat = {'labels': [r['categoria'] for r in gastos_cat], 'values': [r['total'] for r in gastos_cat]}
    else:
        chart_gastos_cat = {'labels': [r['Categoria'] for r in gastos_cat], 'values': [r['total'] for r in gastos_cat]}

    margenes_mensuales = []
    for m in meses_ordenados:
        ing = meses_dict[m]['ingresos']
        gas = meses_dict[m]['gastos']
        util = ing - gas
        mar = (util / ing * 100) if ing > 0 else 0
        margenes_mensuales.append({'mes': m, 'margen': round(mar, 1)})
    
    chart_margenes = {
        'labels': [f"{meses_nombres_corto.get(m['mes'].split('-')[1], m['mes'])}" for m in margenes_mensuales],
        'values': [m['margen'] for m in margenes_mensuales],
        'utilidad': [meses_dict[m['mes']]['ingresos'] - meses_dict[m['mes']]['gastos'] for m in margenes_mensuales]
    }

    facturas_recientes = db_execute(conn, f'''
        SELECT f.ID_Factura, c.Nombre, f.Monto, f.Estado, f.Fecha
        FROM Facturas f JOIN Clientes c ON f.ID_Cliente = c.ID_Cliente
        {query_where} ORDER BY f.Fecha DESC LIMIT 5
    ''', params if params else None, fetch='all')
    if not IS_POSTGRES:
        facturas_recientes = [dict(r) for r in facturas_recientes]
    
    gastos_recientes = db_execute(conn, f'''
        SELECT ID_Gasto, Categoria, Monto, Proveedor, Estado, Fecha
        FROM Gastos {query_where} ORDER BY Fecha DESC LIMIT 5
    ''', params if params else None, fetch='all')
    if not IS_POSTGRES:
        gastos_recientes = [dict(r) for r in gastos_recientes]

    meses_nombres = [("01", "Enero"), ("02", "Febrero"), ("03", "Marzo"), ("04", "Abril"), ("05", "Mayo"), ("06", "Junio"), 
                     ("07", "Julio"), ("08", "Agosto"), ("09", "Septiembre"), ("10", "Octubre"), ("11", "Noviembre"), ("12", "Diciembre")]

    conn.close()
    
    return render_template('gestion_comercial.html', 
        vista='comercial', 
        stats={
            'ingresos': ingresos, 'gastos': gastos, 'utilidad': utilidad, 'margen': margen,
            'total_facturas': total_facturas, 'total_facturas_pagadas': total_facturas_pagadas,
            'total_gastos': total_gastos_reg, 'avg_ticket': avg_ticket,
            'crecimiento_ingresos': round(crecimiento_ingresos, 1)
        },
        chart_cobranza=json.dumps(chart_cobranza), 
        chart_top_clientes=json.dumps(chart_top_clientes),
        chart_trend=json.dumps(chart_trend),
        chart_gastos_cat=json.dumps(chart_gastos_cat),
        chart_margenes=json.dumps(chart_margenes),
        facturas_recientes=facturas_recientes,
        gastos_recientes=gastos_recientes,
        mes_actual=mes_filtro, 
        anio_actual=anio_filtro,
        trimestre_actual=trimestre_filtro,
        meses=meses_nombres
    )
            
#--- BOTON PARA EXPORTAR INFORMACION A UN EXCEL ---
@app.route('/exportar_comercial')
def exportar_comercial():
    mes_filtro = request.args.get('mes')
    conn = get_db_connection()
    query_where = "WHERE Fecha LIKE %s" if mes_filtro else ""
    params = (f"2024-{mes_filtro}%",) if mes_filtro else None

    q_fac, p_fac = sql_compat(f"SELECT * FROM Facturas {query_where}", params)
    q_gas, p_gas = sql_compat(f"SELECT * FROM Gastos {query_where}", params)
    df_fac = pd.read_sql_query(q_fac, conn, params=p_fac)
    df_gas = pd.read_sql_query(q_gas, conn, params=p_gas)
    
    resumen_data = {
        'Concepto': ['Total Ingresos', 'Total Gastos', 'Utilidad Neta', 'Margen %'],
        'Valor': [df_fac['Monto'].sum(), df_gas['Monto'].sum(), df_fac['Monto'].sum() - df_gas['Monto'].sum(), 
                  ((df_fac['Monto'].sum() - df_gas['Monto'].sum()) / df_fac['Monto'].sum() * 100) if df_fac['Monto'].sum() > 0 else 0]
    }
    df_res = pd.DataFrame(resumen_data)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_res.to_excel(writer, sheet_name='RESUMEN_FINANCIERO', index=False)
        df_fac.to_excel(writer, sheet_name='INGRESOS', index=False)
        df_gas.to_excel(writer, sheet_name='GASTOS', index=False)
    
    conn.close()
    output.seek(0)
    return send_file(output, download_name=f"Balance_{mes_filtro or 'Anual'}.xlsx", as_attachment=True)

# --- NOTIFICACIONES DEL SISTEMA ---
def crear_notificacion(tipo, titulo, mensaje, icono='bell', usuario_id=None):
    if usuario_id is None:
        usuario_id = session.get('user_id')
    if not usuario_id:
        return
    try:
        conn = get_db_connection()
        db_execute(conn,
            'INSERT INTO Notificaciones (ID_Usuario, Tipo, Titulo, Mensaje, Icono) VALUES (%s, %s, %s, %s, %s)',
            (usuario_id, tipo, titulo, mensaje, icono), fetch='none'
        )
        conn.close()
    except Exception as e:
        print(f"Error creando notificación: {e}")

def _ensure_notificaciones_table():
    """Ensures Notificaciones table exists (for PostgreSQL migrations)."""
    if not IS_POSTGRES:
        return
    try:
        conn = get_db_connection()
        db_execute(conn, '''
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
            )
        ''', fetch='none')
        conn.close()
    except Exception as e:
        print(f"Error asegurando tabla Notificaciones: {e}")

def _ensure_configuracion_table():
    """Ensures Configuracion table exists (for PostgreSQL migrations)."""
    if not IS_POSTGRES:
        return
    try:
        conn = get_db_connection()
        db_execute(conn, '''
            CREATE TABLE IF NOT EXISTS Configuracion (
                ID_Config SERIAL PRIMARY KEY,
                ID_Usuario INTEGER,
                Clave TEXT NOT NULL,
                Valor TEXT NOT NULL,
                UNIQUE(ID_Usuario, Clave),
                FOREIGN KEY (ID_Usuario) REFERENCES Usuario (IDUsuario)
            )
        ''', fetch='none')
        conn.close()
    except Exception as e:
        print(f"Error asegurando tabla Configuracion: {e}")

@app.before_request
def before_request_handler():
    if not hasattr(app, '_db_migrated'):
        if IS_POSTGRES:
            _ensure_notificaciones_table()
            _ensure_configuracion_table()
            ensure_all_tables()
        elif not os.environ.get('VERCEL'):
            from database import init_db
            db_path = os.path.join(base_dir, 'logistica.db')
            if not os.path.exists(db_path):
                init_db()
            _ensure_notificaciones_table()
            _ensure_configuracion_table()
        app._db_migrated = True

@app.route('/api/notificaciones', methods=['GET'])
def api_get_notificaciones():
    if 'user_id' not in session:
        return jsonify({'error': 'No autenticado'}), 401
    conn = get_db_connection()
    notifs = db_execute(conn,
        'SELECT ID_Notificacion, Tipo, Titulo, Mensaje, Icono, Leida, Fecha_Creacion FROM Notificaciones WHERE ID_Usuario = %s ORDER BY Fecha_Creacion DESC LIMIT 50',
        (session['user_id'],), fetch='all'
    )
    no_leidas = db_execute(conn,
        'SELECT COUNT(*) FROM Notificaciones WHERE ID_Usuario = %s AND Leida = 0',
        (session['user_id'],), fetch='count'
    )
    conn.close()
    return jsonify({
        'notificaciones': notifs,
        'no_leidas': no_leidas
    })

@app.route('/api/notificaciones/<int:notif_id>/leer', methods=['POST'])
def api_mark_read(notif_id):
    if 'user_id' not in session:
        return jsonify({'error': 'No autenticado'}), 401
    conn = get_db_connection()
    db_execute(conn,
        'UPDATE Notificaciones SET Leida = 1 WHERE ID_Notificacion = %s AND ID_Usuario = %s',
        (notif_id, session['user_id']), fetch='none'
    )
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/notificaciones/leer-todas', methods=['POST'])
def api_mark_all_read():
    if 'user_id' not in session:
        return jsonify({'error': 'No autenticado'}), 401
    conn = get_db_connection()
    db_execute(conn,
        'UPDATE Notificaciones SET Leida = 1 WHERE ID_Usuario = %s AND Leida = 0',
        (session['user_id'],), fetch='none'
    )
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/configuracion', methods=['GET'])
def api_get_configuracion():
    if 'user_id' not in session:
        return jsonify({'error': 'No autenticado'}), 401
    conn = get_db_connection()
    config_rows = db_execute(conn,
        'SELECT Clave, Valor FROM Configuracion WHERE ID_Usuario = %s', (session['user_id'],), fetch='all'
    )
    conn.close()
    if IS_POSTGRES:
        config = {row['clave']: row['valor'] for row in config_rows}
    else:
        config = {row['Clave']: row['Valor'] for row in config_rows}
    defaults = {
        'tema': 'dark', 'sidebar_colapsado': 'false', 'animaciones': 'true',
        'notif_upload': 'true', 'notif_eliminar': 'true', 'notif_registro': 'true',
        'filas_tabla': '10'
    }
    for k, v in defaults.items():
        if k not in config:
            config[k] = v
    return jsonify(config)

@app.route('/api/notificaciones/limpiar', methods=['POST'])
def api_clear_notifications():
    if 'user_id' not in session:
        return jsonify({'error': 'No autenticado'}), 401
    conn = get_db_connection()
    db_execute(conn,
        'DELETE FROM Notificaciones WHERE ID_Usuario = %s AND Leida = 1',
        (session['user_id'],), fetch='none'
    )
    conn.close()
    return jsonify({'ok': True})

def db_execute_safe(conn, query, params=None, fetch='all', default=None):
    """Execute a query, returning default value on error (e.g. missing table)."""
    try:
        return db_execute(conn, query, params, fetch)
    except Exception:
        return default

def sql_table_exists(conn, table_name):
    """Check if a table exists in the database."""
    try:
        cursor = conn.cursor()
        if IS_POSTGRES:
            cursor.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = %s)", (table_name,))
        else:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        return cursor.fetchone() is not None
    except Exception:
        return False

def ensure_all_tables():
    """Creates missing tables in PostgreSQL (Supabase)."""
    if not IS_POSTGRES:
        return
    try:
        conn = get_db_connection()
        db_execute(conn, '''
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
        ''', fetch='none')
        db_execute(conn, '''
            CREATE TABLE IF NOT EXISTS Vehiculos (
                ID_Vehiculo TEXT PRIMARY KEY,
                Marca TEXT,
                Modelo TEXT,
                Anio INTEGER,
                Placa TEXT UNIQUE,
                Tipo_Vehiculo TEXT,
                Capacidad_Carga REAL
            )
        ''', fetch='none')
        db_execute(conn, '''
            CREATE TABLE IF NOT EXISTS Rutas (
                ID_Ruta TEXT PRIMARY KEY,
                Origen TEXT,
                Destino TEXT,
                Distancia REAL,
                Tiempo_Entrega TEXT,
                Costo_Transporte REAL
            )
        ''', fetch='none')
        db_execute(conn, '''
            CREATE TABLE IF NOT EXISTS Clientes (
                ID_Cliente TEXT PRIMARY KEY,
                Nombre TEXT NOT NULL,
                Direccion TEXT,
                Telefono TEXT,
                Email TEXT
            )
        ''', fetch='none')
        db_execute(conn, '''
            CREATE TABLE IF NOT EXISTS Cargas (
                ID_Carga TEXT PRIMARY KEY,
                Tipo_Carga TEXT,
                Peso REAL,
                Volumen REAL,
                Valor_Carga REAL,
                ID_Ruta TEXT,
                FOREIGN KEY (ID_Ruta) REFERENCES Rutas (ID_Ruta)
            )
        ''', fetch='none')
        db_execute(conn, '''
            CREATE TABLE IF NOT EXISTS Facturas (
                ID_Factura TEXT PRIMARY KEY,
                Fecha TEXT,
                ID_Cliente TEXT,
                Monto REAL,
                Estado TEXT,
                FOREIGN KEY (ID_Cliente) REFERENCES Clientes (ID_Cliente)
            )
        ''', fetch='none')
        db_execute(conn, '''
            CREATE TABLE IF NOT EXISTS Proveedores (
                ID_Proveedor TEXT PRIMARY KEY,
                Nombre TEXT,
                Direccion TEXT,
                Telefono TEXT,
                Email TEXT
            )
        ''', fetch='none')
        db_execute(conn, '''
            CREATE TABLE IF NOT EXISTS Gastos (
                ID_Gasto TEXT PRIMARY KEY,
                Fecha TEXT,
                Categoria TEXT,
                Monto REAL,
                Proveedor TEXT,
                Estado TEXT
            )
        ''', fetch='none')
        conn.close()
    except Exception as e:
        print(f"Error ensuring tables: {e}")

@app.errorhandler(500)
def internal_error(e):
    return f"Error interno del servidor: {e}", 500

@app.errorhandler(404)
def not_found(e):
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
