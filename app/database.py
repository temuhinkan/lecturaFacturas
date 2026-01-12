import sqlite3
import os
from typing import Any, List, Dict, Optional, Tuple
from datetime import datetime
from contextlib import contextmanager

# --- Configuración ---
DB_NAME = "facturas.db"

class DuplicateInvoiceError(Exception):
    """Excepción lanzada cuando se intenta insertar una factura duplicada."""
    pass

@contextmanager
def get_db_connection():
    """Gestiona la conexión a la BBDD de forma segura."""
    conn = sqlite3.connect(DB_NAME, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

# --- Utilidades ---
def _clean_numeric_value(value: Any) -> Optional[float]:
    if value is None or str(value).strip() in ['', 'None']:
        return None
    try:
        if isinstance(value, str):
            value = value.replace('.', '').replace(',', '.')
        return float(value)
    except (ValueError, TypeError):
        return None

# --- Inicialización y Esquema ---

def setup_database():
    """Configura el esquema completo de la base de datos."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
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
                procesado_en TEXT,
                concepto TEXT,
                exportado TEXT       
            )
        """)
        # NUEVA TABLA: Base de Conocimiento para Aprendizaje Inteligente
        # Esta tabla permite que el sistema aprenda posiciones relativas de campos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_base (
                rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                emisor_id TEXT,           -- Puede ser CIF o Nombre
                campo TEXT,               -- nombre_factura, importe, matricula...
                ancla TEXT,               -- Palabra clave cercana (ej: "TOTAL")
                rel_x REAL,               -- Distancia horizontal al ancla
                rel_y REAL,               -- Distancia vertical al ancla
                pagina INTEGER DEFAULT 0, -- Página donde suele estar
                confianza INTEGER DEFAULT 1, -- Cuántas veces se ha corregido igual
                ultima_correccion TEXT,
                UNIQUE(emisor_id, campo, ancla) -- Evita duplicar reglas para el mismo caso
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS extractors (
                extractor_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,       
                class_path TEXT NOT NULL,        
                is_enabled INTEGER DEFAULT 1     
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS extraction_fields (
                field_id INTEGER PRIMARY KEY AUTOINCREMENT,
                field_name TEXT UNIQUE NOT NULL, 
                description TEXT,                
                data_type TEXT NOT NULL,         
                is_required INTEGER NOT NULL DEFAULT 1 
            )
        """)
        
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
            )
        """)
        conn.commit()
    
    insert_default_fields()
    _run_migrations()

def _run_migrations():
    REQUIRED_COLUMNS = {
        "processed_invoices": {
            "tasas": "REAL", "log_data": "TEXT", "procesado_en": "TEXT",
            "concepto": "TEXT", "exportado": "TEXT"
        }
    }
    with get_db_connection() as conn:
        cursor = conn.cursor()
        for table, columns in REQUIRED_COLUMNS.items():
            cursor.execute(f"PRAGMA table_info({table})")
            existing = [info[1] for info in cursor.fetchall()]
            for col_name, col_type in columns.items():
                if col_name not in existing:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
        conn.commit()
# --- Funciones de Aprendizaje (NUEVAS) ---

def save_learning_rule(emisor_id, campo, ancla, rel_x, rel_y, pagina):
    """Guarda o actualiza una regla de extracción basada en una corrección manual."""
    ahora = datetime.now().isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # INSERT OR REPLACE para que si el usuario corrige la posición, la regla se actualice
        cursor.execute("""
            INSERT INTO knowledge_base (emisor_id, campo, ancla, rel_x, rel_y, pagina, ultima_correccion)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(emisor_id, campo, ancla) DO UPDATE SET
                rel_x = excluded.rel_x,
                rel_y = excluded.rel_y,
                confianza = confianza + 1,
                ultima_correccion = excluded.ultima_correccion
        """, (emisor_id, campo, ancla, rel_x, rel_y, pagina, ahora))
        conn.commit()

