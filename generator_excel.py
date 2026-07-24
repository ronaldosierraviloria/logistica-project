import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

# Configuración
n_datos = 100
n_rutas = 10  # Solo las 10 rutas más importantes

def generar_fechas(n, fecha_inicio=datetime(2022, 1, 1), fecha_fin=datetime(2024, 12, 31)):
    """Genera n fechas aleatorias distribuidas entre fecha_inicio y fecha_fin,
    cubriendo los 36 meses del rango (2022-2024)."""
    total_dias = (fecha_fin - fecha_inicio).days
    fechas = [fecha_inicio + timedelta(days=random.randint(0, total_dias)) for _ in range(n)]
    return sorted(f.strftime('%Y-%m-%d') for f in fechas)

# Listas extendidas para mayor variedad
nombres_base = ["Juan", "Maria", "Carlos", "Ana", "Luis", "Elena", "Pedro", "Sofia", "Diego", "Lucia", 
               "Andres", "Claudia", "Javier", "Beatriz", "Ricardo", "Marta", "Hugo", "Isabel", "Oscar", "Teresa",
               "Fernando", "Gabriela", "Miguel", "Valentina", "Santiago", "Camila", "Alejandro", "Daniela", "Jorge", "Natalia",
               "Sebastian", "Paula", "Rafael", "Lorena", "Adrian", "Carolina", "Victor", "Diana", "Emilio", "Juliana",
               "Mauricio", "Sara", "Andres", "Cecilia", "Esteban", "Viviana", "Felipe", "Lorena", "Gustavo", "Miriam",
               "Johana", "Cesar", "Patricia", "Alvaro", "Yolanda", "Camilo", "Clara", "Ramiro", "Natalia", "Hernan",
               "Liliana", "Julián", "Adriana", "Mauricio", "Silvia", "Nicolas", "Lorena", "Edgar", "Monica", "Julio",
               "Angela", "Pablo", "Rosa", "Estefania", "Guillermo", "Lina", "Alfredo", "Margarita", "Joaquin", "Carmen",
               "Sergio", "Ingrid", "Tomas", "Yenny", "Camila", "Dario", "Fabiola", "Leonardo", "Alicia", "Ramona"
               , "Jazmin", "Brayan", "Katherine", "Samuel", "Dulce", "Emilia", "Gonzalo", "Yesica", "Candelaria", "Renato"]
apellidos_base = ["Perez", "Gomez", "Rodriguez", "Lopez", "Martinez", "Cano", "Giraldo", "Castro", "Rios", "Vega",
                 "Torres", "Ruiz", "Morales", "Jimenez", "Sierra", "Pineda", "Herrera", "Suarez", "Vargas", "Blanco",
                 "Mendoza", "Ortega", "Silva", "Cruz", "Flores", "Leon", "Salazar", "Navarro", "Dominguez", "Rojas",
                 "Castillo", "Santos", "Duarte", "Cortes", "Mejia", "Valencia", "Acosta", "Camacho", "Palacios", "Montoya",
                 "Gallardo", "Figueroa", "Cabrera", "Arias", "Soto", "Quintero", "Pacheco", "Benitez", "Cardenas", "Mora", "Cisneros",
                 "Barrios", "Parra", "Salinas", "Tapia", "Campos", "Fuentes", "Rendon", "Zapata", "Velez", "Castañeda",
                 "Peña", "Carmona", "Valdez", "Barrera", "Orozco", "Lara", "Salgado", "Cueva", "Molina", "Rincon",
                 "Cordero", "Porras", "Sarmiento", "Daza", "Bermudez", "Cano", "Londoño", "Arango", "Gaitan", "Hernandez", "Lozada", "Maturana", "Naranjo", "Pastrana",
                 "Restrepo", "Trujillo", "Urbina", "Yepes", "Zambrano"]

# Ciudades usadas para direcciones/generales (se mantiene variedad amplia)
ciudades = ["Sincelejo", "Cartagena", "Barranquilla", "Monteria", "Medellin", "Bogota", "Santa Marta", "Cali", "Bucaramanga", "Pereira",
            "Manizales", "Armenia", "Neiva", "Ibagué", "Villavicencio", "Cúcuta", "Valledupar", "Popayán", "Tunja", "Florencia",
            "Yopal", "Quibdó", "Riohacha", "San Andrés", "Leticia", "Mitú", "Puerto Carreño"]

# Las 10 capitales de departamento más importantes de Colombia (mayor población / relevancia logística)
capitales_principales = ["Bogotá", "Medellín", "Cali", "Barranquilla", "Cartagena",
                          "Cúcuta", "Bucaramanga", "Pereira", "Santa Marta", "Ibagué"]

