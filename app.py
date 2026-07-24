from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, jsonify
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import os
import pandas as pd
import sqlite3
import json
from datetime import datetime
import io
import xlsxwriter

base_dir = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, 
            template_folder=os.path.join(base_dir, 'FrontEnd', 'Templates'), 
            static_folder=os.path.join(base_dir, 'FrontEnd', 'Static'))
app.secret_key = "supersecretkey"

# --- CUSTOM JINJA2 FILTERS ---
@app.template_filter('format_currency')
def format_currency(value):
    """Formats a numeric value as currency: 1869484.0 -> $1,869,484"""
    if value is None:
        return '$0'
    try:
        val = float(value)
        return f'${int(val):,}'
    except (ValueError, TypeError):
        return str(value)

@app.template_filter('format_number')
def format_number(value):
    """Formats a numeric value with thousand separators: 1869484.0 -> 1,869,484"""
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

if os.environ.get('VERCEL'):
    UPLOAD_FOLDER = '/tmp'
else:
    UPLOAD_FOLDER = os.path.join('FrontEnd', 'Static', 'Uploads')

if not os.environ.get('VERCEL'):
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

DATABASE = 'logistica.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# --- DASHBOARD Y GESTIÓN DE TABLAS ---
@app.route('/')
def index():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    tabla_seleccionada = request.args.get('tabla')
    conn = get_db_connection()
    
    totales = {
        'empleados': conn.execute('SELECT COUNT(*) FROM Empleados').fetchone()[0],
        'vehiculos': conn.execute('SELECT COUNT(*) FROM Vehiculos').fetchone()[0],
        'rutas': conn.execute('SELECT COUNT(*) FROM Rutas').fetchone()[0],
        'clientes': conn.execute('SELECT COUNT(*) FROM Clientes').fetchone()[0]
    }

    if not tabla_seleccionada:
        ingresos_res = conn.execute('SELECT SUM(Monto) FROM Facturas WHERE Estado="Pagada"').fetchone()
        ingresos_total = ingresos_res[0] if ingresos_res[0] else 0

        cargas_raw = conn.execute('SELECT Tipo_Carga, COUNT(*) as cant FROM Cargas GROUP BY Tipo_Carga').fetchall()
        chart_cargas = {
            'labels': [row['Tipo_Carga'] for row in cargas_raw],
            'values': [row['cant'] for row in cargas_raw]
        }

        facturas_raw = conn.execute('SELECT Fecha, SUM(Monto) as total FROM Facturas GROUP BY Fecha ORDER BY Fecha ASC').fetchall()
        chart_ingresos = {
            'labels': [row['Fecha'] for row in facturas_raw],
            'values': [row['total'] for row in facturas_raw]
        }

        recientes = conn.execute('''
            SELECT f.ID_Factura, c.Nombre, f.Monto, f.Estado 
            FROM Facturas f 
            JOIN Clientes c ON f.ID_Cliente = c.ID_Cliente 
            ORDER BY f.ID_Factura DESC LIMIT 4
        ''').fetchall()

        excel_filename = session.get('excel_filename')
        excel_uploaded = excel_filename and os.path.exists(os.path.join(UPLOAD_FOLDER, excel_filename))

        conn.close()
        return render_template('index.html', vista ='dashboard',
                               es_dashboard=True, totales=totales, ingresos=ingresos_total,
                               recientes=recientes, chart_cargas=json.dumps(chart_cargas),
                               chart_ingresos=json.dumps(chart_ingresos), tabla_activa='Centro de Control',
                               excel_uploaded=excel_uploaded, excel_filename=excel_filename)

    else:
        datos_tabla = []
        columnas = []
        try:
            cursor = conn.execute(f'SELECT * FROM {tabla_seleccionada}')
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
            conn = sqlite3.connect(DATABASE)
            # Lista de tus 8 tablas
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
    """Exporta todos los datos de la base de datos a un archivo Excel."""
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = get_db_connection()
    tablas = ['Empleados', 'Vehiculos', 'Rutas', 'Clientes', 'Cargas', 'Facturas', 'Proveedores', 'Gastos']
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        for tabla in tablas:
            try:
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
        user = conn.execute('SELECT * FROM Usuario WHERE Correo = ?', (correo,)).fetchone()
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
            existe = conn.execute('SELECT IDUsuario FROM Usuario WHERE Correo = ?', (correo,)).fetchone()
            if existe:
                flash('El correo ya está registrado', 'warning')
                return redirect(url_for('register'))
                        
            conn.execute('''
                INSERT INTO Usuario (Nombres, Apellidos, Correo, Contrasena, Rol) 
                VALUES (?, ?, ?, ?, ?)
            ''', (nombres, apellidos, correo, hashed_password, rol))
            conn.commit()
            
            crear_notificacion('registro', 'Nuevo usuario registrado', f'{nombres} {apellidos} se ha registrado en el sistema con rol {rol}.', 'user-plus', conn.execute('SELECT IDUsuario FROM Usuario WHERE Correo = ?', (correo,)).fetchone()[0])
            
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
    user = conn.execute('SELECT * FROM Usuario WHERE IDUsuario = ?', (session['user_id'],)).fetchone()
    
    if request.method == 'POST':
        accion = request.form.get('accion')
        
        if accion == 'actualizar_perfil':
            nombres = request.form.get('nombres', '').strip()
            apellidos = request.form.get('apellidos', '').strip()
            correo = request.form.get('correo', '').strip()
            
            if nombres and apellidos and correo:
                try:
                    conn.execute('UPDATE Usuario SET Nombres = ?, Apellidos = ?, Correo = ? WHERE IDUsuario = ?',
                                (nombres, apellidos, correo, session['user_id']))
                    conn.commit()
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
                    conn.execute('UPDATE Usuario SET Contrasena = ? WHERE IDUsuario = ?',
                                (hashed, session['user_id']))
                    conn.commit()
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
                conn.execute('''
                    INSERT INTO Configuracion (ID_Usuario, Clave, Valor) VALUES (?, ?, ?)
                    ON CONFLICT(ID_Usuario, Clave) DO UPDATE SET Valor = excluded.Valor
                ''', (user_id, clave, valor))
            conn.commit()
            flash('Configuracion guardada correctamente', 'success')
        
        elif accion == 'limpiar_notificaciones':
            conn.execute('DELETE FROM Notificaciones WHERE ID_Usuario = ?', (user_id,))
            conn.commit()
            flash('Notificaciones eliminadas', 'success')
        
        elif accion == 'limpiar_db':
            if session.get('user_role') == 'Administrador':
                tablas = ['Empleados', 'Vehiculos', 'Rutas', 'Clientes', 'Cargas', 'Facturas', 'Proveedores', 'Gastos']
                for t in tablas:
                    conn.execute(f'DELETE FROM {t}')
                conn.commit()
                flash('Base de datos limpiada exitosamente', 'success')
            else:
                flash('Solo administradores pueden limpiar la base de datos', 'danger')
        
        conn.close()
        return redirect(url_for('configuracion'))
    
    # GET - cargar configuracion actual
    config_rows = conn.execute(
        'SELECT Clave, Valor FROM Configuracion WHERE ID_Usuario = ?', (user_id,)
    ).fetchall()
    config = {row['Clave']: row['Valor'] for row in config_rows}
    
    # Estadisticas de la base de datos
    stats = {}
    for t in ['Empleados', 'Vehiculos', 'Rutas', 'Clientes', 'Cargas', 'Facturas', 'Proveedores', 'Gastos']:
        stats[t] = conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
    max_count = max(stats.values()) if stats.values() else 1
    total_notifs = conn.execute('SELECT COUNT(*) FROM Notificaciones WHERE ID_Usuario = ?', (user_id,)).fetchone()[0]
    total_usuarios = conn.execute('SELECT COUNT(*) FROM Usuario').fetchone()[0]
    
    conn.close()
    
    # Aplicar configuracion actual a la sesion para el template
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
    cursor = conn.cursor()
    cursor.execute("SELECT Cargo, COUNT(*) FROM Empleados GROUP BY Cargo")
    res_emp = cursor.fetchall()
    chart_emp = {
        "labels": [row[0] for row in res_emp],
        "values": [row[1] for row in res_emp]
    }

    cursor.execute("SELECT Marca, COUNT(*) FROM Vehiculos GROUP BY Marca")
    res_veh = cursor.fetchall()
    chart_veh = {
        "labels": [row[0] for row in res_veh],
        "values": [row[1] for row in res_veh]
    }
    try:
        if tipo == 'personal':
            total_records = conn.execute('SELECT COUNT(*) FROM Empleados').fetchone()[0]
            cursor = conn.execute('SELECT ID_Empleado, Nombre, Apellido, Cargo, Telefono FROM Empleados LIMIT ? OFFSET ?', (per_page, offset)).fetchall()
            columnas_tabla = ["Nombre", "Apellido", "Cargo", "Teléfono"]
        else:
            total_records = conn.execute('SELECT COUNT(*) FROM Vehiculos').fetchone()[0]
            cursor = conn.execute('SELECT ID_Vehiculo, Placa, Marca, Modelo, Tipo_Vehiculo, Anio, Capacidad_Carga FROM Vehiculos LIMIT ? OFFSET ?', (per_page, offset)).fetchall()
            columnas_tabla = ["Placa", "Marca", "Modelo", "Tipo Vehículo", "Año","Capacidad De Carga"]
        
        datos_tabla = [list(row) for row in cursor]
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

    total_pages = (total_records + per_page - 1) // per_page
    
    # Column indices for number formatting (relative to fila[1:])
    numero_indices = []
    moneda_indices = []
    if tipo == 'vehiculos':
        numero_indices = [5]  # Capacidad_Carga
    
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
            conn.execute(f'DELETE FROM {tabla} WHERE {columna_id} = ?', (id,))
            conn.commit()
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
    total_rutas = conn.execute('SELECT COUNT(*) FROM Rutas').fetchone()[0]
    total_cargas = conn.execute('SELECT COUNT(*) FROM Cargas').fetchone()[0]
    total_clientes = conn.execute('SELECT COUNT(*) FROM Clientes').fetchone()[0]
    
    peso_total = conn.execute('SELECT SUM(Peso) FROM Cargas').fetchone()[0] or 0
    valor_total = conn.execute('SELECT SUM(Valor_Carga) FROM Cargas').fetchone()[0] or 0
    distancia_promedio = conn.execute('SELECT AVG(Distancia) FROM Rutas').fetchone()[0] or 0
    distancia_total = conn.execute('SELECT SUM(Distancia) FROM Rutas').fetchone()[0] or 0
    costo_total = conn.execute('SELECT SUM(Costo_Transporte) FROM Rutas').fetchone()[0] or 0
    
    # --- Charts: Volumen por Categoria ---
    cargas_raw = conn.execute('SELECT Tipo_Carga, COUNT(*) as cant FROM Cargas GROUP BY Tipo_Carga ORDER BY cant DESC').fetchall()
    chart_cargas = {
        'labels': [row['Tipo_Carga'] for row in cargas_raw],
        'values': [row['cant'] for row in cargas_raw]
    }

    # --- Charts: Valor por Categoria ---
    valor_raw = conn.execute('SELECT Tipo_Carga, SUM(Valor_Carga) as total FROM Cargas GROUP BY Tipo_Carga ORDER BY total DESC').fetchall()
    chart_valor_categoria = {
        'labels': [row['Tipo_Carga'] for row in valor_raw],
        'values': [row['total'] for row in valor_raw]
    }

    # --- Charts: Ranking Costos por Destino ---
    rutas_costo = conn.execute('SELECT Destino, Costo_Transporte FROM Rutas ORDER BY Costo_Transporte DESC LIMIT 5').fetchall()
    chart_rutas = {
        'labels': [row['Destino'] for row in rutas_costo],
        'values': [row['Costo_Transporte'] for row in rutas_costo]
    }

    # --- Charts: Distancia por Ruta (TOP 8) ---
    rutas_dist = conn.execute('SELECT Origen || " → " || Destino as ruta, Distancia FROM Rutas ORDER BY Distancia DESC LIMIT 8').fetchall()
    chart_dist_rutas = {
        'labels': [row['ruta'] for row in rutas_dist],
        'values': [row['Distancia'] for row in rutas_dist]
    }

    # --- Charts: Top Clientes por Cantidad de Cargas (para pestana clientes) ---
    clientes_cargas = conn.execute('''
        SELECT c.Nombre, COUNT(ca.ID_Carga) as cant 
        FROM Clientes c 
        LEFT JOIN Cargas ca ON 1=1 
        GROUP BY c.Nombre 
        ORDER BY cant DESC LIMIT 6
    ''').fetchall()
    chart_clientes_cargas = {
        'labels': [row['Nombre'] for row in clientes_cargas],
        'values': [row['cant'] for row in clientes_cargas]
    }

    datos_tabla = []
    columnas_tabla = []
    total_records = 0
    moneda_indices = []  # column indices (relative to fila[1:]) that are monetary
    numero_indices = []  # column indices that are numeric (thousand-separated)
    
    if tipo == 'clientes':
        total_records = conn.execute('SELECT COUNT(*) FROM Clientes').fetchone()[0]
        cursor = conn.execute('SELECT ID_Cliente AS id, Nombre, Email, Telefono FROM Clientes LIMIT ? OFFSET ?', (per_page, offset)).fetchall()
        columnas_tabla = ["Cliente", "Email", "Teléfono"]
    elif tipo == 'cargas':
        total_records = conn.execute('SELECT COUNT(*) FROM Cargas').fetchone()[0]
        cursor = conn.execute('SELECT ID_Carga AS id, Tipo_Carga, Peso, Valor_Carga FROM Cargas LIMIT ? OFFSET ?', (per_page, offset)).fetchall()
        columnas_tabla = ["Tipo de Carga", "Peso (kg)", "Valor ($)"]
        numero_indices = [1]  # Peso (index in fila[1:])
        moneda_indices = [2]  # Valor_Carga
    else: # Rutas
        total_records = conn.execute('SELECT COUNT(*) FROM Rutas').fetchone()[0]
        cursor = conn.execute('SELECT ID_Ruta AS id, Origen, Destino, Distancia, Costo_Transporte FROM Rutas LIMIT ? OFFSET ?', (per_page, offset)).fetchall()
        columnas_tabla = ["Origen", "Destino", "Distancia", "Costo"]
        numero_indices = [2]  # Distancia (index in fila[1:])
        moneda_indices = [3]  # Costo_Transporte
    datos_tabla = [list(row) for row in cursor]
    total_pages = (total_records + per_page - 1) // per_page
    
    # Extract city pairs for the map (only when viewing rutas, max 20)
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

    # Build WHERE clause based on filters
    conditions = []
    params = []
    
    if mes_filtro and anio_filtro:
        conditions.append("Fecha LIKE ?")
        params.append(f"{anio_filtro}-{mes_filtro}%")
    elif mes_filtro:
        conditions.append("substr(Fecha,1,4) = ?")
        params.append("2024")
        conditions.append("substr(Fecha,6,2) = ?")
        params.append(mes_filtro)
    elif anio_filtro:
        conditions.append("Fecha LIKE ?")
        params.append(f"{anio_filtro}%")
    
    if trimestre_filtro:
        trimestre_meses = {'1': ('01','02','03'), '2': ('04','05','06'), '3': ('07','08','09'), '4': ('10','11','12')}
        if trimestre_filtro in trimestre_meses:
            meses_t = trimestre_meses[trimestre_filtro]
            placeholders = ','.join(['?' for _ in meses_t])
            conditions.append(f"substr(Fecha,6,2) IN ({placeholders})")
            params.extend(meses_t)
    
    query_where = "WHERE " + " AND ".join(conditions) if conditions else ""
    params = tuple(params)

    # --- KPIs principales ---
    ingresos = conn.execute(f'SELECT SUM(Monto) FROM Facturas {query_where}', params).fetchone()[0] or 0
    gastos = conn.execute(f'SELECT SUM(Monto) FROM Gastos {query_where}', params).fetchone()[0] or 0
    utilidad = ingresos - gastos
    margen = (utilidad / ingresos * 100) if ingresos > 0 else 0
    
    # KPIs adicionales
    total_facturas = conn.execute(f'SELECT COUNT(*) FROM Facturas {query_where}', params).fetchone()[0] or 0
    if query_where:
        total_facturas_pagadas = conn.execute(f'SELECT COUNT(*) FROM Facturas {query_where} AND Estado="Pagada"', params).fetchone()[0] or 0
    else:
        total_facturas_pagadas = conn.execute('SELECT COUNT(*) FROM Facturas WHERE Estado="Pagada"').fetchone()[0] or 0
    total_gastos_reg = conn.execute(f'SELECT COUNT(*) FROM Gastos {query_where}', params).fetchone()[0] or 0
    avg_ticket = (ingresos / total_facturas) if total_facturas > 0 else 0
    
    # --- Crecimiento de ingresos (comparar mes actual vs mes anterior) ---
    if mes_filtro and anio_filtro:
        mes_anterior = f"{int(mes_filtro)-1:02d}" if int(mes_filtro) > 1 else None
        if mes_anterior:
            ing_mes_act = ingresos
            ing_mes_ant = conn.execute('SELECT SUM(Monto) FROM Facturas WHERE Fecha LIKE ?', (f"{anio_filtro}-{mes_anterior}%",)).fetchone()[0] or 0
            crecimiento_ingresos = ((ing_mes_act - ing_mes_ant) / ing_mes_ant * 100) if ing_mes_ant > 0 else 0
        else:
            crecimiento_ingresos = 0
    elif mes_filtro:
        mes_anterior = f"{int(mes_filtro)-1:02d}" if int(mes_filtro) > 1 else None
        if mes_anterior:
            ing_mes_act = ingresos
            ing_mes_ant = conn.execute('SELECT SUM(Monto) FROM Facturas WHERE substr(Fecha,1,4) = "2024" AND substr(Fecha,6,2) = ?', (mes_anterior,)).fetchone()[0] or 0
            crecimiento_ingresos = ((ing_mes_act - ing_mes_ant) / ing_mes_ant * 100) if ing_mes_ant > 0 else 0
        else:
            crecimiento_ingresos = 0
    else:
        # Anual: comparar ultimo mes completo vs penultimo
        meses_data = conn.execute('''
            SELECT substr(Fecha,1,7) as mes, SUM(Monto) as total 
            FROM Facturas GROUP BY mes ORDER BY mes DESC LIMIT 2
        ''').fetchall()
        if len(meses_data) >= 2:
            crecimiento_ingresos = ((meses_data[0]['total'] - meses_data[1]['total']) / meses_data[1]['total'] * 100) if meses_data[1]['total'] > 0 else 0
        else:
            crecimiento_ingresos = 0

    # --- Chart 1: Estado de Cartera (Doughnut) ---
    cobranza = conn.execute(f'SELECT Estado, SUM(Monto) as total FROM Facturas {query_where} GROUP BY Estado', params).fetchall()
    chart_cobranza = {'labels': [r['Estado'] for r in cobranza], 'values': [r['total'] for r in cobranza]}

    # --- Chart 2: Top Clientes por Ingresos (Barra horizontal) ---
    top_clientes = conn.execute(f'''
        SELECT c.Nombre, SUM(f.Monto) as total FROM Facturas f 
        JOIN Clientes c ON f.ID_Cliente = c.ID_Cliente 
        {query_where} GROUP BY c.Nombre ORDER BY total DESC LIMIT 6
    ''', params).fetchall()
    chart_top_clientes = {'labels': [r['Nombre'] for r in top_clientes], 'values': [r['total'] for r in top_clientes]}

    # --- Chart 3: Ingresos vs Gastos por Mes (Line chart) ---
    ingresos_mensuales = conn.execute('''
        SELECT substr(Fecha,1,7) as mes, SUM(Monto) as total 
        FROM Facturas GROUP BY mes ORDER BY mes
    ''').fetchall()
    gastos_mensuales = conn.execute('''
        SELECT substr(Fecha,1,7) as mes, SUM(Monto) as total 
        FROM Gastos GROUP BY mes ORDER BY mes
    ''').fetchall()
    
    # Merge data
    meses_dict = {}
    for r in ingresos_mensuales:
        meses_dict[r['mes']] = {'ingresos': r['total'], 'gastos': 0}
    for r in gastos_mensuales:
        if r['mes'] in meses_dict:
            meses_dict[r['mes']]['gastos'] = r['total']
        else:
            meses_dict[r['mes']] = {'ingresos': 0, 'gastos': r['total']}
    
    meses_ordenados = sorted(meses_dict.keys())
    meses_nombres_corto = {'01':'Ene','02':'Feb','03':'Mar','04':'Abr','05':'May','06':'Jun','07':'Jul','08':'Ago','09':'Sep','10':'Oct','11':'Nov','12':'Dic'}
    chart_trend = {
        'labels': [meses_nombres_corto.get(m.split('-')[1], m.split('-')[1]) for m in meses_ordenados],
        'ingresos': [meses_dict[m]['ingresos'] for m in meses_ordenados],
        'gastos': [meses_dict[m]['gastos'] for m in meses_ordenados]
    }

    # --- Chart 4: Gastos por Categoria (Doughnut) ---
    gastos_cat = conn.execute('''
        SELECT Categoria, SUM(Monto) as total 
        FROM Gastos GROUP BY Categoria ORDER BY total DESC
    ''').fetchall()
    chart_gastos_cat = {'labels': [r['Categoria'] for r in gastos_cat], 'values': [r['total'] for r in gastos_cat]}

    # --- Chart 5: Margenes Mensuales (Bar chart) ---
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

    # --- Tablas recientes (respetan filtro de mes) ---
    facturas_recientes = conn.execute(f'''
        SELECT f.ID_Factura, c.Nombre, f.Monto, f.Estado, f.Fecha
        FROM Facturas f JOIN Clientes c ON f.ID_Cliente = c.ID_Cliente
        {query_where} ORDER BY f.Fecha DESC LIMIT 5
    ''', params).fetchall()
    
    gastos_recientes = conn.execute(f'''
        SELECT ID_Gasto, Categoria, Monto, Proveedor, Estado, Fecha
        FROM Gastos {query_where} ORDER BY Fecha DESC LIMIT 5
    ''', params).fetchall()

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
    query_where = "WHERE Fecha LIKE ?" if mes_filtro else ""
    params = (f"2024-{mes_filtro}%",) if mes_filtro else ()

    df_fac = pd.read_sql_query(f"SELECT * FROM Facturas {query_where}", conn, params=params)
    df_gas = pd.read_sql_query(f"SELECT * FROM Gastos {query_where}", conn, params=params)
    
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
    """Crea una notificación en la BD para un evento del sistema."""
    if usuario_id is None:
        usuario_id = session.get('user_id')
    if not usuario_id:
        return
    try:
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO Notificaciones (ID_Usuario, Tipo, Titulo, Mensaje, Icono) VALUES (?, ?, ?, ?, ?)',
            (usuario_id, tipo, titulo, mensaje, icono)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error creando notificación: {e}")

