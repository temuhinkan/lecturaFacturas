import sqlite3
import os
from typing import Any, List, Dict, Optional
from datetime import datetime # AÑADIDO: Necesario para obtener la fecha/hora de inserción

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
            procesado_en TEXT -- NUEVA COLUMNA
        )
    """)
    conn.commit()
    
    # 2. Lógica de Migración (Añadir columnas faltantes si la tabla ya existía)
    
    # Columnas que sabemos que pudieron haber sido añadidas más tarde.
    # AÑADIDO: 'procesado_en' a la lista de columnas a revisar.
    REQUIRED_COLUMNS_TO_CHECK = {
        "tasas": "REAL",
        "log_data": "TEXT",
        "procesado_en": "TEXT" 
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

def insert_invoice_data(data: Dict[str, Any], original_path: str, is_validated: int):
    """Inserta o actualiza los datos de una factura procesada."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 1. Limpieza de datos
    file_name = data.get('Archivo', os.path.basename(original_path))
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
            path, file_name, tipo, fecha, numero_factura, emisor, cliente, cif, 
            modelo, matricula, base, iva, importe, tasas, is_validated, log_data, procesado_en
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    # AÑADIDO: 'procesado_en' a la lista de valores.
    values = (
        original_path, file_name, data.get('Tipo'), data.get('Fecha'), 
        data.get('Número de Factura'), data.get('Emisor'), data.get('Cliente'), 
        data.get('CIF'), data.get('Modelo'), data.get('Matricula'), 
        base, iva, importe, tasas, is_validated, data.get('DebugLines'), procesado_en
    )
    
    # ⚠️ TRAZA AÑADIDA: Imprime la sentencia SQL y los valores.
    # Esto aparecerá en la consola/terminal donde se ejecuta main_gui.py
    print("\n--- TRAZA BBDD: INTENTO DE INSERT/REPLACE ---")
    print("SQL:", sql.strip())
    print("VALORES:", values)
    print("------------------------------------------\n")
    
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
        cursor.execute("SELECT * FROM processed_invoices ORDER BY procesado_en DESC")
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
        cursor.execute("SELECT * FROM processed_invoices Where is_validated=1 ORDER BY file_name ASC")
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
    
    # 1. Preparar el valor (usando la función de limpieza local)
    if field_name in ['base', 'iva', 'importe', 'tasas']:
        final_value = _clean_numeric_value(new_value)
    elif str(new_value).strip() == '':
        final_value = None
    else:
        final_value = new_value

    try:
        # Seguridad: Solo permitimos que se actualicen nombres de columnas válidos
        valid_cols = ['file_name', 'tipo', 'fecha', 'numero_factura', 'emisor', 'cliente', 'cif', 
                      'modelo', 'matricula', 'base', 'iva', 'importe', 'tasas', 'is_validated', 'log_data', 'procesado_en']
        if field_name not in valid_cols:
             raise ValueError(f"Intento de actualizar columna inválida: {field_name}")

        sql = f"UPDATE processed_invoices SET {field_name} = ? WHERE path = ?"
        
        cursor.execute(sql, (final_value, file_path))
        conn.commit()
        
        return cursor.rowcount
        
    except sqlite3.Error as e:
        print(f"Error al actualizar la BBDD ({field_name}): {e}")
        conn.rollback()
        return 0
    except ValueError as e:
        print(f"Error de actualización: {e}")
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