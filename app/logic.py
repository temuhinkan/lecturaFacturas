import os
import sys
import importlib
import importlib.util
import tempfile
import traceback
from typing import Tuple, List, Optional, Any, Dict
import re # Necesario para la lógica de mapeo

# Importaciones para extracción de PDF y OCR
import fitz # PyMuPDF
try:
    from PIL import Image
    import pytesseract
except ImportError:
    Image = None
    pytesseract = None
    Image.MAX_IMAGE_PIXELS = 2147483647                

# Importar configuración y dependencias
from config import EXTRACTION_MAPPING, TESSERACT_CMD_PATH, ERROR_DATA, DEFAULT_VAT_RATE_STR
from split_pdf import split_pdf_into_single_page_files # Función de utilidad

# --- Configuración de OCR (Tesseract) ---
if sys.platform == "win32" and pytesseract and TESSERACT_CMD_PATH:
    try:
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD_PATH
    except Exception as e:
        print(f"Error al configurar Tesseract: {e}")

# --- Dependencia: BaseInvoiceExtractor (CLASE FUNCIONAL) ---
# Importamos directamente, ya que BaseInvoiceExtractor.py ahora tiene la lógica de mapeo y trazas.
from extractors.base_invoice_extractor import BaseInvoiceExtractor
# -------------------------------------------------------------


# ----------------------------------------------------------------------
# FUNCIONES DE EXTRACCIÓN Y LECTURA DE DOCUMENTOS
# ----------------------------------------------------------------------

def _get_pdf_lines(pdf_path: str) -> List[str]:
    """
    Lee un PDF (o imagen) usando fitz. Si no encuentra texto, intenta OCR (Tesseract).
    Retorna una lista de líneas de texto limpias. (Lógica unificada de Lectura/OCR)
    """
    lines: List[str] = []
    file_extension = os.path.splitext(pdf_path)[1].lower()
    print("DEBUG FLOW: _get_pdf_lines: Iniciando lectura del documento.")
    # --- 1. Leer texto directo (PDF con capa de texto) ---
    if file_extension == ".pdf":
        print("DEBUG FLOW: Intentando lectura directa de PDF.")
        try:
            doc = fitz.open(pdf_path)
            texto = ''
            for page in doc:
                texto += page.get_text() or ''
            doc.close()
            lines = [line for line in texto.splitlines() if line.strip()]
            if lines:
                print(f"DEBUG FLOW: Lectura directa exitosa. {len(lines)} líneas encontradas.")
                return lines
        except Exception:
            print("DEBUG FLOW: Falló la lectura directa de PDF, intentando OCR.")
            pass # Continúa al OCR

    # --- 2. OCR (Rasterización de PDF o Lectura de Imagen) ---
    if Image and pytesseract:
        print("DEBUG FLOW: Intentando OCR (Tesseract).")
        try:
            temp_img_to_delete: Optional[str] = None
            if file_extension in ['.jpg', '.jpeg', '.png', '.tiff', '.tif']:
                # OCR directo sobre la imagen
                ocr_text = pytesseract.image_to_string(Image.open(pdf_path), lang='spa')
                lines = [line for line in ocr_text.splitlines() if line.strip()]
                return lines

            elif file_extension == ".pdf":
                # OCR sobre la primera página rasterizada del PDF
                doc = fitz.open(pdf_path)
                if len(doc) > 0:
                    page = doc.load_page(0)
                    zoom = 300 / 72
                    mat = fitz.Matrix(zoom, zoom)
                    print(f"DEBUG OCR: Abierto PDF. Zoom: {zoom:.2f}x (300 DPI)")
                    pix = page.get_pixmap(matrix=mat, alpha=False)
                    doc.close()

                    temp_img_name = f"ocr_temp_{os.path.splitext(os.path.basename(pdf_path))[0]}.png"
                    temp_img_to_delete = os.path.join(tempfile.gettempdir(), temp_img_name)
                    pix.save(temp_img_to_delete)
                    img_size = os.path.getsize(temp_img_to_delete) / (1024 * 1024) # en MB
                    print(f"DEBUG OCR: Imagen temporal guardada ({img_size:.2f} MB).")
                    
                    try:
                        ocr_text = pytesseract.image_to_string(Image.open(temp_img_to_delete), lang='spa')
                    except Exception as e:
                        print(f"❌ ERROR CRÍTICO OCR: Falló pytesseract.image_to_string. Error: {e}")
                        ocr_text = "" 
                        
                    lines = [line for line in ocr_text.splitlines() if line.strip()]
                    print(f"DEBUG OCR: {len(lines)} líneas detectadas por OCR.")
                    
                    if temp_img_to_delete and os.path.exists(temp_img_to_delete):
                        os.remove(temp_img_to_delete)

                    return lines
        except Exception:
            print("DEBUG FLOW: Falló la ejecución de OCR.")
            pass

    print("DEBUG FLOW: _get_pdf_lines: No se pudo extraer texto. Retornando lista vacía.")
    return lines


