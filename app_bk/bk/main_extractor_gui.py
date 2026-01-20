import os
import csv
import PyPDF2
import shutil
import fitz # Motor principal para lectura de PDF y rasterización para OCR
import tempfile 
import sys 
import importlib 
import importlib.util 
import tkinter as tk
from tkinter import filedialog, messagebox, ttk 
from tkinter.scrolledtext import ScrolledText 
from typing import Tuple, List, Optional, Any, Dict 
import subprocess 
import re 
from PIL import Image, ImageTk, ImageDraw # Añadido ImageDraw para crear iconos
import pytesseract
import traceback 
import sqlite3 

# --- Configuración de OCR (Tesseract) ---
try:
    from PIL import Image
    import pytesseract
    
    if sys.platform == "win32":
        # ¡AJUSTA ESTA RUTA SI ES NECESARIO!
        pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe' 
    
except ImportError:
    Image = None
    pytesseract = None
    ImageTk = None 
except AttributeError:
    Image = None
    pytesseract = None
    ImageTk = None 


# --- Importaciones de Extractor y Utilidades (STUBS/MOCKUPS) ---
try:
    # Intenta importar el extractor base
    from extractors.base_invoice_extractor import BaseInvoiceExtractor
    # Intenta importar utilidades
    from split_pdf import split_pdf_into_single_page_files
except ImportError:
    # Stubs si BaseInvoiceExtractor o utilidades no existen
    class BaseInvoiceExtractor:
        def __init__(self, lines, pdf_path=None): 
            self.lines = lines
            self.pdf_path = pdf_path
            self.cif = 'B00000000'
        def extract_all(self): 
            return ("Tipo_BASE", "Fecha_BASE", "NºFactura_BASE", "Emisor_BASE", "Cliente_BASE", "CIF_BASE", "Modelo_BASE", "Matricula_BASE", 100.0, 82.64, 17.36, 0.0)
        def is_valid(self): return True
        def extract_data(self, lines: List[str]) -> Dict[str, Any]:
            return {'tipo': 'Tipo_STUB', 'importe': 99.99}
    
    def split_pdf_into_single_page_files(a, b): return [a]
    print("ADVERTENCIA: Usando stubs para BaseInvoiceExtractor y utilidades.")


# ----------------------------------------------------------------------
# FUNCIONES DE BASE DE DATOS (SQLite)
# ----------------------------------------------------------------------
DB_NAME = 'facturas_procesadas.db'

def setup_database():
    """Conecta a la BBDD (o la crea) y asegura que la tabla existe y tiene 'log_data' y 'is_validated'."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 1. Crear la tabla si no existe
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
            procesado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            log_data TEXT,
            is_validated INTEGER DEFAULT 0 -- Columna de validación
        )
    """)
    
    # 🚨 MIGRACIÓN: Asegurar que 'log_data' existe
    try:
        cursor.execute("SELECT log_data FROM processed_invoices LIMIT 1")
    except sqlite3.OperationalError:
        print("Migrating DB: Adding 'log_data' column.")
        cursor.execute("ALTER TABLE processed_invoices ADD COLUMN log_data TEXT")
        
    # 🚨 NUEVA MIGRACIÓN: Asegurar que 'is_validated' existe
    try:
        cursor.execute("SELECT is_validated FROM processed_invoices LIMIT 1")
    except sqlite3.OperationalError:
        print("Migrating DB: Adding 'is_validated' column.")
        cursor.execute("ALTER TABLE processed_invoices ADD COLUMN is_validated INTEGER DEFAULT 0") 
    
    conn.commit()
    conn.close()

def _clean_numeric_value(value: Any) -> float:
    """Limpia una cadena de formato de moneda/separadores y la convierte a float."""
    if value is None:
        return 0.0
    try:
        # Intenta convertir a string, reemplaza coma por punto, elimina símbolos y convierte a float.
        return float(str(value).replace(',', '.').replace('€', '').replace('%', '').strip() or 0.0) 
    except ValueError:
        return 0.0

