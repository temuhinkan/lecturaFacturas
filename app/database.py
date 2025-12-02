import sqlite3
import os
from typing import Any, List, Dict, Optional, Tuple
from datetime import datetime # AÑADIDO: Necesario para obtener la fecha/hora de inserción

# --- Definición de Excepción Personalizada ---
class DuplicateInvoiceError(Exception):
    """Excepción lanzada cuando se intenta insertar una factura duplicada."""
    pass
# ---------------------------------------------

DB_NAME = "facturas.db"

# --- Utilidad numérica (Necesaria para limpiar la entrada del usuario) ---
def _clean_numeric_value(value: Any) -> Optional[float]:
    """Limpia una cadena de texto para obtener un valor flotante."""
    if value is None or str(value).strip() == '':
        return None
    try:
        if isinstance(value, str):
            # Elimina separador de miles (punto) y reemplaza coma por punto decimal
            value = value.replace('.', '').replace(',', '.')
        return float(value)
    except (ValueError, TypeError):
        return None

# --- Funciones de la Base de Datos ---

def insert_default_fields():
    """Inserta los campos obligatorios y opcionales por defecto con su tipo de dato."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # [FIELD_NAME, IS_REQUIRED (1/0), DATA_TYPE, DESCRIPTION]
    fields_data: List[Tuple[str, int, str, str]] = [
        ('TIPO', 1, 'TEXT', 'Tipo de operación (COMPRA, VENTA)'),
        ('FECHA', 1, 'DATE', 'Fecha de la factura'),
        ('NUM_FACTURA', 1, 'TEXT', 'Número de factura'),
        ('EMISOR', 1, 'TEXT', 'Nombre del emisor'),
        ('CIF_EMISOR', 1, 'NIF/CIF', 'CIF/NIF del emisor'),
        ('CLIENTE', 1, 'TEXT', 'Nombre del cliente (nuestra empresa)'),
        ('CIF', 1, 'NIF/CIF', 'CIF/NIF del cliente (nuestro)'),
        ('IMPORTE', 1, 'FLOAT', 'Importe total'),
        ('BASE', 1, 'FLOAT', 'Base imponible'),
        ('IVA', 1, 'FLOAT', 'Impuesto de valor añadido'),
        ('TASAS', 1, 'FLOAT', 'Otros cargos o tasas'),
        ('MODELO', 0, 'TEXT', 'Modelo de vehículo/producto'), # Opcional
        ('MATRICULA', 0, 'TEXT', 'Matrícula de vehículo'),   # Opcional
    ]

    try:
        for name, req, dtype, desc in fields_data:
            cursor.execute("""
                INSERT OR IGNORE INTO extraction_fields (field_name, is_required, data_type, description)
                VALUES (?, ?, ?, ?)
            """, (name, req, dtype, desc))
        conn.commit()
    except Exception as e:
        print(f"Error al insertar campos por defecto: {e}")
    finally:
        conn.close()


def setup_database():
    """
    Configura la tabla de facturas si no existe y realiza la migración de esquema 
    añadiendo columnas faltantes (como log_data) sin perder datos existentes.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 1. Crear la tabla si no existe (con el esquema más reciente)
    # AÑADIDO: La columna 'procesado_en' (TEXT)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS processed_invoices (
            path TEXT PRIMARY KEY,
            file_name TEXT,
            tipo TEXT,
            fecha TEXT,
            numero_factura TEXT,
            emisor TEXT,
            cif_emisor TEXT,
            cliente TEXT,
            cif TEXT,
            modelo TEXT,
            matricula TEXT,
            base REAL,
            iva REAL,
            importe REAL,
            tasas REAL,
            is_validated INTEGER,
            log_data TEXT,
            procesado_en TEXT -- NUEVA COLUMNA,
            concepto TEXT,
            exportado TEXT       
        )
    """)
    conn.commit()
    
    # 2. Crear la tabla de extractores
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS extractors (
            extractor_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,       
            class_path TEXT NOT NULL,        
            is_enabled INTEGER DEFAULT 1     
        );
    """)

    # 3. Crear la tabla de definición de campos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS extraction_fields (
            field_id INTEGER PRIMARY KEY AUTOINCREMENT,
            field_name TEXT UNIQUE NOT NULL, 
            description TEXT,                
            data_type TEXT NOT NULL,         
            is_required INTEGER NOT NULL DEFAULT 1 
        );
    """)
    
    # 4. Crear la tabla de configuraciones de extracción
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS extractor_configurations (
            config_id INTEGER PRIMARY KEY AUTOINCREMENT,
            extractor_id INTEGER NOT NULL,    
            field_id INTEGER NOT NULL,        
            attempt_order INTEGER NOT NULL,
            type TEXT NOT NULL,          
            ref_text TEXT,               
            offset INTEGER,              
            segment TEXT,                
            value TEXT,                  
            line INTEGER,                
            UNIQUE (extractor_id, field_id, attempt_order),
            FOREIGN KEY (extractor_id) REFERENCES extractors(extractor_id),
            FOREIGN KEY (field_id) REFERENCES extraction_fields(field_id)
        );
    """)

    # 5. Insertar los campos maestros (DEBE EJECUTARSE DESPUÉS DE CREAR LA TABLA)
    insert_default_fields()

    # 6. Lógica de Migración (Añadir columnas faltantes si la tabla ya existía)
    
    # Columnas que sabemos que pudieron haber sido añadidas más tarde.
    # AÑADIDO: 'procesado_en' a la lista de columnas a revisar.
    REQUIRED_COLUMNS_TO_CHECK = {
        "tasas": "REAL",
        "log_data": "TEXT",
        "procesado_en": "TEXT",
        "concepto":"TEXT" ,
        "exportado":"TEXT" 
    }

    try:
        # Obtener las columnas existentes en la tabla
        cursor.execute("PRAGMA table_info(processed_invoices)")
        existing_columns = [info[1] for info in cursor.fetchall()]

        # Iterar y añadir columnas faltantes
        for column_name, column_type in REQUIRED_COLUMNS_TO_CHECK.items():
            if column_name not in existing_columns:
                print(f"MIGRACIÓN BBDD: Añadiendo columna faltante '{column_name}'...")
                # Comando que añade la columna sin modificar los datos existentes.
                cursor.execute(f"ALTER TABLE processed_invoices ADD COLUMN {column_name} {column_type}")
                conn.commit()
                
    except sqlite3.OperationalError as e:
        # Esto captura errores si la tabla está bloqueada o hay otro problema.
        print(f"ADVERTENCIA DE MIGRACIÓN: Falló el checkeo de esquema: {e}")
        conn.rollback()
        
    finally:
        conn.close()