def _load_extractor_class_dynamic(extractor_path_str: str):
    """Carga dinámicamente una clase de extractor dado su path completo (módulo.Clase)."""
    print(f"DEBUG FLOW: Intentando carga dinámica de '{extractor_path_str}'...")
    try:
        parts = extractor_path_str.split('.')
        module_name = ".".join(parts[:-1])
        class_name = parts[-1]

        module_spec = importlib.util.find_spec(module_name)
        if not module_spec or not module_spec.origin:
            raise ImportError(f"No se encontró el archivo del módulo: {module_name}")

        module = importlib.util.module_from_spec(module_spec)

        # Aseguramos que la clase base esté disponible en el namespace del módulo cargado
        module.__dict__['BaseInvoiceExtractor'] = BaseInvoiceExtractor

        sys.modules[module_name] = module
        module_spec.loader.exec_module(module)

        print(f"DEBUG FLOW: Carga dinámica EXITOSA para '{class_name}'.")
        return getattr(module, class_name)

    except Exception as e:
        print(f"DEBUG FLOW: Carga dinámica FALLIDA para '{extractor_path_str}'. Error: {e}")
        raise RuntimeError(f"Fallo al cargar la clase {extractor_path_str}. Error: {e}")


def find_extractor_for_file(file_path: str) -> Optional[str]:
    """Identifica el extractor adecuado por nombre de archivo o por CIF extraído."""
    nombre_archivo = os.path.basename(file_path).lower()

    # 1. Búsqueda por palabra clave en el nombre del archivo
    print("DEBUG FLOW: find_extractor_for_file: Iniciando búsqueda por palabra clave en nombre.")
    for keyword, class_path in EXTRACTION_MAPPING.items():
        if keyword in nombre_archivo:
            print(f"DEBUG FLOW: find_extractor_for_file: Coincidencia por palabra clave '{keyword}'. Extractor: {class_path}")
            return class_path

    # 2. Búsqueda por CIF usando el extractor base
    print("DEBUG FLOW: find_extractor_for_file: No se encontró por nombre. Intentando búsqueda por CIF.")
    try:
        # Se asume que lines ya fue cargado por _get_pdf_lines, pero lo volvemos a llamar por si acaso.
        lines = _get_pdf_lines(file_path)
        if not lines: return None

        # Usamos BaseInvoiceExtractor para una extracción preliminar (busca el CIF)
        temp_extractor = BaseInvoiceExtractor(lines, file_path)
        
        # Llama a extract_all para obtener la tupla completa
        extracted_data = temp_extractor.extract_all()
        
        # El índice 4 es para CIF_EMISOR en la tupla
        cif_extraido_base = str(extracted_data[4]).replace('-', '').replace('.', '').strip().upper() if len(extracted_data) > 4 and extracted_data[4] else None

        if cif_extraido_base:
            print(f"DEBUG FLOW: find_extractor_for_file: CIF Base extraído: {cif_extraido_base}")
            for keyword, class_path in EXTRACTION_MAPPING.items():
                try:
                    module_path, class_name = class_path.rsplit('.', 1)
                    module = importlib.import_module(module_path)
                    ExtractorClass = getattr(module, class_name)
                    if hasattr(ExtractorClass, 'EMISOR_CIF') and ExtractorClass.EMISOR_CIF.upper() == cif_extraido_base:
                        print(f"DEBUG FLOW: find_extractor_for_file: Coincidencia por CIF para clase '{class_path}'.")
                        return class_path
                except Exception:
                    continue
        else:
            print("DEBUG FLOW: find_extractor_for_file: No se pudo extraer CIF con el extractor base.")

    except Exception as e:
        print(f"DEBUG FLOW: find_extractor_for_file: Falló la búsqueda por CIF. Error: {e}")
        pass

    print("DEBUG FLOW: find_extractor_for_file: No se encontró extractor específico. Usando fallback.")
    return None