def get_learning_rules_for_emisor(emisor_id):
    """Recupera todas las reglas aprendidas para un emisor específico."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM knowledge_base WHERE emisor_id = ?", (emisor_id,))
        return [dict(row) for row in cursor.fetchall()]
def insert_default_fields():
    fields_data = [
        ('TIPO', 1, 'TEXT', 'Tipo de operación'), ('FECHA', 1, 'DATE', 'Fecha factura'),
        ('NUM_FACTURA', 1, 'TEXT', 'Número factura'), ('EMISOR', 1, 'TEXT', 'Nombre emisor'),
        ('CIF_EMISOR', 1, 'NIF/CIF', 'CIF emisor'), ('CLIENTE', 1, 'TEXT', 'Nombre cliente'),
        ('CIF', 1, 'NIF/CIF', 'CIF cliente'), ('IMPORTE', 1, 'FLOAT', 'Total'),
        ('BASE', 1, 'FLOAT', 'Base imponible'), ('IVA', 1, 'FLOAT', 'IVA'),
        ('TASAS', 1, 'FLOAT', 'Tasas'), ('CONCEPTO', 0, 'TEXT', 'Concepto'),
        ('MODELO', 0, 'TEXT', 'Modelo'), ('MATRICULA', 0, 'TEXT', 'Matrícula')
    ]
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.executemany("""
            INSERT OR IGNORE INTO extraction_fields (field_name, is_required, data_type, description)
            VALUES (?, ?, ?, ?)
        """, fields_data)
        conn.commit()

# --- Funciones Requeridas por main_gui.py ---

def fetch_all_invoices() -> List[Dict]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM processed_invoices")
        return [dict(row) for row in cursor.fetchall()]

def fetch_all_invoices_OK() -> List[Dict]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM processed_invoices WHERE is_validated = 1")
        return [dict(row) for row in cursor.fetchall()]

def fetch_all_invoices_exported() -> List[Dict]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM processed_invoices WHERE exportado = 'SI'")
        return [dict(row) for row in cursor.fetchall()]

def delete_invoice_data(file_path: str):
    normalized_path = file_path.replace('\\', '/')
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM processed_invoices WHERE path = ?", (normalized_path,))
        conn.commit()

def update_invoice_field(file_path: str, field_name: str, new_value: Any):
    normalized_path = file_path.replace('\\', '/')
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if field_name in ['base', 'iva', 'importe', 'tasas']:
            new_value = _clean_numeric_value(new_value)
        cursor.execute(f"UPDATE processed_invoices SET {field_name} = ? WHERE path = ?", (new_value, normalized_path))
        conn.commit()

def is_invoice_processed(file_path: str) -> bool:
    normalized_path = file_path.replace('\\', '/')
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM processed_invoices WHERE path = ?", (normalized_path,))
        return cursor.fetchone() is not None

def delete_entire_database_schema():
    """Cuidado: Esto borra todo."""
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
    setup_database()

# --- Gestión de Extractores ---

def get_extractor_configuration(extractor_name: str) -> Dict[str, List[Dict[str, Any]]]:
    config = {}
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Verificamos si la tabla existe antes de consultar
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='extractor_configurations'")
            if not cursor.fetchone():
                return {}
            query = """
                SELECT ef.field_name, ec.type, ec.ref_text, ec.offset, ec.segment, ec.value, ec.line, ec.attempt_order
                FROM extractor_configurations ec
                JOIN extractors e ON ec.extractor_id = e.extractor_id
                JOIN extraction_fields ef ON ec.field_id = ef.field_id
                WHERE e.name = ?
                ORDER BY ef.field_name, ec.attempt_order
            """
            cursor.execute(query, (extractor_name,))
            for row in cursor.fetchall():
                field = row['field_name']
                if field not in config: config[field] = []
                config[field].append(dict(row))
    except sqlite3.OperationalError:
        return {} # Retorna vacío si la tabla no existe aún
    return config

def save_extractor_configuration(extractor_name: str, field_name: str, rule: Dict[str, Any]) -> bool:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT extractor_id FROM extractors WHERE name = ?", (extractor_name,))
            ext_row = cursor.fetchone()
            if not ext_row:
                cursor.execute("INSERT INTO extractors (name, class_path) VALUES (?, ?)", 
                               (extractor_name, f"extractors.{extractor_name.lower()}.{extractor_name}"))
                ext_id = cursor.lastrowid
            else: ext_id = ext_row['extractor_id']

            cursor.execute("SELECT field_id FROM extraction_fields WHERE field_name = ?", (field_name,))
            f_row = cursor.fetchone()
            if not f_row: return False
            
            cursor.execute("""
                INSERT OR REPLACE INTO extractor_configurations 
                (extractor_id, field_id, attempt_order, type, ref_text, offset, segment, value, line)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (ext_id, f_row['field_id'], rule.get('attempt_order', 1), rule.get('type'), 
                  rule.get('ref_text'), rule.get('offset', 0), rule.get('segment', '1'), 
                  rule.get('value'), rule.get('line', 0)))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error: {e}")
            return False