def get_extractor_configuration(extractor_name: str) -> Dict[str, Any] | None:
    """
    Recupera la configuración de un extractor habilitado y la reconstruye en el formato de diccionario original.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    query = """
        SELECT 
            ef.field_name, 
            ec.type, ec.ref_text, ec.offset, ec.segment, ec.value, ec.line 
        FROM extractor_configurations ec
        JOIN extractors e ON ec.extractor_id = e.extractor_id
        JOIN extraction_fields ef ON ec.field_id = ef.field_id
        WHERE 
            e.name = ? AND e.is_enabled = 1
        ORDER BY 
            ef.field_name, ec.attempt_order
    """
    
    try:
        cursor.execute(query, (extractor_name,))
        rows = cursor.fetchall()
        
        if not rows:
            return None 

        extraction_mapping: Dict[str, List[Dict[str, Any]]] = {}
        
        for row in rows:
            field_name, config_type, ref_text, offset, segment, value, line = row
            
            config_attempt = {'type': config_type}
            
            # Reconstruir el diccionario (añadiendo solo campos relevantes con valor)
            if ref_text is not None: config_attempt['ref_text'] = ref_text
            if offset is not None: config_attempt['offset'] = offset
            if segment is not None: config_attempt['segment'] = segment
            if value is not None: config_attempt['value'] = value
            if line is not None: config_attempt['line'] = line
            
            if field_name not in extraction_mapping:
                extraction_mapping[field_name] = []
                
            extraction_mapping[field_name].append(config_attempt)
            
        return extraction_mapping
        
    except Exception as e:
        print(f"Error al recuperar la configuración de '{extractor_name}': {e}")
        return None
    finally:
        conn.close()

def check_duplicate_invoice(numero_factura: str, cif_emisor: str, exclude_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Verifica si una factura con el mismo número y CIF emisor ya existe en processed_invoices,
    excluyendo opcionalmente la factura actual por su path.
    
    Args:
        numero_factura: El número de factura a buscar.
        cif_emisor: El CIF o NIF del emisor a buscar.
        exclude_path: Si se proporciona, excluye el registro con este 'path' de la búsqueda.
        
    Returns:
        Una lista de diccionarios, donde cada diccionario representa una fila 
        encontrada (factura duplicada). La lista estará vacía si no se encuentran duplicados.
    """
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    results = []
    
    # ⚠️ MODIFICACIÓN: Construir la consulta y parámetros de forma dinámica
    sql = "SELECT * FROM processed_invoices WHERE cif_emisor=? AND numero_factura=?"
    params: List[Any] = [cif_emisor, numero_factura]
    
    if exclude_path:
        sql += " AND path != ?"
        params.append(exclude_path)
    
    try:
        # Ejecutar la consulta con los parámetros de forma segura
        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall()
        
        # Convertir las filas sqlite3.Row a diccionarios
        results = [dict(row) for row in rows]
        
    except sqlite3.Error as e:
        print(f"Error de BBDD al verificar factura duplicada: {e}")
        
    finally:
        conn.close()
    print('results',results)   
    return results

