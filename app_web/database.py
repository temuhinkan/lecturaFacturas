import sqlite3
import os
from typing import Any, List, Dict, Optional
from datetime import datetime
from contextlib import contextmanager

# --- CONFIGURACIÓN DE RUTAS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "facturas.db")

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

@contextmanager
def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def _clean_numeric_value(value: Any) -> Optional[float]:
    if value is None or str(value).strip() in ['', 'None']:
        return 0.0
    try:
        if isinstance(value, (int, float)):
            return float(value)
        val_str = str(value).replace('.', '').replace(',', '.')
        return float(val_str)
    except (ValueError, TypeError):
        return 0.0

def setup_database():
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 1. Facturas
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
                concepto TEXT,
                is_validated INTEGER DEFAULT 0,
                exportado TEXT DEFAULT 'NO',
                log_data TEXT,
                procesado_en TEXT
            )
        """)

        # 2. Vehículos (Corregida la indentación aquí)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vehiculos (
                matricula TEXT PRIMARY KEY,
                fecha_compra TEXT,
                factura_n TEXT,
                proveedor TEXT,
                cif_proveedor TEXT,
                modelo TEXT,
                base REAL,
                iva REAL,
                exento TEXT,
                total REAL,
                estado TEXT DEFAULT 'Disponible'
            )
        """)

        # 3. Gastos (Corregida la referencia a matricula)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gastos_vehiculo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vehiculo_id TEXT,
                factura_path TEXT,
                concepto TEXT,
                importe REAL,
                fecha_gasto TEXT,
                FOREIGN KEY(vehiculo_id) REFERENCES vehiculos(matricula),
                FOREIGN KEY(factura_path) REFERENCES processed_invoices(path)
            )
        """)

        # 4. Clientes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT UNIQUE,
                cif TEXT,
                extractor_default TEXT,
                palabras_clave TEXT,
                prioridad INTEGER DEFAULT 0
            )
        """)

        conn.commit()

def save_vehicle_from_excel(data: dict):
    query = '''
        INSERT INTO vehiculos (matricula, fecha_compra, factura_n, proveedor, cif_proveedor, modelo, base, iva, exento, total)
        VALUES (:matricula, :fecha, :factura, :proveedor, :cif, :modelo, :base, :iva, :exento, :total)
        ON CONFLICT(matricula) DO UPDATE SET
            fecha_compra = excluded.fecha_compra,
            factura_n = excluded.factura_n,
            proveedor = excluded.proveedor,
            modelo = excluded.modelo,
            total = excluded.total
    '''
    with get_db_connection() as conn:
        conn.execute(query, data)
        conn.commit()

def fetch_all_vehicles():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM vehiculos ORDER BY matricula ASC")
        return [dict(row) for row in cursor.fetchall()]   
    # Insertar datos por defecto si es necesario
    _initialize_defaults()

def _initialize_defaults():
    """Inserta extractores básicos si no existen."""
    extractors_base = [
        ('GENERICO', 'extractors.base_invoice_extractor.BaseInvoiceExtractor', 1),
    ]
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.executemany("""
            INSERT OR IGNORE INTO extractors (name, class_path, is_enabled)
            VALUES (?, ?, ?)
        """, extractors_base)
        conn.commit()

# --- FUNCIONES: GESTIÓN DE FACTURAS ---

def fetch_all_invoices() -> List[Dict]:
    """Obtiene todas las facturas."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM processed_invoices ORDER BY procesado_en DESC")
        return [dict(row) for row in cursor.fetchall()]

def insert_invoice_data(data: Dict[str, Any], original_path: str, is_validated: int):
    """Inserta o actualiza una factura procesada."""
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
            normalized_path, 
            data.get('Archivo', os.path.basename(normalized_path)),
            data.get('Tipo'), data.get('Fecha'), data.get('Número de Factura'), 
            data.get('Emisor'), data.get('CIF Emisor'), data.get('Cliente'), 
            data.get('CIF'), data.get('Modelo'), data.get('Matricula'), 
            data.get('Concepto'), 
            _clean_numeric_value(data.get('Base')), 
            _clean_numeric_value(data.get('IVA')), 
            _clean_numeric_value(data.get('Importe')), 
            _clean_numeric_value(data.get('Tasas')), 
            is_validated, 
            str(data.get('DebugLines', '')), 
            datetime.now().isoformat()
        )
        cursor.execute(sql, values)
        conn.commit()

def update_invoice_field(file_path: str, field_name: str, new_value: Any):
    """Actualiza un campo específico de una factura."""
    normalized_path = file_path.replace('\\', '/')
    
    # Limpieza de numéricos si el campo es de dinero
    if field_name in ['base', 'iva', 'importe', 'tasas']:
        new_value = _clean_numeric_value(new_value)
        
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Nota: Usar f-string en el nombre de columna es seguro si el input está controlado,
        # pero idealmente se valida contra una lista blanca.
        allowed_fields = ['emisor', 'fecha', 'importe', 'matricula', 'is_validated', 'exportado', 'concepto']
        if field_name in allowed_fields:
            cursor.execute(f"UPDATE processed_invoices SET {field_name} = ? WHERE path = ?", (new_value, normalized_path))
            conn.commit()

def is_invoice_processed(file_path: str) -> bool:
    normalized_path = file_path.replace('\\', '/')
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM processed_invoices WHERE path = ?", (normalized_path,))
        return cursor.fetchone() is not None

# --- FUNCIONES: GESTIÓN DE STOCK Y VEHÍCULOS ---

def get_all_vehiculos():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # CORREGIDO: Usar 'vehiculos' en lugar de 'stock_vehiculos'
        cursor.execute("SELECT id, matricula, marca, modelo, precio_compra, estado FROM vehiculos") 
        return [dict(row) for row in cursor.fetchall()]

def add_vehiculo(matricula, marca, modelo, precio_compra, bastidor=""):
    """Añade un nuevo coche al stock."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO vehiculos (matricula, marca, modelo, precio_compra, bastidor)
                VALUES (?, ?, ?, ?, ?)
            """, (matricula.upper(), marca, modelo, precio_compra, bastidor))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

def vincular_gasto_vehiculo(vehiculo_id, factura_path, concepto, importe):
    """
    Inserta un registro en la tabla de gastos vinculados.
    Se llama desde validador.py cuando pulsas 'Validar y Guardar'.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("""
            INSERT INTO gastos_vehiculo (vehiculo_id, factura_path, concepto, importe, fecha_gasto)
            VALUES (?, ?, ?, ?, ?)
        """, (vehiculo_id, factura_path, concepto, importe, fecha_hoy))
        conn.commit()