def get_extraction_mapping() -> Dict[str, str]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, class_path FROM extractors WHERE is_enabled=1")
        return {row['name']: row['class_path'] for row in cursor.fetchall()}

def insert_invoice_data(data: Dict[str, Any], original_path: str, is_validated: int):
    normalized_path = original_path.replace('\\', '/')
    with get_db_connection() as conn:
        cursor = conn.cursor()
        sql = """
            INSERT OR REPLACE INTO processed_invoices (
                path, file_name, tipo, fecha, numero_factura, emisor, cif_emisor, 
                cliente, cif, modelo, matricula, concepto, base, iva, importe, 
                tasas, is_validated, log_data, procesado_en
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        values = (
            normalized_path, data.get('Archivo', os.path.basename(normalized_path)),
            data.get('Tipo'), data.get('Fecha'), data.get('Número de Factura'), 
            data.get('Emisor'), data.get('CIF Emisor'), data.get('Cliente'), 
            data.get('CIF'), data.get('Modelo'), data.get('Matricula'), 
            data.get('Concepto'), _clean_numeric_value(data.get('Base')), 
            _clean_numeric_value(data.get('IVA')), _clean_numeric_value(data.get('Importe')), 
            _clean_numeric_value(data.get('Tasas')), is_validated, 
            data.get('DebugLines'), datetime.now().isoformat()
        )
        cursor.execute(sql, values)
        conn.commit()
def initialize_extractors_data():
    """
    Inserta los extractores base en la tabla 'extractors' si no existen.
    Esto permite que el sistema sepa qué clases de Python usar para cada cliente.
    """
    extractors_base = [
        ('GENERICO', 'extractors.base_invoice_extractor.BaseInvoiceExtractor', 1),
        # Puedes añadir aquí otros extractores fijos que tengas en tu carpeta /extractors
    ]
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.executemany("""
                INSERT OR IGNORE INTO extractors (name, class_path, is_enabled)
                VALUES (?, ?, ?)
            """, extractors_base)
            conn.commit()
        except Exception as e:
            print(f"Error inicializando extractors: {e}")

def is_invoice_processed(file_path: str) -> bool:
    """Verifica si una factura ya existe en la base de datos."""
    normalized_path = file_path.replace('\\', '/')
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM processed_invoices WHERE path = ?", (normalized_path,))
        return cursor.fetchone() is not None
def get_all_extractor_names():
    """Obtiene la lista de nombres de extractores registrados en la tabla 'extractors'."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM extractors ORDER BY name ASC")
            rows = cursor.fetchall()
            # Devolvemos una lista de strings
            return [row[0] for row in rows]
    except Exception as e:
        print(f"Error al obtener nombres de extractores: {e}")
        return ["GENERICO"] # Fallback por seguridad