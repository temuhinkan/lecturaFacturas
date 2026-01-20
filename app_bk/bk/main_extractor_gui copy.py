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
from PIL import Image
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
except AttributeError:
    Image = None
    pytesseract = None


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
    """Conecta a la BBDD (o la crea) y asegura que la tabla existe y tiene 'log_data'."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Intenta crear la tabla si no existe (sin la nueva columna, si la migración no se ha hecho)
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
            procesado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 🚨 MIGRACIÓN: Verifica si la columna 'log_data' existe y la añade si no (para bases de datos existentes)
    try:
        cursor.execute("SELECT log_data FROM processed_invoices LIMIT 1")
    except sqlite3.OperationalError:
        print("Migrating DB: Adding 'log_data' column.")
        cursor.execute("ALTER TABLE processed_invoices ADD COLUMN log_data TEXT")
    
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

def insert_invoice_data(data: Dict[str, Any], original_path: str):
    """Inserta o actualiza datos de la factura en la BBDD."""
    
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
    
    # 🚨 NUEVA LÍNEA: Obtener el log/debug
    log_data_val = data.get('DebugLines') or ''

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
        log_data_val # 🚨 NUEVO: Valor del log
    )
    
    # 🚨 QUERY ACTUALIZADA: Se añade 'log_data' a la lista de columnas
    cursor.execute("""
        INSERT OR REPLACE INTO processed_invoices 
        (path, file_name, tipo, fecha, numero_factura, emisor, cliente, cif, modelo, matricula, base, iva, importe, tasas, log_data)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, invoice_data)
    
    conn.commit()
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
    """🚨 NUEVA FUNCIÓN: Elimina la tabla 'processed_invoices' (borrando todos los datos)."""
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

# --- Mapeo de Clases de Extracción (¡CORREGIDO!) ---
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
            numeric_val = float(str(value).replace(',', '.').replace('€', '').strip()) 
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
            'DebugLines': debug_output # 🚨 AHORA SIEMPRE CONTIENE EL LOG COMPLETO DE LA EXTRACCIÓN
        }
        if current_row['IVA'] in ['No encontrado', '']:
            current_row['IVA'] = '21%'  
            
        # Guardar en BBDD (usa INSERT OR REPLACE)
        insert_invoice_data(current_row, final_path_on_disk)

        all_extracted_rows_with_debug.append(current_row)

    # El CSV sigue generándose con las facturas PROCESADAS en esta ejecución.
    unique_rows_csv = []
    seen_combinations = set()

    for row_with_debug in all_extracted_rows_with_debug:
        row_csv = row_with_debug.copy()
        row_csv.pop('DebugLines', None) 
        row_csv.pop('__OriginalPath__', None)

        row_tuple = tuple(sorted((k, v) for k, v in row_csv.items() if k != 'Archivo'))
        if row_tuple not in seen_combinations:
            seen_combinations.add(row_tuple)
            unique_rows_csv.append(row_csv)

    output_dir = os.path.dirname(ruta_input) if os.path.isfile(ruta_input) else ruta_input
    csv_output_path = os.path.join(output_dir, 'facturas_resultado.csv')
    
    try:
        with open(csv_output_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
            fieldnames = ['Archivo', 'Tipo', 'Fecha', 'Número de Factura', 'Emisor', 'Cliente', 'CIF', 'Modelo', 'Matricula', "Base", "IVA", 'Importe', 'Tasas']
            # Usar ';' como delimitador para compatibilidad con Excel
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=';')
            writer.writeheader()
            writer.writerows(unique_rows_csv)

    except Exception as e:
        messagebox.showerror("Error al escribir CSV", f"No se pudo escribir el archivo CSV: {e}")
        return [], ""
    
    return all_extracted_rows_with_debug, csv_output_path