# --- FUNCIONES: EXTRACTORES Y APRENDIZAJE ---

def get_extraction_mapping() -> Dict[str, str]:
    """Mapeo para logic.py: devuelve {NombreExtractor: RutaClase}."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, class_path FROM extractors WHERE is_enabled = 1")
        return {row['name']: row['class_path'] for row in cursor.fetchall()}
def get_extractor_names() -> List[str]:
    """Obtiene solo los nombres de los extractores disponibles."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM extractors WHERE is_enabled = 1")
        return [row['name'] for row in cursor.fetchall()]
def save_learning_rule(emisor_id, campo, ancla, rel_x, rel_y, pagina):
    """Guarda aprendizaje del usuario sobre posiciones de datos."""
    ahora = datetime.now().isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
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
def fetch_all_clients():
    """Obtiene todos los clientes de la tabla."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM clientes ORDER BY nombre ASC")
        return [dict(row) for row in cursor.fetchall()]
def save_client(data: dict):
    """Inserta un nuevo cliente o actualiza uno existente por su Nombre."""
    query = """
    INSERT INTO clientes (nombre, cif, extractor_default, palabras_clave)
    VALUES (?, ?, ?, ?)
    ON CONFLICT(nombre) DO UPDATE SET
        cif = excluded.cif,
        extractor_default = excluded.extractor_default,
        palabras_clave = excluded.palabras_clave
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                data.get('nombre'), 
                data.get('cif'), 
                data.get('extractor_default', 'Genérico'), 
                data.get('palabras_clave')
            ))
            conn.commit()
            return True
    except Exception as e:
        print(f"Error al guardar cliente: {e}")
        return False
def delete_invoice(path):
    with get_db_connection() as conn:
        conn.execute("DELETE FROM processed_invoices WHERE path = ?", (path,))
        conn.commit()
def save_vehicle_from_excel(data: dict):
    """Guarda o actualiza un vehículo desde los datos del Excel."""
    query = '''
        INSERT INTO vehiculos (matricula, fecha_compra, factura_n, proveedor, cif_proveedor, modelo, base, iva, exento, total)
        VALUES (:matricula, :fecha, :factura, :proveedor, :cif, :modelo, :base, :iva, :exento, :total)
        ON CONFLICT(matricula) DO UPDATE SET
            fecha_compra = excluded.fecha_compra,
            factura_n = excluded.factura_n,
            total = excluded.total
    '''
    with get_db_connection() as conn:
        conn.execute(query, data)
        conn.commit()
def fetch_gastos_por_vehiculo(matricula):
    """Obtiene todos los gastos asociados a una matrícula."""
    query = "SELECT * FROM gastos_vehiculo WHERE vehiculo_id = ? ORDER BY fecha_gasto DESC"
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (matricula,))
        return [dict(row) for row in cursor.fetchall()]
    
def fetch_export_history():
    """Obtiene un resumen de los lotes exportados y cuántas facturas tiene cada uno."""
    query = """
        SELECT exportado, COUNT(*) as total_facturas
        FROM processed_invoices
        WHERE exportado IS NOT NULL AND exportado != ''
        GROUP BY exportado
        ORDER BY exportado DESC
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]

def fetch_invoices_by_export_batch(batch_name):
    """Obtiene todas las facturas que pertenecen a un lote de exportación específico."""
    query = "SELECT * FROM processed_invoices WHERE exportado = ?"
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (batch_name,))
        return [dict(row) for row in cursor.fetchall()]
# --- EJECUCIÓN DIRECTA (PARA INICIALIZAR) ---
if __name__ == "__main__":
    setup_database()
    print(f"✅ Base de datos configurada correctamente en: {DB_PATH}")
    # Opcional: Crear un coche de prueba para que veas algo en el Dropdown
    add_vehiculo("1234BBB", "TestBrand", "TestModel", 10000)