data_dict = {
    "Empleados": {
        "ID_Empleado": [f"EMP{i:03}" for i in range(1, n_datos + 1)],
        "Nombre": [random.choice(nombres_base) for _ in range(n_datos)],
        "Apellido": [random.choice(apellidos_base) for _ in range(n_datos)],
        "Direccion": [f"Calle {random.randint(1, 150)} # {random.randint(1, 80)}-{random.randint(1, 99)}" for _ in range(n_datos)],
        "Telefono": [f"3{random.randint(0, 2)}{random.randint(0, 9)}{random.randint(1000000, 9999999)}" for _ in range(n_datos)],
        "Salario": [1800000 + (random.randint(1, 40) * 50000) for _ in range(n_datos)],
        "Cargo": random.choices(["Conductor", "Logistica", "Despachador", "Administrativo", "Mantenimiento", "Ventas", "Gerente Proyecto"], k=n_datos),
        "Fecha_Ingreso": generar_fechas(n_datos)
    },
    "Vehiculos": {
        "ID_Vehiculo": [f"VEH{i:03}" for i in range(1, n_datos + 1)],
        "Marca": random.choices(["Kenworth", "Chevrolet", "Hino", "Foton", "International", "Volvo", "Scania", "Mercedes-Benz"], k=n_datos),
        "Modelo": [f"Mod-{random.randint(2015, 2025)}" for _ in range(n_datos)],
        "Anio": [random.randint(2015, 2025) for _ in range(n_datos)],
        "Placa": [f"{chr(random.randint(65, 90))}{chr(random.randint(65, 90))}{chr(random.randint(65, 90))}{random.randint(100, 999)}" for _ in range(n_datos)],
        "Tipo_Vehiculo": random.choices(["Tractocamion", "Turbo", "Sencillo", "Minimula", "Camioneta", "Furgon"], k=n_datos),
        "Capacidad_Carga": [round(random.uniform(1.5, 35.0), 1) for _ in range(n_datos)]
    },
    "Rutas": {
        "ID_Ruta": [f"RT{i:03}" for i in range(1, n_rutas + 1)],
        "Origen": [],
        "Destino": [],
        "Distancia": [random.randint(50, 1200) for _ in range(n_rutas)],
        "Tiempo_Entrega": [f"{random.randint(4, 48)} Horas" for _ in range(n_rutas)],
        "Costo_Transporte": [random.randint(250000, 2800000) for _ in range(n_rutas)]
    },
    "Clientes": {
        "ID_Cliente": [f"CLI{i:03}" for i in range(1, n_datos + 1)],
        "Nombre": [f"Empresa {random.choice(['Trans', 'Logi', 'Inter', 'Mega', 'Eco'])}{random.choice(['Sur', 'Envios', 'Global', 'Express', 'Pack'])} {i}" for i in range(1, n_datos + 1)],
        "Direccion": [f"Av. Industrial {random.randint(1, 200)} Bodega {random.randint(1, 50)}" for _ in range(n_datos)],
        "Telefono": [f"601{random.randint(2000000, 7999999)}" for _ in range(n_datos)],
        "Email": [f"contacto_cliente{i:03}@empresa.com.co" for i in range(1, n_datos + 1)]
    },
    "Cargas": {
        "ID_Carga": [f"CRG{i:03}" for i in range(1, n_datos + 1)],
        "Tipo_Carga": random.choices(["Perecederos", "Construccion", "Quimicos", "Muebles", "Textiles", "Maquinaria", "Electronicos"], k=n_datos),
        "Peso": [random.randint(50, 8000) for _ in range(n_datos)],
        "Volumen": [round(random.uniform(1.0, 50.0), 2) for _ in range(n_datos)],
        "Valor_Carga": [random.randint(5000000, 150000000) for _ in range(n_datos)],
        "ID_Ruta": [f"RT{random.randint(1, n_rutas):03}" for _ in range(n_datos)]
    },
    "Facturas": {
        "ID_Factura": [f"FAC{i:03}" for i in range(1, n_datos + 1)],
        "Fecha": generar_fechas(n_datos),
        "ID_Cliente": [f"CLI{random.randint(1, n_datos):03}" for _ in range(n_datos)],
        "Monto": [random.randint(800000, 12000000) for _ in range(n_datos)],
        "Estado": random.choices(["Pagada", "Pendiente", "Vencida"], weights=[0.6, 0.3, 0.1], k=n_datos)
    },
    "Proveedores": {
        "ID_Proveedor": [f"PRV{i:03}" for i in range(1, n_datos + 1)],
        "Nombre": [f"Suministros {random.choice(['Industriales', 'Logicos', 'Tecnicos', 'Automotrices'])} {i}" for i in range(1, n_datos + 1)],
        "Direccion": [f"Zona Franca Lote {random.randint(1, 100)}" for _ in range(n_datos)],
        "Telefono": [f"315{random.randint(1000000, 9999999)}" for _ in range(n_datos)],
        "Email": [f"ventas@proveedor{i:03}.com" for i in range(1, n_datos + 1)]
    },
    "Gastos": {
        "ID_Gasto": [f"GAS{i:03}" for i in range(1, n_datos + 1)],
        "Fecha": generar_fechas(n_datos, fecha_inicio=datetime(2022, 1, 1), fecha_fin=datetime(2024, 12, 31)),
        "Categoria": random.choices(["Combustible", "Mantenimiento", "Peajes", "Seguros", "Repuestos", "Viaticos", "Nomina"], k=n_datos),
        "Monto": [random.randint(50000, 3500000) for _ in range(n_datos)],
        "Proveedor": [f"Suministros {random.randint(1, n_datos):03}" for _ in range(n_datos)],
        "Estado": random.choices(["Pagado", "Pendiente"], weights=[0.8, 0.2], k=n_datos)
    }
}

# Generar las 10 rutas entre capitales principales, evitando que origen == destino
for _ in range(n_rutas):
    origen, destino = random.sample(capitales_principales, 2)
    data_dict["Rutas"]["Origen"].append(origen)
    data_dict["Rutas"]["Destino"].append(destino)

with pd.ExcelWriter("Datos_Logistica_100_Registros.xlsx") as writer:
    for sheet_name, data in data_dict.items():
        df = pd.DataFrame(data)
        df.to_excel(writer, sheet_name=sheet_name, index=False)

print(f"¡Éxito! Archivo 'Datos_Logistica_100_Registros.xlsx' generado con {n_datos} registros (10 rutas entre capitales principales, fechas 2022-2024).")