def _ensure_notificaciones_table():
    """Asegura que la tabla Notificaciones exista (migración para DB existente)."""
    try:
        conn = get_db_connection()
        conn.execute('''
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
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error asegurando tabla Notificaciones: {e}")

def _ensure_configuracion_table():
    """Asegura que la tabla Configuracion exista (migración para DB existente)."""
    try:
        conn = get_db_connection()
        conn.execute('''
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
    except Exception as e:
        print(f"Error asegurando tabla Configuracion: {e}")

@app.before_request
def before_request_handler():
    """Ejecuta migraciones ligeras antes de cada request."""
    if not hasattr(app, '_db_migrated'):
        _ensure_notificaciones_table()
        _ensure_configuracion_table()
        app._db_migrated = True

@app.route('/api/notificaciones', methods=['GET'])
def api_get_notificaciones():
    """Obtiene las notificaciones del usuario actual."""
    if 'user_id' not in session:
        return jsonify({'error': 'No autenticado'}), 401
    conn = get_db_connection()
    notifs = conn.execute(
        'SELECT ID_Notificacion, Tipo, Titulo, Mensaje, Icono, Leida, Fecha_Creacion FROM Notificaciones WHERE ID_Usuario = ? ORDER BY Fecha_Creacion DESC LIMIT 50',
        (session['user_id'],)
    ).fetchall()
    no_leidas = conn.execute(
        'SELECT COUNT(*) FROM Notificaciones WHERE ID_Usuario = ? AND Leida = 0',
        (session['user_id'],)
    ).fetchone()[0]
    conn.close()
    return jsonify({
        'notificaciones': [dict(n) for n in notifs],
        'no_leidas': no_leidas
    })

@app.route('/api/notificaciones/<int:notif_id>/leer', methods=['POST'])
def api_mark_read(notif_id):
    """Marca una notificación como leída."""
    if 'user_id' not in session:
        return jsonify({'error': 'No autenticado'}), 401
    conn = get_db_connection()
    conn.execute(
        'UPDATE Notificaciones SET Leida = 1 WHERE ID_Notificacion = ? AND ID_Usuario = ?',
        (notif_id, session['user_id'])
    )
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/notificaciones/leer-todas', methods=['POST'])
def api_mark_all_read():
    """Marca todas las notificaciones como leídas."""
    if 'user_id' not in session:
        return jsonify({'error': 'No autenticado'}), 401
    conn = get_db_connection()
    conn.execute(
        'UPDATE Notificaciones SET Leida = 1 WHERE ID_Usuario = ? AND Leida = 0',
        (session['user_id'],)
    )
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/configuracion', methods=['GET'])
def api_get_configuracion():
    """Devuelve la configuracion del usuario como JSON (para sincronizar con localStorage)."""
    if 'user_id' not in session:
        return jsonify({'error': 'No autenticado'}), 401
    conn = get_db_connection()
    config_rows = conn.execute(
        'SELECT Clave, Valor FROM Configuracion WHERE ID_Usuario = ?', (session['user_id'],)
    ).fetchall()
    conn.close()
    config = {row['Clave']: row['Valor'] for row in config_rows}
    # Valores por defecto
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
    """Elimina todas las notificaciones leídas del usuario."""
    if 'user_id' not in session:
        return jsonify({'error': 'No autenticado'}), 401
    conn = get_db_connection()
    conn.execute(
        'DELETE FROM Notificaciones WHERE ID_Usuario = ? AND Leida = 1',
        (session['user_id'],)
    )
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

if __name__ == '__main__':
    app.run(debug=True)