def _pad_data(data: Tuple) -> Tuple:
    """Asegura que la tupla de datos tenga el número correcto de campos (13)."""
    REQUIRED_FIELDS = 13
    if len(data) >= REQUIRED_FIELDS:
        return data[:REQUIRED_FIELDS]
    return data + (None,) * (REQUIRED_FIELDS - len(data))


def extraer_datos(pdf_path: str, debug_mode: bool = False) -> Tuple[Any, ...]:
    """
    Función principal de extracción de datos. Retorna una tupla de 13 campos + log (14 elementos).
    """
    debug_output: str = ""
    extracted_data_raw: Tuple = tuple()
    print("DEBUG FLOW: Iniciando extraer_datos.")

    try:
        lines = _get_pdf_lines(pdf_path)

        if not lines:
            debug_output += "Error: No se pudo leer texto del documento (PDF o Imagen)."
            return (*_pad_data(extracted_data_raw), debug_output)

        print(f"DEBUG FLOW: {len(lines)} líneas de texto leídas del documento.")

        if debug_mode:
            debug_output += f"🔍 DEBUG MODE ACTIVATED: Document read successfully.\n\n"
            for i, linea in enumerate(lines):
                debug_output += f"Line {i:02d}: {linea}\n"
            debug_output += "\n"

        # 1. Mapeo y Carga DINÁMICA del Extractor
        print("DEBUG FLOW: Buscando extractor específico...")
        full_class_path = find_extractor_for_file(pdf_path)
        doc_path_for_extractor = pdf_path

        ExtractorClass = None
        if full_class_path:
            print("DEBUG FLOW: Extractor específico encontrado. Intentando cargar la clase.")
            debug_output += f"➡️ Extractor encontrado en mapeo: {full_class_path}\n"
            try:
                ExtractorClass = _load_extractor_class_dynamic(full_class_path)
            except RuntimeError as e:
                debug_output += f"❌ ERROR en la carga dinámica del extractor: {e}\n"
                pass # Continúa al extractor genérico

        if ExtractorClass:
            print("DEBUG FLOW: Extractor específico cargado. Ejecutando extracción.")
            try:
                # 2. Extractor Específico
                extractor = ExtractorClass(lines, doc_path_for_extractor)
                if hasattr(extractor, 'extract_data') and callable(getattr(extractor, 'extract_data')):
                    data_dict = extractor.extract_data(lines)
                    # Mapeo de dict a tupla
                    extracted_data_raw = (
                        data_dict.get('tipo'), data_dict.get('fecha'), data_dict.get('num_factura'),
                        data_dict.get('emisor'), data_dict.get('cif_emisor'),data_dict.get('cliente'), data_dict.get('cif'),
                        data_dict.get('modelo'), data_dict.get('matricula'), data_dict.get('importe'),
                        data_dict.get('base'), data_dict.get('iva'), data_dict.get('tasas')
                    )
                else:
                    extracted_data_raw = extractor.extract_all()

                debug_output += f"✅ Extracción exitosa con {full_class_path}.\n"
                print(f"DEBUG FLOW: Extracción con extractor específico completada.")
                return (*_pad_data(extracted_data_raw), debug_output)

            except Exception as e:
                print(f"DEBUG FLOW: Falló la ejecución del extractor específico. Error: {e}")
                debug_output += f"❌ ERROR: Falló la ejecución del extractor para '{full_class_path}'. Error: {e}\n"
                # Continúa al extractor genérico

        # 3. Extractor Genérico (Fallback)
        print("DEBUG FLOW: Iniciando Extractor Genérico (Fallback).")
        debug_output += "➡️ No specific invoice type detected or specific extractor failed. Using generic extraction function (BaseInvoiceExtractor).\n"
        generic_extractor = BaseInvoiceExtractor(lines, doc_path_for_extractor)
        extracted_data_raw = generic_extractor.extract_all()
        debug_output += "✅ Extracción exitosa con Extractor Genérico.\n"
        print("DEBUG FLOW: Extracción con extractor genérico completada.")
        return (*_pad_data(extracted_data_raw), debug_output)

    except Exception as e:
        traceback_str = traceback.format_exc()
        debug_output += f"❌ FATAL ERROR durante la extracción: {e}\n{traceback_str}"
        print(f"DEBUG FLOW: ERROR FATAL en extraer_datos. {e}")
        return (*ERROR_DATA[:-1], debug_output)