# --- Interfaz Gráfica (Tkinter) (InvoiceApp) ---
class InvoiceApp:
    def __init__(self, master):
        self.master = master
        master.title("Extractor de Facturas v2.4 (Log en BBDD y Borrado Total)")
        
        self.ruta_input_var = tk.StringVar(value="")
        self.debug_mode_var = tk.BooleanVar(value=False)
        self.debug_mode_var.trace_add("write", self._on_debug_mode_change)
        
        self.force_reprocess_var = tk.BooleanVar(value=False)

        self.tree: Optional[ttk.Treeview] = None
        self.debug_text_area: Optional[ScrolledText] = None
        self.button_call_generator: Optional[tk.Button] = None 
        self.button_launch_file: Optional[tk.Button] = None    
        
        self.columns = ['Archivo', 'Tipo', 'Fecha', 'Número de Factura', 'Emisor', 'Cliente', 'CIF', 'Modelo', 'Matricula', 'Base', 'IVA', 'Importe', 'Tasas'] 

        self.results_data: List[Dict[str, Any]] = [] 
        self.db_data: List[Dict[str, Any]] = []      

        setup_database() 
        self.load_all_data_from_db() 
        
        self.create_widgets()
        
    def _on_debug_mode_change(self, *args):
        if self.tree and self.button_call_generator and self.tree.get_children():
            if self.debug_mode_var.get() == False:
                self.button_call_generator['state'] = tk.DISABLED
            else:
                self.button_call_generator['state'] = tk.NORMAL

    # --------------------------------------------------
    # FUNCIONES DE GUI PARA BBDD Y EDICIÓN
    # --------------------------------------------------
    
    def format_numeric_value(self, value: Any, is_currency: bool = True) -> str:
        """ (Función helper para formatear números) """
        if value is None:
            return 'No encontrado'
        try:
            numeric_val = float(str(value).replace(',', '.').replace('€', '').strip()) 
            formatted = f"{numeric_val:.2f}"
            if is_currency:
                return f"{formatted} €".replace('.', ',')
            return formatted.replace('.', ',')
        except ValueError:
            return str(value)

    def load_all_data_from_db(self):
        """Carga todos los datos de la BBDD y actualiza la vista."""
        conn = sqlite3.connect(DB_NAME)
        
        try:
            conn.row_factory = sqlite3.Row 
            cursor = conn.cursor()
            
            # Intenta seleccionar log_data, sino usa ''
            try:
                cursor.execute("SELECT *, log_data FROM processed_invoices ORDER BY procesado_en DESC")
            except sqlite3.OperationalError:
                 # Fallback si la migración no ha podido añadir la columna (DB antigua no modificada)
                cursor.execute("SELECT * FROM processed_invoices ORDER BY procesado_en DESC")
            
            self.db_data = []
            
            for row in cursor.fetchall():
                # NEW: Manejo de la columna log_data
                log_data_value = row['log_data'] if 'log_data' in row.keys() else "Cargado de BBDD. Log no guardado."
                
                formatted_row = {
                    'Archivo': row['file_name'],
                    '__OriginalPath__': row['path'],
                    'Tipo': row['tipo'] or 'N/A',
                    'Fecha': row['fecha'] or 'N/A',
                    'Número de Factura': row['numero_factura'] or 'N/A',
                    'Emisor': row['emisor'] or 'N/A',
                    'Cliente': row['cliente'] or 'N/A',
                    'CIF': row['cif'] or 'N/A',
                    'Modelo': row['modelo'] or 'N/A',
                    'Matricula': row['matricula'] or 'N/A',
                    "Base": self.format_numeric_value(row['base'], is_currency=False),
                    "IVA": self.format_numeric_value(row['iva'], is_currency=False),
                    'Importe': self.format_numeric_value(row['importe'], is_currency=True),
                    'Tasas': self.format_numeric_value(row['tasas'], is_currency=False),
                    'DebugLines': log_data_value # 🚨 AHORA EL LOG VIENE DE BBDD
                }
                self.db_data.append(formatted_row)
            
            self._update_treeview_with_data(self.db_data)
        finally:
            conn.close()
        
    def _update_treeview_with_data(self, data_list: List[Dict[str, Any]]):
        """Helper para actualizar la tabla con una lista de datos."""
        if not self.tree: return
        self.tree.delete(*self.tree.get_children()) # Borra todos los elementos existentes
        
        for i, row in enumerate(data_list):
            display_values = [row.get(col, 'N/A') for col in self.columns]
            self.tree.insert('', tk.END, iid=str(i), values=display_values) 

    def on_double_click_edit(self, event):
        """Permite editar el valor de una celda seleccionada y guarda el cambio en BBDD."""
        if not self.tree.selection():
            return

        region = self.tree.identify("region", event.x, event.y)
        if region != "heading":
            item_id = self.tree.focus()
            column_id = self.tree.identify_column(event.x)
            column_index = int(column_id.replace('#', '')) - 1
            column_name = self.columns[column_index]
            
            if column_name in ['Archivo']: # 'DebugLines' ya no está en las columnas visibles
                 return 
            
            current_value = self.tree.item(item_id, 'values')[column_index]

            entry_edit = tk.Entry(self.tree, width=self.tree.column(column_id, option="width"))
            entry_edit.insert(0, current_value)
            
            x, y, width, height = self.tree.bbox(item_id, column_id)
            entry_edit.place(x=x, y=y, w=width, h=height)
            entry_edit.focus()

            def on_edit_finished(event=None):
                new_value = entry_edit.get()
                entry_edit.destroy()
                
                # Usamos item_id (que es str(index))
                data_index = int(item_id) 
                if 0 <= data_index < len(self.db_data):
                    row_data = self.db_data[data_index]
                    original_path = row_data.get('__OriginalPath__')
                    
                    if new_value != current_value and original_path:
                        # 1. Actualizar el Treeview
                        current_values = list(self.tree.item(item_id, 'values'))
                        current_values[column_index] = new_value
                        self.tree.item(item_id, values=current_values)
                        
                        # 2. Actualizar el diccionario local (db_data)
                        row_data[column_name] = new_value
                        
                        # 3. Guardar el cambio en la BBDD
                        self._save_update_to_db(original_path, column_name, new_value)
                    
            entry_edit.bind('<Return>', on_edit_finished)
            entry_edit.bind('<FocusOut>', on_edit_finished)

    def _save_update_to_db(self, path: str, column_name: str, new_value: Any):
        """Guarda un solo cambio en la BBDD."""
        
        db_column_map = {
            'Archivo': 'file_name', 'Tipo': 'tipo', 'Fecha': 'fecha', 'Número de Factura': 'numero_factura', 
            'Emisor': 'emisor', 'Cliente': 'cliente', 'CIF': 'cif', 'Modelo': 'modelo', 
            'Matricula': 'matricula', 'Base': 'base', 'IVA': 'iva', 'Importe': 'importe', 'Tasas': 'tasas'
            # log_data no se permite editar
        }
        db_column = db_column_map.get(column_name)
        
        if not db_column:
            return

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        if db_column in ['base', 'iva', 'importe', 'tasas']:
            new_value = _clean_numeric_value(new_value)

        try:
            query = f"UPDATE processed_invoices SET {db_column} = ? WHERE path = ?"
            cursor.execute(query, (new_value, path))
            conn.commit()
            print(f"✅ Actualización BBDD: '{db_column}' de {os.path.basename(path)} a {new_value}")
        except Exception as e:
            messagebox.showerror("Error de BBDD", f"Fallo al actualizar {column_name} en la BBDD: {e}")
        finally:
            conn.close()

    def export_to_csv_excel(self):
        """Exporta todos los datos cargados en self.db_data a un archivo CSV."""
        
        if not self.db_data:
            messagebox.showwarning("Advertencia", "No hay datos en la tabla para exportar.")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("Archivos CSV", "*.csv")],
            initialfile="facturas_exportadas.csv",
            title="Guardar resultados como CSV (compatible con Excel)"
        )

        if not file_path:
            return

        try:
            fieldnames = [col for col in self.columns]
            
            data_to_write = []
            for row in self.db_data:
                clean_row = {k: row.get(k, 'N/A') for k in fieldnames}
                
                for k, v in clean_row.items():
                    if isinstance(v, str):
                        clean_row[k] = v.replace('€', '').strip().replace(',', '.') 

                data_to_write.append(clean_row)

            with open(file_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
                # Usar ';' como delimitador y encoding 'utf-8-sig' ayuda a que Excel lo abra correctamente
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=';')
                writer.writeheader()
                writer.writerows(data_to_write)

            messagebox.showinfo("Éxito", f"Datos exportados correctamente a:\n{file_path}")

        except Exception as e:
            messagebox.showerror("Error de Exportación", f"Fallo al exportar el archivo CSV: {e}")
            
    def delete_selected_invoices(self):
        """Elimina las facturas seleccionadas de la GUI y de la BBDD."""
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("Advertencia", "Seleccione una o más facturas para eliminar.")
            return

        confirmation = messagebox.askyesno(
            "Confirmar Eliminación", 
            f"¿Está seguro que desea eliminar {len(selected_items)} factura(s) de la BBDD?\nEsta acción es irreversible."
        )

        if not confirmation:
            return

        paths_to_delete: List[str] = []

        # Recorrer las selecciones para obtener las rutas
        for item_id in selected_items:
            # item_id es str(index)
            data_index = int(item_id)
            if 0 <= data_index < len(self.db_data):
                path = self.db_data[data_index].get('__OriginalPath__')
                if path:
                    paths_to_delete.append(path)
        
        if paths_to_delete:
            deleted_count = delete_invoice_data(paths_to_delete)
            messagebox.showinfo("Éxito", f"Se eliminaron {deleted_count} registro(s) de la BBDD.")
            
            # Recargar los datos para refrescar la GUI y self.db_data
            self.load_all_data_from_db()

        else:
            messagebox.showerror("Error", "No se pudo recuperar la ruta de la factura seleccionada para eliminarla.")

    def delete_entire_database_action(self):
        """🚨 NUEVO MÉTODO: Maneja la confirmación y el borrado total de la BBDD."""
        confirmation = messagebox.askyesno(
            "⚠️ ¡ADVERTENCIA CRÍTICA!",
            "¿Está ABSOLUTAMENTE seguro de que desea **BORRAR TODOS LOS DATOS** de la base de datos?\n\nEsta acción eliminará de forma PERMANENTE todos los registros de facturas procesadas y no se puede deshacer."
        )
        
        if not confirmation:
            return

        if delete_entire_database_schema():
            # 1. Volvemos a inicializar la BBDD (crea la tabla vacía con la estructura correcta)
            setup_database()
            # 2. Recargamos la interfaz con la tabla vacía
            self.load_all_data_from_db()
            messagebox.showinfo("Éxito", "La base de datos de facturas procesadas ha sido borrada completamente.")
        else:
            messagebox.showerror("Error", "Ocurrió un error al intentar borrar la base de datos.")


    # --------------------------------------------------
    # WIDGETS Y EVENTOS DE LA GUI
    # --------------------------------------------------

    def create_widgets(self):
        frame_ruta = tk.Frame(self.master, padx=10, pady=10); frame_ruta.pack(fill='x')
        tk.Label(frame_ruta, text="Ruta a Fichero o Directorio:").pack(side='left', padx=(0, 10))
        self.entry_ruta = tk.Entry(frame_ruta, textvariable=self.ruta_input_var, width=50); self.entry_ruta.pack(side='left', fill='x', expand=True, padx=(0, 10))
        tk.Button(frame_ruta, text="Seleccionar...", command=self.select_path).pack(side='left')

        frame_controls = tk.Frame(self.master, padx=10, pady=5); frame_controls.pack(fill='x')
        
        tk.Checkbutton(frame_controls, text="Modo Debug (capturar líneas)", variable=self.debug_mode_var).pack(side='left', anchor='w')
        
        # NUEVO CHECKBUTTON: Forzar reprocesamiento
        tk.Checkbutton(frame_controls, text="Forzar Reprocesamiento (Ignorar BBDD) 🔄", variable=self.force_reprocess_var).pack(side='left', anchor='w', padx=(15, 0))
        
        tk.Button(frame_controls, text="INICIAR EXTRACCIÓN", command=self.execute_extraction, bg="green", fg="white", font=('Arial', 12, 'bold')).pack(side='right')

        # 🚨 NUEVO FRAME para Botones de Acción de BBDD
        frame_db_actions = tk.Frame(self.master, padx=10, pady=5); frame_db_actions.pack(fill='x')
        
        tk.Button(frame_db_actions, text="📊 Exportar a CSV (Compatible Excel)", command=self.export_to_csv_excel, bg='#4CAF50', fg='white').pack(side='left', padx=(0, 5))
        
        # 🚨 NUEVO BOTÓN: Borrado total de la BBDD
        tk.Button(frame_db_actions, text="💥 BORRAR TODA LA BBDD", command=self.delete_entire_database_action, bg='#FF0000', fg='white', font=('Arial', 10, 'bold')).pack(side='right', padx=(5, 0))
        
        tk.Button(frame_db_actions, text="🗑️ Eliminar Seleccionado(s) de BBDD", command=self.delete_selected_invoices, bg='#FF5722', fg='white').pack(side='right')


        results_frame = tk.LabelFrame(self.master, text="Resultados de la Extracción (Datos cargados de BBDD)", padx=5, pady=5); results_frame.pack(fill='both', expand=True, padx=10, pady=(10, 5))
        self.tree = ttk.Treeview(results_frame, columns=self.columns, show='headings', selectmode='extended') 
        for col in self.columns:
            self.tree.heading(col, text=col); 
            width = 150 if col == 'Archivo' else (60 if col in ['Tipo', 'IVA', 'Tasas'] else (80 if col in ['Base', 'Importe', 'Fecha'] else 100))
            self.tree.column(col, anchor='w', width=width)
        
        vsb = ttk.Scrollbar(results_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side='right', fill='y')
        self.tree.pack(side='top', fill='both', expand=True)
        self.tree.bind('<<TreeviewSelect>>', self.show_debug_info)
        self.tree.bind('<Double-1>', self.on_double_click_edit) 

        debug_frame = tk.LabelFrame(self.master, text="Detalle de Líneas Procesadas y Acciones (Log Guardado)", padx=5, pady=5); debug_frame.pack(fill='x', padx=10, pady=(5, 10))
        self.debug_text_area = ScrolledText(debug_frame, height=8, wrap=tk.WORD, state=tk.DISABLED, font=('Consolas', 9)); self.debug_text_area.pack(side='top', fill='both', expand=True)
        
        action_frame = tk.Frame(debug_frame)
        action_frame.pack(side='bottom', fill='x', pady=(5, 0))

        self.button_launch_file = tk.Button(action_frame, text="➡️ Abrir Archivo Asociado (PDF/Imagen)", command=self.launch_associated_file, bg='#ADD8E6', state=tk.DISABLED)
        self.button_launch_file.pack(side='left', fill='x', expand=True, padx=(0, 5))
        
        self.button_call_generator = tk.Button(action_frame, text="Llamar al Generador de Extractores", command=self.call_external_program_template, bg='#F08080', state=tk.DISABLED)
        self.button_call_generator.pack(side='right', fill='x', expand=True, padx=(5, 0))


    def select_path(self):
        dir_path = filedialog.askdirectory(title="Seleccionar Directorio con Facturas")
        if dir_path:
            self.ruta_input_var.set(dir_path)
            return
        
        file_path = filedialog.askopenfilename(
            title="Seleccionar Archivo de Factura (PDF/Imagen)",
            filetypes=[
                ("Archivos Soportados", "*.pdf *.jpg *.jpeg *.png *.tiff *.tif"),
                ("Archivos PDF", "*.pdf"),
                ("Archivos de Imagen", "*.jpg *.jpeg *.png *.tiff *.tif"),
                ("Todos los Archivos", "*.*")
            ]
        )
        if file_path:
            self.ruta_input_var.set(file_path)

    def _update_action_buttons_state(self):
        has_results = bool(self.db_data)
        is_debug_on = self.debug_mode_var.get()
        
        self.button_launch_file['state'] = tk.NORMAL if has_results and self.tree.selection() else tk.DISABLED
        
        if self.tree.selection() and is_debug_on:
            self.button_call_generator['state'] = tk.NORMAL
        else:
            self.button_call_generator['state'] = tk.DISABLED

    def execute_extraction(self):
        ruta = self.ruta_input_var.get()
        debug = self.debug_mode_var.get()
        force_reprocess = self.force_reprocess_var.get() 
        
        if not ruta:
            messagebox.showerror("Error", "Debe seleccionar un archivo o directorio.")
            return

        self.results_data = []
        
        if self.debug_text_area:
             self.debug_text_area.config(state=tk.NORMAL)
             self.debug_text_area.delete('1.0', tk.END)
             self.debug_text_area.insert(tk.END, "Ejecutando la extracción...")
             self.debug_text_area.config(state=tk.DISABLED)
        
        self.master.config(cursor="wait")
        self.entry_ruta.config(state='disabled')
        
        try:
            # 1. Ejecuta la extracción
            all_extracted_rows_with_debug, csv_output_path = run_extraction(ruta, debug, force_reprocess)
            self.results_data = all_extracted_rows_with_debug 
            
            # 2. Vuelve a cargar TODOS los datos 
            self.load_all_data_from_db()
            
            if all_extracted_rows_with_debug:
                 messagebox.showinfo("¡Éxito!", f"Proceso completado. Resultados visibles y escritos en: {csv_output_path}")
            else:
                 messagebox.showwarning("Advertencia", "Extracción finalizada. No se procesaron archivos nuevos o no se encontraron datos válidos.")

        except Exception as e:
            messagebox.showerror("Error de Ejecución", f"Ha ocurrido un error durante la extracción: {e}\n{traceback.format_exc()}")
            
        finally:
            self.master.config(cursor="")
            self.entry_ruta.config(state='normal')
            self._update_action_buttons_state() 
            if self.debug_text_area:
                 self.debug_text_area.config(state=tk.NORMAL)
                 self.debug_text_area.delete('1.0', tk.END)
                 self.debug_text_area.insert(tk.END, "Extracción finalizada. Seleccione una fila para ver el detalle de las líneas.")
                 self.debug_text_area.config(state=tk.DISABLED)

    def show_debug_info(self, event):
        selected_items = self.tree.selection()
        
        self.debug_text_area.config(state=tk.NORMAL)
        self.debug_text_area.delete('1.0', tk.END)
        
        if not selected_items:
            self.debug_text_area.insert(tk.END, "Seleccione una fila para ver el detalle de las líneas procesadas.")
        else:
            item_id = selected_items[0] 
            data_index = int(item_id)
            
            if 0 <= data_index < len(self.db_data):
                row = self.db_data[data_index] 
                
                # Usamos el log directamente de self.db_data (que contiene el log guardado o el recién extraído)
                debug_lines_source = row.get('DebugLines', 'No hay información de debug disponible.')

                summary = (
                    f"--- RESUMEN DE EXTRACCIÓN ---\n"
                    f"Archivo: {row.get('Archivo')}\n"
                    f"Nº Factura: {row.get('Número de Factura')}\n"
                    f"Emisor: {row.get('Emisor')}\n"
                    f"Importe: {row.get('Importe')}\n"
                    f"---------------------------\n\n"
                )
                
                self.debug_text_area.insert(tk.END, summary)
                self.debug_text_area.insert(tk.END, debug_lines_source)
                

        self.debug_text_area.config(state=tk.DISABLED)
        self._update_action_buttons_state()

    def launch_associated_file(self):
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("Advertencia", "Seleccione primero una factura en la tabla de resultados.")
            return

        item_id = selected_items[0] 
        data_index = int(item_id)
        
        if 0 <= data_index < len(self.db_data):
            row = self.db_data[data_index] 
            file_path = row.get('__OriginalPath__')
            
            if not file_path or not os.path.exists(file_path):
                messagebox.showerror("Error", f"Ruta de archivo no encontrada o archivo inexistente: {file_path}")
                return

            try:
                if sys.platform == "win32":
                    os.startfile(file_path)
                elif sys.platform == "darwin":
                    subprocess.run(['open', file_path], check=True)
                else:
                    subprocess.run(['xdg-open', file_path], check=True)

            except Exception as e:
                messagebox.showerror("Error al abrir", f"No se pudo abrir el archivo:\n{file_path}\nError: {e}")
        else:
            messagebox.showerror("Error", "Error interno al recuperar la información del archivo.")

    
    def call_external_program_template(self):
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("Advertencia", "Seleccione primero una factura en la tabla de resultados.")
            return
            
        item_id = selected_items[0] 
        data_index = int(item_id)
        
        if 0 <= data_index < len(self.db_data):
            row = self.db_data[data_index]
            
            ruta_archivo = row.get('__OriginalPath__', None)
            
            if not ruta_archivo or not os.path.exists(ruta_archivo):
                messagebox.showerror("Error", f"Ruta de archivo no válida o inexistente: {ruta_archivo}")
                return
            
            debug_row = row 
            
            tipo = str(debug_row.get('Tipo', ''))
            fecha = str(debug_row.get('Fecha', ''))
            num_factura = str(debug_row.get('Número de Factura', ''))
            emisor = str(debug_row.get('Emisor', ''))
            cliente = str(debug_row.get('Cliente', ''))
            cif = str(debug_row.get('CIF', '')) 
            modelo = str(debug_row.get('Modelo', ''))
            matricula = str(debug_row.get('Matricula', ''))
            base = str(debug_row.get('Base', ''))
            iva = str(debug_row.get('IVA', ''))
            importe = str(debug_row.get('Importe', ''))
            tasas = str(debug_row.get('Tasas', ''))
            # 🚨 Ahora el log viene directamente de la BBDD (o del resultado de la ejecución)
            debug_lines = str(debug_row.get('DebugLines', '')) 
            nombre_base_archivo = os.path.splitext(os.path.basename(ruta_archivo))[0]
            
            
            confirmar = messagebox.askyesno(
                "Confirmar llamada al Generador",
                f"Se va a lanzar el Generador de Extractores con el archivo:\n\n{os.path.basename(ruta_archivo)}\n\n¿Desea continuar y precargar los datos?"
            )
            
            if not confirmar:
                return 
            
            try:
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