def check_procesatedFiles_invoice(normalized_path: str) -> List[Dict[str, Any]]:
    """
    Verifica si una factura con el mismo número y CIF emisor ya existe en processed_invoices.
    
    Args:
        numero_factura: El número de factura a buscar.
        cif_emisor: El CIF o NIF del emisor a buscar.
        
    Returns:
        Una lista de diccionarios, donde cada diccionario representa una fila 
        encontrada (factura duplicada). La lista estará vacía si no se encuentran duplicados.
    """
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    results = []
    
    sql = "SELECT * FROM processed_invoices WHERE path=? "
    
    try:
        # Ejecutar la consulta con los parámetros de forma segura
        cursor.execute(sql, (normalized_path))
        rows = cursor.fetchall()
        
        # Convertir las filas sqlite3.Row a diccionarios
        results = [dict(row) for row in rows]
        
    except sqlite3.Error as e:
        print(f"Error de BBDD al fichero procesado duplicada: {e}")
        # En caso de error (ej. tabla no existe), se devuelve una lista vacía.
        
    finally:
        conn.close()
    print('results',results)   
    return results

def get_extractor_configurations_by_name(extractor_name: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Recupera la configuración de extracción (reglas) para un extractor dado su nombre.
    
    Returns:
        Un diccionario mapeando FIELD_NAME a una lista de diccionarios de reglas.
        Ej: {'FECHA': [{'type': 'VARIABLE', 'ref_text': 'Fecha', 'offset': 0, 'segment': '2'}, ...]}
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Consulta JOIN para obtener todas las reglas de un extractor, ordenadas por campo y orden de intento
    query = """
    SELECT 
        ef.field_name, 
        ec.type, 
        ec.ref_text, 
        ec.offset, 
        ec.segment, 
        ec.value, 
        ec.line 
    FROM extractor_configurations ec 
    JOIN extractors e ON ec.extractor_id = e.extractor_id 
    JOIN extraction_fields ef ON ec.field_id = ef.field_id 
    WHERE e.name = ? 
    ORDER BY ef.field_name, ec.attempt_order
    """
    print(f"BBDD TRACE: Intentando recuperar reglas para el extractor '{extractor_name}'...") # <-- NUEVA TRAZA
    extraction_mapping: Dict[str, List[Dict[str, Any]]] = {}
    
    try:
        cursor.execute(query, (extractor_name,))
        rows = cursor.fetchall()
        
        for row in rows:
            # Los campos están en el orden de la SELECT
            field_name, config_type, ref_text, offset, segment, value, line = row
            
            config_attempt = {'type': config_type}
            
            # Reconstruir el diccionario de la regla (añadiendo solo campos relevantes que no son None)
            if ref_text is not None:
                config_attempt['ref_text'] = ref_text
            if offset is not None:
                config_attempt['offset'] = offset
            if segment is not None:
                config_attempt['segment'] = segment
            if value is not None:
                config_attempt['value'] = value
            if line is not None:
                config_attempt['line'] = line
                
            if field_name not in extraction_mapping:
                extraction_mapping[field_name] = []
            
            extraction_mapping[field_name].append(config_attempt)
        print(f"BBDD TRACE: Mapeo de reglas finalizado. Campos únicos con reglas: {list(extraction_mapping.keys())}")
        return extraction_mapping
        
    except sqlite3.Error as e:
        print(f"Error de BBDD al obtener configuraciones del extractor '{extractor_name}': {e}")
        return {}
    finally:
        conn.close()

def insert_invoice_data(data: Dict[str, Any], original_path: str, is_validated: int):
    """Inserta o actualiza los datos de una factura procesada."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    print("data ",data)
    print("--------------------------------------------")
    numero_factura = data.get('Número de Factura', '').strip()
    cif_emisor = data.get('CIF Emisor', '').strip()
    print ('cif_emisor ', cif_emisor, ' numero_factura ', numero_factura)
    # ⚠️ MODIFICACIÓN: NORMALIZAR LA RUTA
    # Reemplazamos todas las barras invertidas de Windows por barras normales (/)
    # Esto asegura que la clave primaria 'path' sea siempre consistente.
    normalized_path = original_path.replace('\\', '/')
 
    # 🚨 LÓGICA CORREGIDA: Se chequea si hay un duplicado en OTRAS facturas.
    if numero_factura and cif_emisor:
        # Se pasa 'normalized_path' al chequeo para que la factura actual NO se considere duplicado.
        # Se elimina la llamada redundante a 'check_procesatedFiles_invoice'.
        if check_duplicate_invoice(numero_factura, cif_emisor, normalized_path): # MODIFICACIÓN CLAVE
            # Si check_duplicate_invoice devuelve resultados, lanzamos la excepción
            raise DuplicateInvoiceError( # type: ignore
                f"La factura con N° '{numero_factura}' y CIF '{cif_emisor}' ya existe en OTRA factura."
            )
   
    # 1. Limpieza de datos
    file_name = data.get('Archivo', os.path.basename(normalized_path))
    base = _clean_numeric_value(data.get('Base'))
    iva = _clean_numeric_value(data.get('IVA'))
    importe = _clean_numeric_value(data.get('Importe'))
    tasas = _clean_numeric_value(data.get('Tasas'))
    # VALOR AÑADIDO: Timestamp de la inserción
    procesado_en = datetime.now().isoformat()
    
    # 2. Comando SQL (usamos INSERT OR REPLACE para actualizar si ya existe la clave 'path')
    # AÑADIDO: 'procesado_en' a la lista de columnas.
    sql = """
        INSERT OR REPLACE INTO processed_invoices (
            path, file_name, tipo, fecha, numero_factura, emisor,cif_emisor, cliente, cif, 
            modelo, matricula, concepto, base, iva, importe, tasas, is_validated, log_data, procesado_en
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    #validaccion de factura comprobamos en si ya esta insertada una factura cion cif de emisor y numero de factura 

    # AÑADIDO: 'procesado_en' a la lista de valores.
    values = (
        normalized_path, file_name, data.get('Tipo'), data.get('Fecha'), 
        data.get('Número de Factura'), data.get('Emisor'), data.get('CIF Emisor'), data.get('Cliente'), 
        data.get('CIF'), data.get('Modelo'), data.get('Matricula'),  data.get('Concepto'),
        base, iva, importe, tasas, is_validated, data.get('DebugLines'), procesado_en
    )
    try:
        cursor.execute(sql, values)
        conn.commit()
    except sqlite3.Error as e:
        # Relanzamos la excepción para que el log de la GUI la capture.
        conn.rollback()
        raise # Vuelve a lanzar el error de SQLite
    finally:
        conn.close()

def fetch_all_invoices() -> List[Dict[str, Any]]:
    """Recupera todos los registros de facturas."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row # Permite acceder a las columnas por nombre
    cursor = conn.cursor()
    
    try:
        # La consulta ahora funcionará porque la columna 'procesado_en' existe
        cursor.execute("SELECT * FROM processed_invoices  where exportado IS NULL ORDER BY procesado_en DESC")
        rows = cursor.fetchall()
        # Convertir Rows a lista de diccionarios
        invoices = [dict(row) for row in rows]
        return invoices
    except sqlite3.Error as e:
        print(f"Error de BBDD al recuperar datos: {e}")
        return []
    finally:
        conn.close()
def fetch_all_invoices_exported() -> List[Dict[str, Any]]:
    """Recupera todos los registros de facturas."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row # Permite acceder a las columnas por nombre
    cursor = conn.cursor()
    
    try:
        # La consulta ahora funcionará porque la columna 'procesado_en' existe
        cursor.execute("SELECT * FROM processed_invoices  where exportado IS NOT NULL ORDER BY procesado_en DESC")
        rows = cursor.fetchall()
        # Convertir Rows a lista de diccionarios
        invoices = [dict(row) for row in rows]
        return invoices
    except sqlite3.Error as e:
        print(f"Error de BBDD al recuperar datos: {e}")
        return []
    finally:
        conn.close()

def fetch_all_invoices_OK() -> List[Dict[str, Any]]:
    """Recupera todos los registros de facturas. vañlidad"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row # Permite acceder a las columnas por nombre
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT  path, file_name, tipo, fecha, numero_factura, emisor,cif_emisor, cliente, cif, modelo, matricula, concepto, base, iva, importe, tasas, is_validated, procesado_en FROM processed_invoices Where is_validated=1  ORDER BY file_name ASC")
        rows = cursor.fetchall()
        # Convertir Rows a lista de diccionarios
        invoices = [dict(row) for row in rows]
        return invoices
    except sqlite3.Error as e:
        print(f"Error de BBDD al recuperar datos: {e}")
        return []
    finally:
        conn.close()
        
def update_invoice_field(file_path: str, field_name: str, new_value: Any) -> int:
    """
    Actualiza un campo específico de una factura en la BBDD.
    Returns:
      int: El número de filas afectadas (0 o 1).
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 1. Preparar el valor (Usando la utilidad de limpieza _clean_numeric_value)
    if field_name in ['base', 'iva', 'importe', 'tasas']:
        # Se asume que _clean_numeric_value está disponible y limpia el valor
        final_value = _clean_numeric_value(new_value) 
    elif str(new_value).strip() == '':
        final_value = None
    else:
        final_value = new_value

    try:
        # Se mantiene la lista de validación de columnas (es buena práctica)
        valid_cols = ['file_name', 'tipo', 'fecha', 'numero_factura', 'emisor', 'cif_emisor', 
                      'cliente', 'cif', 'modelo', 'matricula', 'concepto', 'base', 'iva', 
                      'importe', 'tasas', 'is_validated', 'log_data', 'procesado_en']
        
        if field_name not in valid_cols:
            print(f"ADVERTENCIA DE SEGURIDAD (BBDD): Intento de actualizar columna no válida: {field_name}")
            return 0

        # CRÍTICO: Normalizar la ruta del archivo (clave primaria)
        normalized_path = file_path.replace('\\', '/')
        
        # Ejecutar el UPDATE
        sql = f"UPDATE processed_invoices SET {field_name} = ? WHERE path = ?"
        
        # --- TRAZA AÑADIDA PARA VER EL PROBLEMA (BBDD) ---
        print(f"--- TRAZA UPDATE (BBDD) ---")
        print(f"  SQL: {sql}")
        print(f"  Valores: {field_name} = '{final_value}', Path = '{normalized_path}'")
        
        cursor.execute(sql, (final_value, normalized_path))
        
        rows_affected = cursor.rowcount
        print(f"  Filas afectadas: {rows_affected}")
        # -------------------------------------------------

        # CRÍTICO: ¡GUARDAR LOS CAMBIOS!
        conn.commit() 
        
        return rows_affected

    except sqlite3.Error as e:
        print(f"❌ ERROR DE BBDD en update_invoice_field: {e}")
        conn.rollback()
        return 0
    finally:
        conn.close()
        
def delete_invoice_data(file_paths: List[str]) -> int:
    """Elimina registros de factura basándose en la lista de rutas."""
    if not file_paths: return 0
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Creamos un placeholder dinámico (?, ?, ...)
    placeholders = ', '.join('?' * len(file_paths))
    sql = f"DELETE FROM processed_invoices WHERE path IN ({placeholders})"
    
    try:
        cursor.execute(sql, file_paths)
        conn.commit()
        deleted_count = cursor.rowcount
        return deleted_count
    except sqlite3.Error as e:
        print(f"Error de BBDD al eliminar datos: {e}")
        conn.rollback()
        return 0
    finally:
        conn.close()

def delete_entire_database_schema() -> bool:
    """Elimina completamente la tabla de facturas."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("DROP TABLE IF EXISTS processed_invoices")
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error al limpiar la BBDD: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()
        
def is_invoice_processed(file_path: str) -> bool:
    """Verifica si un archivo ya ha sido procesado."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT 1 FROM processed_invoices WHERE path = ?", (file_path,))
        return cursor.fetchone() is not None
    except sqlite3.Error as e:
        print(f"Error de BBDD al verificar factura: {e}")
        return False
    finally:
        conn.close()
def is_invoice_validate(file_path: str) -> bool:
    """Verifica si un archivo ya ha sido procesado."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT 1 FROM processed_invoices WHERE path = ? and is_validated=1", (file_path,))
        return cursor.fetchone() is not None
    except sqlite3.Error as e:
        print(f"Error de BBDD al verificar factura: {e}")
        return False
    finally:
        conn.close()

def get_invoice_data(file_path: str) -> Optional[Dict[str, Any]]:
    """Recupera todos los datos de una factura específica por su path."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    # Normalizar la ruta, crítica para la clave primaria
    normalized_path = file_path.replace('\\', '/')
    
    try:
        cursor.execute("SELECT * FROM processed_invoices WHERE path = ?", (normalized_path,))
        row = cursor.fetchone()
        if row:
            data = dict(row)
            # Asegurar que la GUI tiene los campos esperados
            data['file_path'] = data['path'] 
            # El nombre del extractor debe deducirse o guardarse, aquí lo deducimos de file_name.
            data['extractor_name'] = os.path.splitext(os.path.basename(data.get('file_name', 'NuevoExtractor')))[0] 
            data['log_data'] = data.get('log_data', "Log no disponible.")
            
            # Convertir campos numéricos de None a "" (para el formulario)
            for key in ['base', 'iva', 'importe', 'tasas']:
                 data[key] = data[key] if data[key] is not None else ""
                 
            return data
        return None
    except sqlite3.Error as e:
        print(f"Error de BBDD al recuperar datos por path: {e}")
        return None
    finally:
        conn.close()

# --- Funciones de la Base de Datos para Extractores ---

def _create_extractors_table():
    """Crea la tabla 'extractors' si no existe."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS extractors (
                key TEXT PRIMARY KEY,
                module_path TEXT NOT NULL
            )
        """)
        conn.commit()
    except Exception as e:
        print(f"Error al crear la tabla 'extractors': {e}")
    finally:
        conn.close()