def is_invoice_processed(file_path: str, force_reprocess: bool = False) -> bool:
    """Verifica si un archivo ya existe en la BBDD por su ruta completa (path)."""
    if force_reprocess:
        return False 
    
    if not file_path or not isinstance(file_path, str):
        return False
        
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM processed_invoices WHERE path = ?", (file_path,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def insert_invoice_data(data: Dict[str, Any], original_path: str, is_validated: int = 0):
    """Inserta o actualiza datos de la factura en la BBDD. Incluye el estado de validación."""
    
    base_val = _clean_numeric_value(data.get('Base'))
    iva_val = _clean_numeric_value(data.get('IVA'))
    importe_val = _clean_numeric_value(data.get('Importe'))
    tasas_val = _clean_numeric_value(data.get('Tasas'))
    
    # Aseguramos que los campos de texto no sean None
    tipo_val = data.get('Tipo') or ''
    fecha_val = data.get('Fecha') or ''
    numero_factura_val = data.get('Número de Factura') or ''
    emisor_val = data.get('Emisor') or ''
    cliente_val = data.get('Cliente') or ''
    cif_val = data.get('CIF') or ''
    modelo_val = data.get('Modelo') or ''
    matricula_val = data.get('Matricula') or ''
    file_name_val = data.get('Archivo') or os.path.basename(original_path)
    
    # Obtener el log/debug
    log_data_val = data.get('DebugLines') or ''
    
    # Obtener el estado de validación
    validation_status = data.get('is_validated', is_validated)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    invoice_data = (
        original_path,
        file_name_val,
        tipo_val,
        fecha_val,
        numero_factura_val,
        emisor_val,
        cliente_val,
        cif_val,
        modelo_val,
        matricula_val,
        base_val,
        iva_val,
        importe_val,
        tasas_val,
        log_data_val,
        validation_status 
    )
    
    # QUERY ACTUALIZADA: Se añade 'is_validated'
    cursor.execute("""
        INSERT OR REPLACE INTO processed_invoices 
        (path, file_name, tipo, fecha, numero_factura, emisor,cif_emisor cliente, cif, modelo, matricula, base, iva, importe, tasas, log_data, is_validated)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, invoice_data)
    
    conn.commit()
    conn.close()

def update_invoice_field(file_path: str, db_column: str, new_value: Any):
    """
    ACTUALIZACIÓN NUEVA: Actualiza un campo específico de una factura en la BBDD.
    Se asegura de usar _clean_numeric_value para campos REAL.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Mapeo de columnas internas de DB
    NUMERIC_COLUMNS = ['base', 'iva', 'importe', 'tasas']
    
    # Lista segura de columnas permitidas para la actualización
    ALLOWED_COLUMNS = [
        'file_name', 'tipo', 'fecha', 'numero_factura', 'emisor', 'cliente', 
        'cif', 'modelo', 'matricula', 'base', 'iva', 'importe', 'tasas'
    ]
    
    if db_column not in ALLOWED_COLUMNS:
         print(f"Advertencia: Columna de BBDD no válida para edición: {db_column}")
         conn.close()
         return 0
         
    # Manejar conversión numérica para campos REAL
    if db_column in NUMERIC_COLUMNS:
        new_value = _clean_numeric_value(new_value) 

    # Se usa f-string para el nombre de la columna (ya validado/filtrado) y placeholder '?' para el valor.
    query = f"UPDATE processed_invoices SET {db_column} = ? WHERE path = ?"
    
    try:
        cursor.execute(query, (new_value, file_path))
        rows_affected = conn.rowcount
        conn.commit()
        return rows_affected
    except Exception as e:
        print(f"Error al actualizar la BBDD ({db_column}): {e}")
        return 0
    finally:
        conn.close()


def delete_invoice_data(file_paths: List[str]):
    """Elimina uno o varios registros de la factura de la BBDD por su path."""
    if not file_paths:
        return 0
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Crea la cadena de placeholders (?, ?, ...)
    placeholders = ','.join(['?'] * len(file_paths))
    query = f"DELETE FROM processed_invoices WHERE path IN ({placeholders})"
    
    try:
        cursor.execute(query, file_paths)
        deleted_count = conn.rowcount
        conn.commit()
        return deleted_count
    except Exception as e:
        print(f"Error al eliminar de la BBDD: {e}")
        return 0
    finally:
        conn.close()
        
def delete_entire_database_schema():
    """Elimina la tabla 'processed_invoices' (borrando todos los datos)."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("DROP TABLE IF EXISTS processed_invoices")
        conn.commit()
        return True
    except Exception as e:
        print(f"Error al borrar la BBDD: {e}")
        return False
    finally:
        conn.close()


# ----------------------------------------------------------------------
# FUNCIONES AUXILIARES 
# ----------------------------------------------------------------------
def _load_extractor_class_dynamic(extractor_path_str: str):
    """ (Se mantiene sin cambios) """
    try:
        parts = extractor_path_str.split('.')
        module_name = ".".join(parts[:-1]) 
        class_name = parts[-1] 

        module_spec = importlib.util.find_spec(module_name)
        if not module_spec or not module_spec.origin:
            raise ImportError(f"No se encontró el archivo del módulo: {module_name}")

        module = importlib.util.module_from_spec(module_spec)

        BaseInvoiceExtractor_Class = globals().get('BaseInvoiceExtractor')
        if BaseInvoiceExtractor_Class is None:
            raise RuntimeError("BaseInvoiceExtractor no está definida en el ámbito global.")
            
        module.__dict__['BaseInvoiceExtractor'] = BaseInvoiceExtractor_Class

        sys.modules[module_name] = module
        module_spec.loader.exec_module(module)

        return getattr(module, class_name)

    except Exception as e:
        raise RuntimeError(f"Fallo al cargar la clase {extractor_path_str}. Error: {e}")

# --- Mapeo de Clases de Extracción ---
EXTRACTION_MAPPING = {
    "autodoc": "extractors.autodoc_extractor.AutodocExtractor",
    "stellantis": "extractors.stellantis_extractor.StellantisExtractor",
    "brildor": "extractors.brildor_extractor.BrildorExtractor",
    "hermanas": "extractors.hermanas_extractor.HermanasExtractor",
    "kiauto": "extractors.kiauto_extractor.KiautoExtractor",
    "sumauto": "extractors.sumauto_extractor.SumautoExtractor",
    "amor": "extractors.hermanas_extractor.HermanasExtractor", # Alias para "Hermanas del Amor de Dios"
    "pinchete": "extractors.pinchete_extractor.PincheteExtractor",
    "refialias": "extractors.refialias_extractor.RefialiasExtractor",
    "leroy": "extractors.leroy_extractor.LeroyExtractor",
    "poyo": "extractors.poyo_extractor.PoyoExtractor",
    "caravana": "extractors.lacaravana_extractor.LacaravanaExtractor",
    "malaga": "extractors.malaga_extractor.MalagaExtractor",
    "beroil": "extractors.beroil_extractor.BeroilExtractor",
    "berolkemi": "extractors.berolkemi_extractor.BerolkemiExtractor",
    "autocasher": "extractors.autocasher_extractor.AutocasherExtractor",
    "cesvimap": "extractors.cesvimap_extractor.CesvimapExtractor",
    "fiel": "extractors.fiel_extractor.FielExtractor",
    "pradilla": "extractors.pradilla_extractor.PradillaExtractor",
    "boxes": "extractors.boxes_extractor.BoxesExtractor",
    "hergar": "extractors.hergar_extractor.HergarExtractor",
    "musas": "extractors.musas_extractor.MusasExtractor",
    "muas": "extractors.musas_extractor.MusasExtractor", # Alias
    "aema": "extractors.aema_extractor.AemaExtractor",
    "autodescuento": "extractors.autodescuento_extractor.AutodescuentoExtractor",
    "northgate": "extractors.northgate_extractor.NorthgateExtractor",
    "recoautos": "extractors.recoautos_extractor.RecoautosExtractor",
    "colomer": "extractors.colomer_extractor.ColomerExtractor",
    "wurth": "extractors.wurth_extractor.WurthExtractor",
    "candelar": "extractors.cantelar_extractor.CantelarExtractor",
    "cantelar": "extractors.cantelar_extractor.CantelarExtractor",
    "volkswagen": "extractors.volkswagen_extractor.VolkswagenExtractor",
    "oscaro": "extractors.oscaro_extractor.OscaroExtractor",
    "adevinta": "extractors.adevinta_extractor.AdevintaExtractor",
    "amazon": "extractors.amazon_extractor.AmazonExtractor",
    "coslauto": "extractors.coslauto_extractor.CoslautoExtractor"
}
VAT_RATE = "21%" 
ERROR_DATA: Tuple[Any, ...] = (
    "ERROR_EXTRACCION", None, None, None, None, None, None, None, None, None, None, None, "Error de lectura o formato." 
)

def _get_pdf_lines(pdf_path: str) -> List[str]:
    # ... (código para obtener líneas de PDF, sin cambios) ...
    lines: List[str] = []
    try:
        doc = fitz.open(pdf_path)
        texto = ''
        for page in doc:
            texto += page.get_text() or ''
        doc.close()
        lines = [line for line in texto.splitlines() if line.strip()] 
        return lines
    except Exception as e:
        print(f"❌ Error de Lectura PDF con fitz: {e}") 
        return []

def find_extractor_for_file(file_path: str) -> Optional[str]:
    # ... (código para encontrar extractor, sin cambios) ...
    
    nombre_archivo = os.path.basename(file_path).lower()
    for keyword, class_path in EXTRACTION_MAPPING.items():
        if keyword in nombre_archivo:
            return class_path
            
    try:
        lines = _get_pdf_lines(file_path)
        if not lines:
            return None
            
        temp_extractor = BaseInvoiceExtractor(lines, file_path) 
        extracted_data = temp_extractor.extract_all()
        
        cif_extraido_base = str(extracted_data[5]).replace('-', '').replace('.', '').strip().upper() if len(extracted_data) > 5 else None
        
        if cif_extraido_base:
            for keyword, class_path in EXTRACTION_MAPPING.items():
                try:
                    # La ruta ahora incluye 'extractors.'
                    module_path, class_name = class_path.rsplit('.', 1)
                    module = importlib.import_module(module_path) 
                    ExtractorClass = getattr(module, class_name)
                        
                    if hasattr(ExtractorClass, 'EMISOR_CIF') and ExtractorClass.EMISOR_CIF.upper() == cif_extraido_base:
                        return class_path
                except Exception:
                    continue 
            
    except Exception:
        pass

    return None

def extraer_datos(pdf_path: str, debug_mode: bool = False) -> Tuple[Any, ...]:
    """ (Se mantiene la lógica de extracción, la salida incluye debug_output) """
    
    def _pad_data(data: Tuple) -> Tuple:
        REQUIRED_FIELDS = 12
        if len(data) >= REQUIRED_FIELDS:
            return data[:REQUIRED_FIELDS]
        return data + (None,) * (REQUIRED_FIELDS - len(data))

    debug_output: str = "" 
    extracted_data_raw: Tuple = tuple() 
    file_extension = os.path.splitext(pdf_path)[1].lower()
    temp_img_to_delete: Optional[str] = None 

    try:
        # ... (CÓDIGO DE LECTURA Y OCR DEL PDF ORIGINAL) ...
        if file_extension in ['.jpg', '.jpeg', '.png', '.tiff', '.tif']:
            if not Image or not pytesseract:
                 debug_output = "ERROR: OCR (Tesseract/PIL) no disponible para imágenes."
                 return (*_pad_data(extracted_data_raw), debug_output)

            try:
                 ocr_text = pytesseract.image_to_string(Image.open(pdf_path), lang='spa')
                 lines = [line for line in ocr_text.splitlines() if line.strip()]
                 
                 if not lines:
                    debug_output = "❌ Fallo: OCR directo sobre la imagen no produjo texto."
                    return (*_pad_data(extracted_data_raw), debug_output)

                 debug_output += "✅ Éxito: OCR directo sobre imagen inicial.\n"
                 
            except Exception as e:
                 debug_output = f"❌ ERROR: Falló el procesamiento OCR de la imagen: {e}"
                 return (*_pad_data(extracted_data_raw), debug_output)
        
        else:
            if not os.path.exists(pdf_path):
                debug_output = f"Error: El archivo '{pdf_path}' no existe."
                return (*_pad_data(extracted_data_raw), debug_output)
            
            lines = _get_pdf_lines(pdf_path)

            if not lines and file_extension == ".pdf":
                debug_output += "⚠️ ADVERTENCIA: PDF sin capa de texto legible. Intentando con OCR (Rasterización)... \n"
                
                if Image and pytesseract:
                    try:
                        doc = fitz.open(pdf_path)
                        page = doc.load_page(0)
                        zoom = 300 / 72  
                        mat = fitz.Matrix(zoom, zoom)
                        pix = page.get_pixmap(matrix=mat, alpha=False)
                        doc.close()
                        
                        temp_img_name = f"ocr_temp_{os.path.splitext(os.path.basename(pdf_path))[0]}.png"
                        temp_img_to_delete = os.path.join(tempfile.gettempdir(), temp_img_name)
                        pix.save(temp_img_to_delete)

                        ocr_text = pytesseract.image_to_string(Image.open(temp_img_to_delete), lang='spa')
                        
                        lines = [line for line in ocr_text.splitlines() if line.strip()]

                        if lines:
                            debug_output += "✅ Éxito: OCR directo sobre imagen rasterizada. Texto encontrado.\n"
                        else:
                            debug_output += "❌ Fallo: OCR directo no produjo texto.\n"
                            return (*_pad_data(extracted_data_raw), debug_output)

                    except Exception as e:
                        debug_output += f"❌ ERROR: Falló la rasterización/OCR directo: {e}\n"
                        return (*_pad_data(extracted_data_raw), debug_output)
                else:
                    debug_output += "❌ ERROR: OCR (Tesseract/PIL) no disponible.\n"
                    return (*_pad_data(extracted_data_raw), debug_output)
        
        
        if not lines:
            debug_output += "Error: No se pudo leer texto del documento (después de todos los intentos)."
            return (*_pad_data(extracted_data_raw), debug_output)

        if debug_mode:
            debug_output += "🔍 DEBUG MODE ACTIVATED: Showing all lines in file\n\n"
            for i, linea in enumerate(lines):
                debug_output += f"Line {i:02d}: {linea}\n" 
            debug_output += "\n"


        # 3. Mapeo y Carga DINÁMICA del Extractor
        full_class_path = find_extractor_for_file(pdf_path) 
        doc_path_for_extractor = pdf_path 
        
        if full_class_path:
            debug_output += f"➡️ Extractor encontrado en mapeo: {full_class_path}\n"
            
            ExtractorClass = None
            try:
                ExtractorClass = _load_extractor_class_dynamic(full_class_path)
                
            except RuntimeError as e:
                debug_output += f"❌ ERROR en la carga dinámica del extractor: {e}\n"
                print(f"Error de carga dinámica: {e}")
                pass 
            
            if ExtractorClass:
                try:
                    extractor = ExtractorClass(lines, doc_path_for_extractor)
                    
                    if hasattr(extractor, 'extract_data') and callable(getattr(extractor, 'extract_data')):
                        data_dict = extractor.extract_data(lines)
                        
                        extracted_data_raw = (
                            data_dict.get('tipo'),
                            data_dict.get('fecha'),
                            data_dict.get('num_factura'),
                            data_dict.get('emisor'),
                            data_dict.get('cliente'),
                            data_dict.get('cif'),
                            data_dict.get('modelo'),
                            data_dict.get('matricula'),
                            data_dict.get('importe'),
                            data_dict.get('base'),
                            data_dict.get('iva'),
                            data_dict.get('tasas')
                        )
                    else:
                        extracted_data_raw = extractor.extract_all()
                    
                    debug_output += f"✅ Extracción exitosa con {full_class_path}.\n"
                    return (*_pad_data(extracted_data_raw), debug_output)
                    
                except Exception as e:
                    debug_output += f"❌ ERROR: Falló la ejecución del extractor para '{full_class_path}'. Error: {e}\n"
                    print(f"Error de ejecución del extractor: {e}")
        
        # 4. Extractor Genérico (Fallback)
        debug_output += "➡️ No specific invoice type detected or specific extractor failed. Using generic extraction function.\n"
        generic_extractor = BaseInvoiceExtractor(lines, doc_path_for_extractor)
        extracted_data_raw = generic_extractor.extract_all()
        
        return (*_pad_data(extracted_data_raw), debug_output)
        
    finally:
        if temp_img_to_delete and os.path.exists(temp_img_to_delete):
            try:
                os.remove(temp_img_to_delete)
            except Exception as e:
                print(f"Advertencia: No se pudo eliminar la imagen temporal OCR: {temp_img_to_delete}. Error: {e}")

# ----------------------------------------------------------------------
# FUNCIÓN DE EJECUCIÓN (run_extraction) 
# ----------------------------------------------------------------------
def run_extraction(ruta_input: str, debug_mode: bool, force_reprocess: bool) -> Tuple[List[Dict[str, Any]], str]:
    """ Procesa archivos, incluyendo la división condicional de PDFs. """
    
    if not ruta_input:
        messagebox.showerror("Error", "Debe seleccionar un archivo o directorio para procesar.")
        return [], "" 

    all_pdfs_to_process: List[str] = [] 
    SUPPORTED_EXTENSIONS = ('.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.tif')

    # ... (Lógica de búsqueda de archivos y división de PDF se mantiene igual) ...
    if os.path.isdir(ruta_input):
        for root, dirs, files in os.walk(ruta_input):
            if "facturas_Procesadas" in dirs:
                dirs.remove("facturas_Procesadas")
            
            for file in files:
                file_path = os.path.join(root, file)
                if file.lower().endswith(SUPPORTED_EXTENSIONS):
                    if file.lower().endswith('.pdf'):
                        try:
                            with open(file_path, 'rb') as f:
                                pdf_reader = PyPDF2.PdfReader(f)
                                num_pages = len(pdf_reader.pages)

                            is_pradilla = "pradilla" in file.lower()
                            
                            if num_pages > 1 and is_pradilla: 
                                original_dir = os.path.dirname(file_path)
                                processed_dir = os.path.join(original_dir, "facturas_Procesadas")
                                os.makedirs(processed_dir, exist_ok=True)
                                
                                pages_paths = split_pdf_into_single_page_files(file_path, original_dir)
                                all_pdfs_to_process.extend(pages_paths)
                                
                                try:
                                    shutil.move(file_path, processed_dir)
                                except Exception as move_error:
                                     print(f"Advertencia: No se pudo mover '{file}' a facturas_Procesadas. Error: {move_error}")
                                continue
                            else:
                                all_pdfs_to_process.append(file_path) 
                        except Exception:
                            all_pdfs_to_process.append(file_path)
                    else:
                        all_pdfs_to_process.append(file_path) 
    
    elif os.path.isfile(ruta_input):
        if ruta_input.lower().endswith(SUPPORTED_EXTENSIONS):
            if ruta_input.lower().endswith('.pdf'):
                try:
                    with open(ruta_input, 'rb') as f:
                        pdf_reader = PyPDF2.PdfReader(f)
                        num_pages = len(pdf_reader.pages)

                    is_pradilla = "pradilla" in os.path.basename(ruta_input).lower()
                    
                    if num_pages > 1 and is_pradilla: 
                        original_dir = os.path.dirname(ruta_input)
                        processed_dir = os.path.join(original_dir, "facturas_Procesadas")
                        os.makedirs(processed_dir, exist_ok=True)
                        pages_paths = split_pdf_into_single_page_files(ruta_input, original_dir)
                        all_pdfs_to_process.extend(pages_paths)
                        
                        try:
                            shutil.move(ruta_input, processed_dir)
                        except Exception as move_error:
                             print(f"Advertencia: No se pudo mover '{os.path.basename(ruta_input)}' a facturas_Procesadas. Error: {move_error}")
                    else:
                        all_pdfs_to_process.append(ruta_input)
                except Exception:
                    all_pdfs_to_process.append(ruta_input)
            else:
                all_pdfs_to_process.append(ruta_input)
    
    if not all_pdfs_to_process:
        messagebox.showwarning("Advertencia", "No se encontraron archivos PDF o de imagen válidos para procesar en la ruta seleccionada.")
        return [], ""

    all_extracted_rows_with_debug: List[Dict[str, Any]] = []

    def format_numeric_value(value, is_currency: bool = True) -> str:
        """ (Función helper para formatear números) """
        if value is None:
            return 'No encontrado'
        try:
            # CORREGIDO: Usamos la función de limpieza numérica para evitar errores de formato/conversión
            numeric_val = _clean_numeric_value(value) 
            formatted = f"{numeric_val:.2f}"
            if is_currency:
                return f"{formatted} €".replace('.', ',')
            return formatted.replace('.', ',')
        except ValueError:
            return str(value)

    # PROCESAMIENTO PRINCIPAL
    for archivo_a_procesar in all_pdfs_to_process:
        
        if not archivo_a_procesar or not isinstance(archivo_a_procesar, str):
            print(f"Skipping: Ruta de archivo inválida o vacía.")
            continue
        
        # Usa el flag force_reprocess
        if is_invoice_processed(archivo_a_procesar, force_reprocess=force_reprocess):
            print(f"Skipping: {os.path.basename(archivo_a_procesar)} ya fue procesado.")
            continue
            
        initial_file_to_process = archivo_a_procesar 
        tipo, fecha, numero_factura, emisor, cliente, cif, modelo, matricula, importe, base_imponible, iva, tasas, debug_output = extraer_datos(initial_file_to_process, debug_mode)
        
        
        final_path_on_disk = initial_file_to_process
        display_filename_in_csv = os.path.basename(initial_file_to_process)
        
        if tipo == "ERROR_EXTRACCION":
             print(f"❌ Error: Falló la extracción para {os.path.basename(initial_file_to_process)}")
             continue

        file_extension = os.path.splitext(initial_file_to_process)[1].lower()
        if file_extension in ['.jpg', '.jpeg', '.png', '.tiff', '.tif']:
            original_image_path = initial_file_to_process
            image_dir = os.path.dirname(original_image_path)
            img_procesada_dir = os.path.join(image_dir, "imgProcesada")
            os.makedirs(img_procesada_dir, exist_ok=True)
             
            try:
                 # Mueve la imagen original
                 shutil.move(original_image_path, os.path.join(img_procesada_dir, os.path.basename(original_image_path)))
            except shutil.Error:
                 pass
             
        current_row = {
            'Archivo': display_filename_in_csv.replace(',', '') ,
            '__OriginalPath__': final_path_on_disk,
            'Tipo': tipo or 'No encontrado',
            'Fecha': fecha or 'No encontrada',
            'Número de Factura': numero_factura or 'No encontrado',
            'Emisor': emisor or 'No encontrado',
            'Cliente': cliente or 'No encontrado',
            'CIF': cif or 'No encontrado',
            'Modelo': modelo or 'No encontrado',
            'Matricula': matricula or 'No encontrado',
            "Base": format_numeric_value(base_imponible, is_currency=False),
            "IVA": format_numeric_value(iva, is_currency=False),
            'Importe': format_numeric_value(importe, is_currency=True),
            'Tasas': format_numeric_value(tasas, is_currency=False),
            'DebugLines': debug_output, # AHORA SIEMPRE CONTIENE EL LOG COMPLETO DE LA EXTRACCIÓN
            'is_validated': 0 # NUEVO: Por defecto, no validada al ser nueva
        }
        
        if current_row['IVA'] in ['No encontrado', '']:
            current_row['IVA'] = '21%'
            
        # Guardar en BBDD (usa INSERT OR REPLACE)
        insert_invoice_data(current_row, final_path_on_disk, is_validated=0)
        all_extracted_rows_with_debug.append(current_row)

    # 🚨 Se elimina la generación de CSV aquí. La nueva función _export_validated_to_csv lo manejará.
    return all_extracted_rows_with_debug, ""


# --- Interfaz Gráfica (Tkinter) (InvoiceApp) ---
class InvoiceApp:
    def __init__(self, master):
        self.master = master
        master.title("Extractor de Facturas v2.5 (Redimensionable, Validación y Exportación Filtrada)")
        
        self.ruta_input_var = tk.StringVar(value="")
        self.debug_mode_var = tk.BooleanVar(value=False)
        self.debug_mode_var.trace_add("write", self._on_debug_mode_change)
        self.force_reprocess_var = tk.BooleanVar(value=False)
        
        self.tree: Optional[ttk.Treeview] = None
        self.debug_text_area: Optional[ScrolledText] = None
        self.button_call_generator: Optional[tk.Button] = None
        self.button_launch_file: Optional[tk.Button] = None
        
        # NUEVOS ATRIBUTOS PARA LA EDICIÓN DE CELDAS
        self._entry_editor = None # Para rastrear el widget Entry activo

        # Mapeo de columnas de la tabla a los campos de la BBDD
        self.db_column_map = {
            'Archivo': 'file_name',
            'Tipo': 'tipo',
            'Fecha': 'fecha',
            'Número de Factura': 'numero_factura',
            'Emisor': 'emisor',
            'Cliente': 'cliente',
            'CIF': 'cif',
            'Modelo': 'modelo',
            'Matricula': 'matricula',
            'Base': 'base',
            'IVA': 'iva',
            'Importe': 'importe',
            'Tasas': 'tasas'
        }

        # NUEVO: Añadir 'Validado' como primera columna visible
        self.columns = ['Validado', 'Archivo', 'Tipo', 'Fecha', 'Número de Factura', 'Emisor', 'Cliente', 'CIF', 'Modelo', 'Matricula', 'Base', 'IVA', 'Importe', 'Tasas']
        self.results_data: List[Dict[str, Any]] = []
        self.db_data: List[Dict[str, Any]] = []
        
        # --- Visor ---
        self.viewer_canvas: Optional[tk.Canvas] = None
        self.viewer_scrollbar: Optional[ttk.Scrollbar] = None
        self.current_image: Optional[tk.PhotoImage] = None
        self.canvas_image_id = None
        
        # NUEVO: Imágenes para el estado de validación
        self.validated_image: Any = None
        self.unvalidated_image: Any = None
        
        setup_database()
        self.load_all_data_from_db(is_initial_load=True)
        self.create_widgets()

    def _on_debug_mode_change(self, *args):
        if self.tree and self.button_call_generator and self.tree.get_children():
            # El botón del generador solo se habilita si hay selección Y modo debug activo
            selected_items = self.tree.selection()
            if self.debug_mode_var.get() and selected_items:
                self.button_call_generator['state'] = tk.NORMAL
            else:
                self.button_call_generator['state'] = tk.DISABLED
                
    def create_widgets(self):
        # --------------------------------------------------
        # Configuración de Estilo y Colores
        # --------------------------------------------------
        style = ttk.Style()
        # Configuración general del Treeview
        style.configure("Treeview", 
            background="#FFFFFF", 
            foreground="#000000",
            fieldbackground="#FFFFFF",
            rowheight=25 
        )
        # Configuración del color de fondo al seleccionar (LightBlue: #ADD8E6)
        style.map('Treeview',
            background=[('selected', '#ADD8E6')], 
            foreground=[('selected', 'black')]
        )
        
        # --- Configuración de Imágenes de Validación ---
        try:
            # Check (verde)
            check_img = Image.new('RGBA', (16, 16), color=(255, 255, 255, 0)) # Transparente
            draw = ImageDraw.Draw(check_img)
            draw.rectangle((1, 1, 14, 14), outline='green', fill='light green')
            # Dibujar un checkmark simple
            draw.line([(3, 8), (7, 12), (13, 3)], fill='green', width=2)
            self.validated_image = ImageTk.PhotoImage(check_img)
            
            # Uncheck (rojo)
            uncheck_img = Image.new('RGBA', (16, 16), color=(255, 255, 255, 0))
            draw = ImageDraw.Draw(uncheck_img)
            draw.rectangle((1, 1, 14, 14), outline='red', fill='light pink')
            self.unvalidated_image = ImageTk.PhotoImage(uncheck_img)
            
        except Exception:
             # Fallback a texto si no hay PIL/ImageTk o error
            self.validated_image = '✅'
            self.unvalidated_image = '❌'
        # --------------------------------------------------

        master = self.master
        
        # --- Frame Principal (para la tabla y el visor) ---
        main_frame = ttk.Frame(master, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True) 
        
        # Configurar la columna principal para que se expanda
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(1, weight=1)

        # --- Controles de Ruta y Opciones (Fila 0) ---
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=0, column=0, sticky='ew', pady=(0, 10))
        control_frame.grid_columnconfigure(1, weight=1)
        
        # 1. Selector de Ruta
        ttk.Label(control_frame, text="Ruta de Archivo/Directorio:").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        ruta_entry = ttk.Entry(control_frame, textvariable=self.ruta_input_var)
        ruta_entry.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        ttk.Button(control_frame, text="Seleccionar", command=self._select_path).grid(row=0, column=2, padx=5, pady=5)

        # 2. Botón de Procesar
        ttk.Button(control_frame, text="🔍 Procesar Facturas", command=self._process_files).grid(row=0, column=3, padx=5, pady=5)
        
        # 3. Opciones (Debug, Reprocesar, BBDD, Exportar)
        options_frame = ttk.Frame(control_frame)
        options_frame.grid(row=1, column=0, columnspan=4, sticky='w')
        
        ttk.Checkbutton(options_frame, text="Modo Debug", variable=self.debug_mode_var).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(options_frame, text="Forzar Reprocesado", variable=self.force_reprocess_var).pack(side=tk.LEFT, padx=5)
        ttk.Button(options_frame, text="Borrar BBDD Completa", command=self._delete_db_dialog).pack(side=tk.LEFT, padx=15)
        ttk.Button(options_frame, text="Cargar BBDD", command=lambda: self.load_all_data_from_db(is_initial_load=False)).pack(side=tk.LEFT, padx=5)
        # NUEVO BOTÓN: Exportar solo validados
        ttk.Button(options_frame, text="📄 Exportar CSV (Validados)", command=self._export_validated_to_csv).pack(side=tk.LEFT, padx=5)


        # PanedWindow que separa la tabla (izq) del visor (der)
        self.paned_window = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        self.paned_window.grid(row=1, column=0, sticky='nsew', pady=(0, 10))
        
        # --- Frame para el Visor de Debug/PDF (Panel Lateral) ---
        viewer_frame = ttk.Frame(self.paned_window)
        # Añadir al PanedWindow, dándole 1 vez más de espacio inicial
        self.paned_window.add(viewer_frame, weight=1) 
        
        viewer_frame.grid_rowconfigure(0, weight=1)
        viewer_frame.grid_rowconfigure(1, weight=1) # El debug/log también se expande
        viewer_frame.grid_columnconfigure(0, weight=1)
        
        # Título para el visor de PDF
        ttk.Label(viewer_frame, text="Visor de Documento (Página 1)").grid(row=0, column=0, sticky='new', pady=(0, 5))
        
        # Canvas para el visor de PDF/Imagen
        canvas_container = ttk.Frame(viewer_frame)
        canvas_container.grid(row=0, column=0, sticky='nsew')
        canvas_container.grid_rowconfigure(0, weight=1)
        canvas_container.grid_columnconfigure(0, weight=1)
        
        self.viewer_canvas = tk.Canvas(canvas_container, bg="white", highlightthickness=0)
        self.viewer_canvas.grid(row=0, column=0, sticky='nsew')
        
        # Scrollbar Vertical para el Canvas
        self.viewer_scrollbar = ttk.Scrollbar(canvas_container, orient="vertical", command=self.viewer_canvas.yview)
        self.viewer_scrollbar.grid(row=0, column=1, sticky='ns')
        self.viewer_canvas.config(yscrollcommand=self.viewer_scrollbar.set)
        
        # Enlazar el evento de redimensionamiento
        self.viewer_canvas.bind('<Configure>', self._on_canvas_resize)
        self.viewer_canvas.bind('<MouseWheel>', self._on_mousewheel) # Windows/macOS scroll
        self.viewer_canvas.bind('<Button-4>', self._on_mousewheel) # Linux scroll up
        self.viewer_canvas.bind('<Button-5>', self._on_mousewheel) # Linux scroll down


        # Título para el área de Debug
        ttk.Label(viewer_frame, text="Log / Debug Lines").grid(row=2, column=0, sticky='new', pady=(10, 5))
        
        # Área de texto para debug
        self.debug_text_area = ScrolledText(viewer_frame, wrap=tk.WORD, height=10, font=('Consolas', 9))
        self.debug_text_area.grid(row=3, column=0, sticky='nsew')
        self.debug_text_area.config(state=tk.DISABLED) # Desactivar edición


         # --- Frame para la Tabla (Resultados) ---
        tree_frame = ttk.Frame(self.paned_window)
        # Añadir al PanedWindow, dándole 2 veces más de espacio inicial
        self.paned_window.add(tree_frame, weight=2) 
        
        # 1. Configurar el tree_frame para que el treeview dentro se expanda
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # Scrollbar vertical
        vsb = ttk.Scrollbar(tree_frame, orient="vertical")
        vsb.grid(row=0, column=1, sticky='ns')
        
        # Scrollbar Horizontal
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal")
        hsb.grid(row=1, column=0, sticky='ew')
        
        self.tree = ttk.Treeview(
            tree_frame, 
            columns=self.columns, 
            show='headings', 
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set, # Conectar al scroll horizontal
            selectmode="browse"
        )
        
        # Conectar scrollbars al treeview
        vsb.config(command=self.tree.yview)
        hsb.config(command=self.tree.xview) 

        self.tree.grid(row=0, column=0, sticky='nsew') 

        # --- Configuración de Columnas ---
        min_widths = {
            'Validado': 50, 'Archivo': 150, 'Tipo': 80, 'Fecha': 90, 'Número de Factura': 120, 
            'Emisor': 120, 'Cliente': 100, 'CIF': 90, 'Modelo': 80, 
            'Matricula': 80, 'Base': 80, 'IVA': 60, 'Importe': 90, 'Tasas': 70
        }
        
        for col in self.columns:
            # Eliminar la coma para que no aparezca en el encabezado
            display_name = col.replace(',', '') 
            self.tree.heading(col, text=display_name, command=lambda c=col: self._sort_treeview(c), anchor='center')
            self.tree.column(col, minwidth=min_widths.get(col, 50), width=min_widths.get(col, 50), stretch=tk.NO, anchor='center')

        # Bind para toggle de validación y para inicio de edición (NUEVO)
        self.tree.bind('<Button-1>', self._on_cell_click) # NUEVO: Usamos el clic simple para edición/validación
        
        # Bind para la selección (dispara la actualización del visor/debug y el estado de los botones)
        self.tree.bind('<<TreeviewSelect>>', self._on_item_select)
        # ELIMINADA la línea: self.tree.bind('<Double-1>', self._on_item_double_click) 
        # --- Botones de Acción (Generador y Lanzar Archivo) ---
        action_frame = ttk.Frame(main_frame)
        action_frame.grid(row=2, column=0, sticky='ew', pady=(10, 0))
        action_frame.columnconfigure(0, weight=1)
        action_frame.columnconfigure(1, weight=1)

        self.button_launch_file = ttk.Button(action_frame, text="📂 Abrir Archivo Seleccionado", command=self._launch_selected_file)
        self.button_launch_file.grid(row=0, column=0, sticky='e', padx=10)
        self.button_launch_file['state'] = tk.DISABLED

        self.button_call_generator = ttk.Button(action_frame, text="⚙️ Llamar a Generador de Extractor", command=self._call_extractor_generator)
        self.button_call_generator.grid(row=0, column=1, sticky='w', padx=10)
        self.button_call_generator['state'] = tk.DISABLED

        # Cargar los datos iniciales
        self._populate_treeview()


    def _on_canvas_resize(self, event):
        """Ajusta la región de scroll del canvas cuando se redimensiona."""
        if self.canvas_image_id:
            bbox = self.viewer_canvas.bbox(self.canvas_image_id)
            if bbox:
                # La región de scroll debe ser al menos el tamaño de la imagen.
                self.viewer_canvas.config(scrollregion=bbox)
        else:
            # Si no hay imagen, centrar el mensaje de "Archivo no seleccionado"
            self._clear_viewer(text="Seleccione una fila de la tabla para ver el documento.")

    def _on_mousewheel(self, event):
        """Maneja el evento de rueda del ratón para hacer scroll vertical en el canvas."""
        # Determinar la dirección del scroll
        if sys.platform == "win32" or sys.platform == "darwin": # Windows/macOS
            if event.delta > 0:
                self.viewer_canvas.yview_scroll(-1, "units")
            else:
                self.viewer_canvas.yview_scroll(1, "units")
        else: # Linux
            if event.num == 4:
                self.viewer_canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                self.viewer_canvas.yview_scroll(1, "units")


    # --------------------------------------------------
    # FUNCIONES DE VISOR CON SCROLL 
    # --------------------------------------------------
    def _clear_viewer(self, text: str):
        """Helper para limpiar el canvas y mostrar un mensaje, centrado dinámicamente."""
        if not self.viewer_canvas:
            return
        
        self.viewer_canvas.delete("all")
        self.current_image = None
        self.canvas_image_id = None
        
        # Asegurarse de que el widget tenga dimensiones antes de calcular el centro
        self.viewer_canvas.update_idletasks()
        width = self.viewer_canvas.winfo_width()
        height = self.viewer_canvas.winfo_height()

        # Muestra el mensaje centrado
        if width > 1 and height > 1:
            self.viewer_canvas.create_text(
                width / 2, 
                height / 2, 
                text=text, 
                fill="black", 
                anchor="center", 
                justify="center",
                width=width - 20 # Limitar el ancho del texto
            )
        else:
            # Si no tiene dimensiones aún, lo colocamos en 5,5 para que se muestre.
            self.viewer_canvas.create_text(5, 5, text=text, fill="black", anchor="nw") 

        # Resetear el scroll region (importante para evitar scroll vacio)
        self.viewer_canvas.config(scrollregion=(0, 0, 0, 0))


    def _display_file_in_viewer(self, file_path: str):
        """Muestra la primera página de un PDF o una imagen en el panel lateral CON SCROLL."""
        if not Image or not ImageTk:
            self._clear_viewer(text="Visor no disponible (Faltan módulos PIL/ImageTk).")
            return
        
        if not file_path or not os.path.exists(file_path):
            self._clear_viewer(text="Archivo no encontrado o no válido.")
            return

        # 1. Limpiar el canvas antes de dibujar
        self.viewer_canvas.delete("all")
        self.current_image = None
        self.canvas_image_id = None
        
        temp_img: Optional[Image.Image] = None
        file_extension = os.path.splitext(file_path)[1].lower()

        try:
            # --- Lógica de Renderizado (A 150 DPI) ---
            if file_extension == ".pdf":
                if not fitz:
                    self._clear_viewer(text="PyMuPDF (fitz) no disponible para PDFs.")
                    return
                    
                doc = fitz.open(file_path)
                page = doc.load_page(0)
                
                # Renderizar la página a una resolución de 150 DPI
                DPI = 150
                zoom = DPI / 72
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                doc.close()
                
                pil_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                temp_img = pil_img
                
            elif file_extension in ['.jpg', '.jpeg', '.png', '.tiff', '.tif']:
                pil_img = Image.open(file_path)
                temp_img = pil_img
            else:
                self._clear_viewer(text=f"Tipo de archivo no soportado: {file_extension}")
                return

            # --- Preparación para Tkinter ---
            # Redimensionar la imagen si es mucho más ancha que el canvas
            canvas_width = self.viewer_canvas.winfo_width()
            if canvas_width < 100:
                 # Esperar a que el canvas se configure
                self.viewer_canvas.update_idletasks()
                canvas_width = self.viewer_canvas.winfo_width()
                if canvas_width < 100:
                    canvas_width = 300 # Valor por defecto si falla la obtención

            
            # Si la imagen es más ancha que el canvas (con un margen), redimensionar
            max_view_width = canvas_width - 20 # Margen de 10px a cada lado
            if temp_img.width > max_view_width:
                ratio = max_view_width / temp_img.width
                new_height = int(temp_img.height * ratio)
                temp_img = temp_img.resize((max_view_width, new_height), Image.Resampling.LANCZOS)
                
            self.current_image = ImageTk.PhotoImage(temp_img)

            # 2. Dibujar en el canvas
            self.canvas_image_id = self.viewer_canvas.create_image(
                10, 10, # Pequeño margen
                image=self.current_image, 
                anchor="nw"
            )

            # 3. Configurar la región de scroll para incluir toda la imagen
            # El bbox devuelve las coordenadas (x1, y1, x2, y2) del elemento en el canvas.
            bbox = self.viewer_canvas.bbox(self.canvas_image_id) 
            if bbox:
                self.viewer_canvas.config(scrollregion=bbox)
                self.viewer_canvas.yview_moveto(0) # Mover a la parte superior
        
        except Exception as e:
            traceback.print_exc()
            self._clear_viewer(text=f"Error al mostrar el archivo:\n{e}")
            
    # --------------------------------------------------
    # FUNCIONES DE LÓGICA DE LA APP 
    # --------------------------------------------------
    
    def format_numeric_value(self, value, is_currency: bool = True) -> str:
        """ Método helper para formatear números (copia de la función en global scope) """
        if value is None:
            return 'No encontrado'
        try:
            numeric_val = _clean_numeric_value(value) 
            formatted = f"{numeric_val:.2f}"
            if is_currency:
                return f"{formatted} €".replace('.', ',')
            return formatted.replace('.', ',')
        except ValueError:
            return str(value)

    def _select_path(self):
        """Selecciona un archivo o directorio."""
        path = filedialog.askopenfilename(
            title="Seleccionar archivo (PDF/Imagen) o Directorio (para procesamiento masivo)",
            filetypes=[("Documentos soportados", "*.pdf *.jpg *.jpeg *.png *.tiff *.tif")]
        )
        if not path:
            path = filedialog.askdirectory(
                title="Seleccionar Directorio (para procesamiento masivo)"
            )
            
        if path:
            self.ruta_input_var.set(path)
            self.tree.selection_remove(self.tree.selection()) # Limpiar selección previa

    def _process_files(self):
        """Ejecuta la extracción y actualiza la tabla."""
        ruta_input = self.ruta_input_var.get()
        debug_mode = self.debug_mode_var.get()
        force_reprocess = self.force_reprocess_var.get()

        if not ruta_input:
            messagebox.showwarning("Advertencia", "Debe seleccionar un archivo o directorio primero.")
            return

        try:
            self.results_data, csv_path = run_extraction(ruta_input, debug_mode, force_reprocess)
            
            # Después de procesar, recargar todos los datos de la BBDD
            self.load_all_data_from_db(is_initial_load=False)
            
            if self.results_data:
                messagebox.showinfo("Éxito", f"Procesamiento finalizado. {len(self.results_data)} facturas extraídas/actualizadas.")
            else:
                 # Si no se procesó nada, puede ser porque ya estaba todo en la BBDD
                 messagebox.showinfo("Proceso Terminado", "No se encontraron nuevos archivos para procesar o todos ya estaban en la base de datos (y no se forzó el reprocesado).")

        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error de Procesamiento", f"Ocurrió un error inesperado durante la extracción: {e}")

    def _export_validated_to_csv(self):
        """Exporta SOLO las facturas marcadas como validadas a un archivo CSV."""
        
        # 1. Filtrar los datos validados
        validated_rows = [row for row in self.db_data if row.get('is_validated') == 1]
        
        if not validated_rows:
            messagebox.showwarning("Advertencia", "No hay facturas marcadas como validadas para exportar.")
            return

        # 2. Abrir diálogo para seleccionar dónde guardar
        csv_output_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            title="Guardar CSV de Facturas Validadas",
            initialfile='facturas_validadas_resultado.csv'
        )

        if not csv_output_path:
            return

        # 3. Preparar los datos para el CSV
        csv_data = []
        # Excluir 'Validado' y campos internos para la exportación
        fieldnames = ['Archivo', 'Tipo', 'Fecha', 'Número de Factura', 'Emisor', 'Cliente', 'CIF', 'Modelo', 'Matricula', "Base", "IVA", 'Importe', 'Tasas']

        for row_with_debug in validated_rows:
            row_csv = row_with_debug.copy()
            # Eliminar campos internos y de debug
            row_csv.pop('DebugLines', None)
            row_csv.pop('__OriginalPath__', None)
            row_csv.pop('is_validated', None)
            
            # Asegurar el orden correcto de las columnas y el formato
            ordered_row = {field: row_csv.get(field, '') for field in fieldnames}
            csv_data.append(ordered_row)
            
        # 4. Escribir el CSV
        try:
            with open(csv_output_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
                # Usar ';' como delimitador para compatibilidad con Excel
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=';')
                writer.writeheader()
                writer.writerows(csv_data)
                messagebox.showinfo("Éxito", f"Exportación finalizada. {len(validated_rows)} facturas validadas exportadas.\nCSV guardado en: {csv_output_path}")

        except Exception as e:
            messagebox.showerror("Error al escribir CSV", f"No se pudo escribir el archivo CSV: {e}")


    def load_all_data_from_db(self, is_initial_load: bool = False):
        """Carga todos los datos de la BBDD a self.db_data y repopula la tabla."""
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row # Permite acceder a las columnas por nombre
        cursor = conn.cursor()
        
        # Selecciona todas las columnas, incluyendo log_data y la NUEVA is_validated
        cursor.execute("SELECT * FROM processed_invoices ORDER BY procesado_en DESC")
        
        self.db_data = []
        for row in cursor.fetchall():
            # Crear una fila que coincida con el formato de 'current_row' en run_extraction
            # NOTA: Los valores numéricos vienen como float, los convertimos a string para mostrar.
            
            # NOTA IMPORTANTE: Se ha movido el método format_numeric_value a la clase para que sea accesible
            
            formatted_row = {
                'Archivo': row['file_name'] or os.path.basename(row['path']),
                '__OriginalPath__': row['path'], # Ruta completa para lanzar/debug
                'Tipo': row['tipo'],
                'Fecha': row['fecha'],
                'Número de Factura': row['numero_factura'],
                'Emisor': row['emisor'],
                'Cliente': row['cliente'],
                'CIF': row['cif'],
                'Modelo': row['modelo'],
                'Matricula': row['matricula'],
                "Base": self.format_numeric_value(row['base'], is_currency=False),
                "IVA": self.format_numeric_value(row['iva'], is_currency=False),
                'Importe': self.format_numeric_value(row['importe'], is_currency=True),
                'Tasas': self.format_numeric_value(row['tasas'], is_currency=False),
                'DebugLines': row['log_data'] or 'No hay información de log disponible.',
                'is_validated': row['is_validated'] # NUEVO: Cargar estado de validación
            }
            self.db_data.append(formatted_row)

        conn.close()
        
        if not is_initial_load and not self.db_data:
            messagebox.showinfo("Base de Datos", "La base de datos se ha cargado/está vacía.")
            
        self._populate_treeview()
        
    def _populate_treeview(self):
        """Limpia y rellena el Treeview con los datos actuales de la BBDD (self.db_data)."""
        if not self.tree:
            return
            
        # 1. Limpiar todos los elementos existentes
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        # 2. Insertar los nuevos datos
        for row_data in self.db_data:
            # Determinar el valor de visualización para la columna 'Validado'
            is_validated = row_data.get('is_validated') == 1
            validation_display = self.validated_image if is_validated else self.unvalidated_image
            
            # Construir la lista de valores en el orden de self.columns
            values = []
            for col in self.columns:
                if col == 'Validado':
                    values.append('') # Usaremos el truco de la imagen para la primera columna
                else:
                    values.append(row_data.get(col) or '')
            
            # Usar la ruta original como iid (identificador interno) para el mapeo
            iid = row_data.get('__OriginalPath__')
            
            # Insertar la fila
            # Se pasa un valor vacío en la primera columna para que `item` pueda usar la imagen
            self.tree.insert('', tk.END, iid=iid, values=values)
            
            # Si es imagen (Photoimage), se asocia a la fila (sólo funciona bien en la primera columna)
            if isinstance(validation_display, tk.PhotoImage):
                 self.tree.item(iid, image=validation_display)
            else:
                 # Si es texto (fallback), lo mostramos en la celda
                 self.tree.set(iid, 'Validado', validation_display)
            
        # Limpiar el visor y el log después de recargar
        self._clear_viewer(text="Seleccione una fila de la tabla para ver el documento.")
        if self.debug_text_area:
            self.debug_text_area.config(state=tk.NORMAL)
            self.debug_text_area.delete('1.0', tk.END)
            self.debug_text_area.config(state=tk.DISABLED)
            
        self.button_launch_file['state'] = tk.DISABLED
        self.button_call_generator['state'] = tk.DISABLED

    # --------------------------------------------------
    # FUNCIONES DE EDICIÓN DE CELDAS (NUEVAS)
    # --------------------------------------------------
    def _on_cell_click(self, event):
        """
        Maneja el clic simple en una celda para iniciar la edición o el toggle de validación.
        """
        
        # Si hay un editor activo, destrúyelo sin guardar para evitar dobles acciones
        if self._entry_editor and self._entry_editor.winfo_exists():
            # Si se hace clic en otro lugar mientras el editor está activo, 
            # el evento FocusOut debería manejar el guardado, pero destruirlo aquí 
            # previene la superposición si FocusOut falló o el clic es muy rápido.
            self._entry_editor.destroy()
            self._entry_editor = None
        
        # 1. Identificar la celda y la columna
        region = self.tree.identify_region(event.x, event.y)
        item = self.tree.identify_row(event.y)
        column_id = self.tree.identify_column(event.x)
        
        if not item or region not in ["cell", "tree"]:
             # Si no hay fila, o se clica en el header/scrollbar, no hacemos nada
             return 

        column_name = self.tree.heading(column_id, 'text')
        
        # A. Si se clica en la columna 'Validado' (#1), hacer toggle
        if column_id == '#1' or (region == "tree" and self.columns[0] == column_name):
            self._toggle_validation_on_click(event)
            return

        # B. Si se clica en cualquier otra columna editable, iniciar edición
        if column_name in self.db_column_map:
            
            # 2. Obtener el valor actual y la posición
            x, y, width, height = self.tree.bbox(item, column_id)
            column_index = self.columns.index(column_name)
            current_value = self.tree.item(item, 'values')[column_index]

            # 3. Crear y posicionar el widget Entry
            self._entry_editor = ttk.Entry(self.tree)
            self._entry_editor.insert(0, current_value)
            self._entry_editor.place(x=x, y=y, width=width, height=height)
            
            # 4. Configurar los bindings del editor
            # El item es el IID del Treeview, que es la ruta completa ('path')
            self._entry_editor.bind('<Return>', lambda e: self._on_entry_save(item, column_name, self._entry_editor))
            self._entry_editor.bind('<FocusOut>', lambda e: self._on_entry_save(item, column_name, self._entry_editor))
            
            self._entry_editor.focus_set()
            self._entry_editor.select_range(0, tk.END) # Seleccionar todo el texto para fácil edición
            
        else:
             # Si el clic no fue en una celda editable ni en 'Validado', es solo una selección normal
             self.tree.selection_set(item)
             self._on_item_select(None)


    def _on_entry_save(self, item_path, column_name, entry_widget):
        """Guarda el valor de la celda en el Treeview y en la BBDD."""
        
        # Evitar guardar si el editor ya ha sido destruido
        if entry_widget is None or not entry_widget.winfo_exists():
            return
            
        # Si el evento FocusOut se dispara antes que el Return, y el widget ya se destruyó
        if self._entry_editor is None:
            return

        new_value = entry_widget.get().strip()
        
        column_index = self.columns.index(column_name)
        current_values = list(self.tree.item(item_path, 'values'))
        old_value = current_values[column_index]

        # 1. Destruir el editor inmediatamente (antes de guardar)
        # Esto previene el loop de FocusOut si el guardado tarda.
        entry_widget.destroy()
        self._entry_editor = None
        
        # Si el valor no cambió, salir
        if old_value == new_value:
            return

        # 2. Actualizar la BBDD
        db_column = self.db_column_map[column_name]
        rows_affected = update_invoice_field(item_path, db_column, new_value)
        
        if rows_affected > 0:
            # 3. Actualizar el Treeview
            
            # Formatear el valor si es numérico para mostrar el formato correcto (con ',')
            if column_name in ['Base', 'IVA', 'Tasas', 'Importe']:
                 # Si es una columna numérica, usar el método de formateo de la clase
                 new_value = self.format_numeric_value(new_value, is_currency=(column_name == 'Importe'))
                 
            current_values[column_index] = new_value
            self.tree.item(item_path, values=current_values)
            
            # 4. Recalcular importes si la columna es numérica clave y no es importe (para evitar loops)
            if column_name in ['Base', 'IVA'] and column_name != 'Importe':
                 self._recalculate_totals_for_item(item_path)
                 
            # 5. Actualizar la caché de la aplicación (self.db_data)
            # Esto asegura que la carga de la BBDD no sobreescriba el valor
            selected_row = next((row for row in self.db_data if row.get('__OriginalPath__') == item_path), None)
            if selected_row:
                 selected_row[column_name] = new_value # Guardar el valor formateado
             
        else:
            # Mostrar advertencia si no se pudo guardar
            messagebox.showwarning("Error de Guardado", f"No se pudo guardar el valor '{new_value}' en la BBDD.")
        
    def _recalculate_totals_for_item(self, item_path: str):
        """
        Intenta recalcular Base, IVA e Importe después de una edición
        de un campo numérico clave.
        """
        
        # 1. Obtener los valores actuales (incluyendo el valor recién guardado)
        current_values_list = list(self.tree.item(item_path, 'values'))
        
        try:
            base_str = current_values_list[self.columns.index('Base')]
            iva_str = current_values_list[self.columns.index('IVA')]
            tasas_str = current_values_list[self.columns.index('Tasas')]

            # Limpiar y convertir a float para cálculo
            base_val = _clean_numeric_value(base_str)
            iva_val = _clean_numeric_value(iva_str)
            tasas_val = _clean_numeric_value(tasas_str)
            
        except (ValueError, IndexError):
            return

        # Recalcular Importe Total
        new_importe_val = base_val + iva_val + tasas_val
        new_importe_str = self.format_numeric_value(new_importe_val, is_currency=True)
        
        # 2. Actualizar Treeview y BBDD con el nuevo Importe si es necesario
        importe_index = self.columns.index('Importe')
        current_importe_str = current_values_list[importe_index]
        
        if current_importe_str != new_importe_str:
            
            # Guardar en BBDD primero
            update_invoice_field(item_path, self.db_column_map['Importe'], new_importe_val)
            
            # Actualizar Treeview
            current_values_list[importe_index] = new_importe_str
            self.tree.item(item_path, values=current_values_list)
            
            # Actualizar la caché de la aplicación (self.db_data)
            selected_row = next((row for row in self.db_data if row.get('__OriginalPath__') == item_path), None)
            if selected_row:
                 selected_row['Importe'] = new_importe_str


    def _toggle_validation_on_click(self, event):
        """Alterna el estado de validación al hacer clic en la columna 'Validado'."""
        if not self.tree:
            return
            
        # Ya sabemos que el clic fue en la columna de validación gracias a _on_cell_click
        selected_item = self.tree.identify_row(event.y)
        
        # Encontrar la fila seleccionada en self.db_data por su iid
        selected_row = next((row for row in self.db_data if row.get('__OriginalPath__') == selected_item), None)

        if selected_row:
            current_validation_state = selected_row.get('is_validated', 0)
            new_validation_state = 1 if current_validation_state == 0 else 0
            
            # 1. Actualizar la BBDD
            self._update_db_validation(selected_item, new_validation_state)
            
            # 2. Actualizar self.db_data
            selected_row['is_validated'] = new_validation_state
            
            # 3. Actualizar la vista del Treeview
            validation_display = self.validated_image if new_validation_state == 1 else self.unvalidated_image
            
            if isinstance(validation_display, tk.PhotoImage):
                # Si es imagen, actualizar la imagen asociada a la fila
                self.tree.set(selected_item, 'Validado', '') 
                self.tree.item(selected_item, image=validation_display)
            else:
                # Si es texto (fallback), lo mostramos en la celda
                self.tree.set(selected_item, 'Validado', validation_display) 

            # Asegurar que la fila permanezca seleccionada para el visor/log
            self.tree.selection_set(selected_item)
            self._on_item_select(None)
        else:
            # Si la fila no se encuentra, simplemente seleccionar
            self.tree.selection_set(selected_item)
            self._on_item_select(None)


    def _update_db_validation(self, file_path: str, is_validated: int):
        """Actualiza el estado de validación de un registro en la BBDD."""
        if not file_path:
            return
            
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE processed_invoices 
                SET is_validated = ? 
                WHERE path = ?
            """, (is_validated, file_path))
            conn.commit()
        except Exception as e:
            messagebox.showerror("Error DB", f"Fallo al actualizar el estado de validación: {e}")
        finally:
            conn.close()

    def _on_item_select(self, event):
        """Maneja la selección de una fila en el Treeview."""
        if not self.tree:
            return
            
        # Si el editor está activo, destruirlo antes de cambiar de foco
        if self._entry_editor and self._entry_editor.winfo_exists():
            # No lo destruimos aquí, el FocusOut ya debió haberlo manejado.
            # Pero si se selecciona otra fila, el FocusOut no se dispara correctamente.
            # Por simplicidad, si la selección no es la misma, lo manejamos.
            pass
            
        selected_items = self.tree.selection()
        if not selected_items:
            # Limpiar si no hay nada seleccionado
            self.button_launch_file['state'] = tk.DISABLED
            self.button_call_generator['state'] = tk.DISABLED
            self._clear_viewer(text="Seleccione una fila de la tabla para ver el documento.")
            if self.debug_text_area:
                self.debug_text_area.config(state=tk.NORMAL)
                self.debug_text_area.delete('1.0', tk.END)
                self.debug_text_area.config(state=tk.DISABLED)
            return

        # Solo procesamos el primer elemento seleccionado
        selected_iid = selected_items[0]
        
        # Buscar el elemento en self.db_data por su iid (que es el __OriginalPath__)
        selected_row = next((row for row in self.db_data if row.get('__OriginalPath__') == selected_iid), None)
        
        if selected_row:
            file_path = selected_row.get('__OriginalPath__')
            debug_lines = selected_row.get('DebugLines') or "No hay información de log disponible."
            
            # Habilitar botones
            self.button_launch_file['state'] = tk.NORMAL
            
            # Habilitar el botón del generador solo si está en modo debug
            if self.debug_mode_var.get():
                self.button_call_generator['state'] = tk.NORMAL
            else:
                 self.button_call_generator['state'] = tk.DISABLED

            # Mostrar archivo en el visor
            self._display_file_in_viewer(file_path)

            # Mostrar debug/log en el área de texto
            if self.debug_text_area:
                self.debug_text_area.config(state=tk.NORMAL)
                self.debug_text_area.delete('1.0', tk.END)
                self.debug_text_area.insert('1.0', debug_lines)
                self.debug_text_area.config(state=tk.DISABLED)
                
    # Eliminado _on_item_double_click
    def _sort_treeview(self, col):
        """Ordena el Treeview por la columna seleccionada."""
        # Obtener los datos actuales de la tabla
        l = [(self.tree.set(k, col), k) for k in self.tree.get_children('')]
        
        # Detección y conversión numérica
        try:
            # Intentar limpiar y convertir a float para ordenación numérica
            cleaned_l = []
            for item, iid in l:
                clean_item = str(item).replace('€', '').replace(',', '.').strip()
                try:
                    cleaned_l.append((float(clean_item), iid))
                except ValueError:
                    cleaned_l.append((item, iid)) # Si no es número, se queda como string

            l = cleaned_l
            
        except Exception:
            # Si hay error, ordenar como strings
            pass
            
        # Determinar si el orden es ascendente o descendente
        if self.tree.heading(col, "reverse"):
            l.sort(reverse=True)
            self.tree.heading(col, reverse=False)
        else:
            l.sort(reverse=False)
            self.tree.heading(col, reverse=True)
            
        # Reordenar los elementos en el Treeview
        for index, (val, k) in enumerate(l):
            self.tree.move(k, '', index)

    def _launch_selected_file(self):
        """Abre el archivo seleccionado en el sistema operativo."""
        selected_items = self.tree.selection()
        if selected_items:
            selected_iid = selected_items[0]
            selected_row = next((row for row in self.db_data if row.get('__OriginalPath__') == selected_iid), None)
            
            if selected_row:
                ruta_archivo = selected_row.get('__OriginalPath__')
                if not ruta_archivo or not os.path.exists(ruta_archivo):
                    messagebox.showerror("Error", "Ruta de archivo no válida.")
                    return
                
                try:
                    if sys.platform == "win32":
                        os.startfile(ruta_archivo)
                    elif sys.platform == "darwin": # macOS
                        subprocess.call(['open', ruta_archivo])
                    else: # linux
                        subprocess.call(['xdg-open', ruta_archivo])
                        
                except Exception as e:
                    messagebox.showerror("Error", f"No se pudo abrir el archivo. Error: {e}")

    def _delete_db_dialog(self):
        """Muestra un diálogo de confirmación para borrar toda la tabla de la BBDD."""
        response = messagebox.askyesno(
            "Confirmación de Borrado",
            "¿Está seguro de que desea ELIMINAR COMPLETAMENTE la tabla de resultados de la base de datos (se perderán todos los datos)?\n\nEsta acción es IRREVERSIBLE."
        )
        if response:
            if delete_entire_database_schema():
                messagebox.showinfo("Éxito", "La tabla 'processed_invoices' ha sido eliminada con éxito.")
                self.db_data = []
                self._populate_treeview()
            else:
                messagebox.showerror("Error", "Fallo al intentar eliminar la tabla de la base de datos.")

    def _call_extractor_generator(self):
        """Lanza el script extractor_generator_gui.py con los datos de la fila seleccionada. SOLO con botón."""
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("Advertencia", "Debe seleccionar una fila primero.")
            return

        if not self.debug_mode_var.get():
             messagebox.showwarning("Advertencia", "Debe activar el Modo Debug para lanzar el Generador de Extractor.")
             return
            
        selected_iid = selected_items[0]
        selected_row = next((row for row in self.db_data if row.get('__OriginalPath__') == selected_iid), None)

        if selected_row:
            try:
                # 1. Preparar los datos
                ruta_archivo = selected_row.get('__OriginalPath__', '')
                nombre_base_archivo = os.path.splitext(os.path.basename(ruta_archivo))[0]
                debug_lines = selected_row.get('DebugLines', 'No hay debug data.')

                # Limpiar y obtener valores para pasarlos como argumentos de línea de comandos
                tipo = selected_row.get('Tipo', '')
                fecha = selected_row.get('Fecha', '')
                num_factura = selected_row.get('Número de Factura', '')
                emisor = selected_row.get('Emisor', '')
                cliente = selected_row.get('Cliente', '')
                cif = selected_row.get('CIF', '')
                modelo = selected_row.get('Modelo', '')
                matricula = selected_row.get('Matricula', '')
                
                # Para Base, IVA, Importe, Tasas: Limpiar para pasar solo el valor numérico (sin '€' ni comas)
                def clean_for_cli(value_str):
                    # Usar _clean_numeric_value para la limpieza y luego convertir a string
                    return str(_clean_numeric_value(value_str))

                base = clean_for_cli(selected_row.get('Base', ''))
                iva = clean_for_cli(selected_row.get('IVA', ''))
                importe = clean_for_cli(selected_row.get('Importe', ''))
                tasas = clean_for_cli(selected_row.get('Tasas', ''))

                # 2. Construir el comando (usando sys.executable para compatibilidad con ejecutables)
                comando = [
                    sys.executable, 
                    'extractor_generator_gui.py', 
                    ruta_archivo,              # 1
                    nombre_base_archivo,       # 2 (Extractor Name Suggestion)
                    debug_lines,               # 3 (Debug Lines)
                    tipo,                      # 4
                    fecha,                     # 5
                    num_factura,               # 6
                    emisor,                    # 7
                    cliente,                   # 8
                    cif,                       # 9
                    modelo,                    # 10
                    matricula,                 # 11
                    base,                      # 12
                    iva,                       # 13
                    importe,                   # 14
                    tasas                      # 15
                ]
                
                subprocess.Popen(comando)
                messagebox.showinfo("Llamada Exitosa", "Se ha lanzado el programa 'extractor_generator_gui.py'.")

            except Exception as e:
                messagebox.showerror("Error de Ejecución", f"No se pudo ejecutar 'extractor_generator_gui.py'.\nError: {e}")


# --- PUNTO DE ENTRADA ---
if __name__ == "__main__":
    if len(sys.argv) > 1:
        print("Ejecutando en modo CLI (Command Line Interface)...")
        
    root = tk.Tk()
    app = InvoiceApp(root)
    root.mainloop()