def initialize_extractors_data():
    """Inserta el mapeo inicial de extractores si la tabla está vacía."""
    _create_extractors_table() # Asegura que la tabla existe

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        # Verificar si ya hay datos
        cursor.execute("SELECT COUNT(*) FROM extractors")
        if cursor.fetchone()[0] == 0:
            print("Inicializando tabla 'extractors' con datos de configuración...")
            data_to_insert = [(key, path) for key, path in INITIAL_EXTRACTION_MAPPING.items()] # type: ignore
            cursor.executemany("INSERT INTO extractors (key, module_path) VALUES (?, ?)", data_to_insert)
            conn.commit()
            print("Inicialización de extractores completada.")
    except Exception as e:
        print(f"Error al inicializar la tabla 'extractors': {e}")
    finally:
        conn.close()

def get_extraction_mapping() -> Dict[str, str]:
    """Recupera el mapeo completo de extractores de la base de datos."""
    _create_extractors_table() # Asegura la existencia en caso de llamada temprana
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    mapping = {}
    
    try:
        cursor.execute("SELECT name, class_path FROM extractors WHERE is_enabled=1")
        rows = cursor.fetchall()
        for row in rows:
            mapping[row['name']] = row['class_path']
        return mapping
    except Exception as e:
        print(f"Error de BBDD al obtener el mapeo de extractores: {e}")
        return {}
    finally:
        conn.close()

def update_invoices_exported_status(file_paths: List[str], export_timestamp: str) -> int:
    """
    Actualiza el campo 'exportado' para una lista de rutas de archivo con la fecha/hora actual.
    Returns: El número de filas afectadas.
    """
    if not file_paths: return 0
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Normalizar las rutas antes de usarlas en la consulta
    normalized_paths = [path.replace('\\', '/') for path in file_paths]
    
    placeholders = ', '.join('?' * len(normalized_paths))
    
    # La lista de valores de la tupla: primero el timestamp, luego las rutas.
    values = (export_timestamp,) + tuple(normalized_paths) 
    
    sql = f"UPDATE processed_invoices SET exportado = ? WHERE path IN ({placeholders})"
    
    try:
        cursor.execute(sql, values)
        conn.commit()
        return cursor.rowcount
    except sqlite3.Error as e:
        print(f"Error de BBDD al actualizar estado de exportación: {e}")
        conn.rollback()
        return 0
    finally:
        conn.close()
# Función para GUARDAR/ACTUALIZAR una regla en la tabla existente
def save_extractor_configuration(extractor_name: str, field_name: str, rule_dict: dict):
    """
    Guarda una regla en la tabla 'extractor_configurations'.
    Serializa el diccionario de la regla a JSON antes de guardar.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        # Convertimos el diccionario de la regla a JSON string para guardarlo
        rule_json_str = json.dumps(rule_dict)
        
        # NOTA: Ajusta el nombre de las columnas según tu esquema real de 'extractor_configurations'
        # Aquí asumo una estructura estándar: extractor_name, field_name, configuration_value
        
        # Opción A: Si la tabla guarda una fila por regla
        cursor.execute('''
            INSERT INTO extractor_configurations (extractor_name, field_name, rule_data, created_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ''', (extractor_name, field_name, rule_json_str))
        
        # Opción B: Si necesitas evitar duplicados, usa INSERT OR REPLACE o verifica antes
        # cursor.execute('DELETE FROM extractor_configurations WHERE extractor_name=? AND field_name=?', (extractor_name, field_name))
        # cursor.execute('INSERT ...')

        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error BBDD al guardar configuración: {e}")
        return False
    finally:
        conn.close()
# OPCIONAL: Puede llamar a initialize_extractors_data() al final de database.py
# para que la inicialización ocurra en el primer import del módulo.
# initialize_extractors_data()