import os
import sys
import importlib
import importlib.util
import tempfile
import traceback
from typing import Tuple, List, Optional, Any, Dict

# Importaciones para extracción de PDF y OCR
import fitz # PyMuPDF
try:
    from PIL import Image
    import pytesseract
except ImportError:
    Image = None
    pytesseract = None

# Importar configuración y dependencias
from config import EXTRACTION_MAPPING, TESSERACT_CMD_PATH, ERROR_DATA, DEFAULT_VAT_RATE_STR
from split_pdf import split_pdf_into_single_page_files # Función de utilidad

# --- Configuración de OCR (Tesseract) ---
if sys.platform == "win32" and pytesseract and TESSERACT_CMD_PATH:
    try:
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD_PATH
    except Exception as e:
        print(f"Error al configurar Tesseract: {e}")

# --- Dependencia: BaseInvoiceExtractor (MOCKUP de seguridad) ---
try:
    from extractors.base_invoice_extractor import BaseInvoiceExtractor
except ImportError:
    # MOCKUP si la clase real no existe
    class BaseInvoiceExtractor:
        def __init__(self, lines, pdf_path=None):
            self.lines = lines
            self.pdf_path = pdf_path
            self.cif = 'B00000000'
        def extract_all(self) -> Tuple[Any, ...]:
            return ("Tipo_BASE", "Fecha_BASE", "NºFactura_BASE", "Emisor_BASE", "Cliente_BASE", "CIF_BASE", "Modelo_BASE", "Matricula_BASE", 100.0, 82.64, 17.36, 0.0)
        def is_valid(self): return True
        def extract_data(self, lines: List[str]) -> Dict[str, Any]:
            return {'tipo': 'Tipo_STUB', 'importe': 99.99}
    print("ADVERTENCIA: Usando BaseInvoiceExtractor stub.")


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

    # --- 1. Leer texto directo (PDF con capa de texto) ---
    if file_extension == ".pdf":
        try:
            doc = fitz.open(pdf_path)
            texto = ''
            for page in doc:
                texto += page.get_text() or ''
            doc.close()
            lines = [line for line in texto.splitlines() if line.strip()]
            if lines:
                return lines
        except Exception:
            pass # Continúa al OCR

    # --- 2. OCR (Rasterización de PDF o Lectura de Imagen) ---
    if Image and pytesseract:
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
                    pix = page.get_pixmap(matrix=mat, alpha=False)
                    doc.close()

                    temp_img_name = f"ocr_temp_{os.path.splitext(os.path.basename(pdf_path))[0]}.png"
                    temp_img_to_delete = os.path.join(tempfile.gettempdir(), temp_img_name)
                    pix.save(temp_img_to_delete)

                    ocr_text = pytesseract.image_to_string(Image.open(temp_img_to_delete), lang='spa')
                    lines = [line for line in ocr_text.splitlines() if line.strip()]

                    if temp_img_to_delete and os.path.exists(temp_img_to_delete):
                        os.remove(temp_img_to_delete)

                    return lines
        except Exception:
            pass

    return lines


def _load_extractor_class_dynamic(extractor_path_str: str):
    """Carga dinámicamente una clase de extractor dado su path completo (módulo.Clase)."""
    try:
        parts = extractor_path_str.split('.')
        module_name = ".".join(parts[:-1])
        class_name = parts[-1]

        module_spec = importlib.util.find_spec(module_name)
        if not module_spec or not module_spec.origin:
            raise ImportError(f"No se encontró el archivo del módulo: {module_name}")

        module = importlib.util.module_from_spec(module_spec)

        global BaseInvoiceExtractor
        if BaseInvoiceExtractor is None:
             raise RuntimeError("BaseInvoiceExtractor no está definida.")
        module.__dict__['BaseInvoiceExtractor'] = BaseInvoiceExtractor

        sys.modules[module_name] = module
        module_spec.loader.exec_module(module)

        return getattr(module, class_name)

    except Exception as e:
        raise RuntimeError(f"Fallo al cargar la clase {extractor_path_str}. Error: {e}")


def find_extractor_for_file(file_path: str) -> Optional[str]:
    """Identifica el extractor adecuado por nombre de archivo o por CIF extraído."""
    nombre_archivo = os.path.basename(file_path).lower()

    # 1. Búsqueda por palabra clave en el nombre del archivo
    for keyword, class_path in EXTRACTION_MAPPING.items():
        if keyword in nombre_archivo:
            return class_path

    # 2. Búsqueda por CIF usando el extractor base
    try:
        lines = _get_pdf_lines(file_path)
        if not lines: return None

        temp_extractor = BaseInvoiceExtractor(lines, file_path)
        extracted_data = temp_extractor.extract_all()
        cif_extraido_base = str(extracted_data[5]).replace('-', '').replace('.', '').strip().upper() if len(extracted_data) > 5 and extracted_data[5] else None

        if cif_extraido_base:
            for keyword, class_path in EXTRACTION_MAPPING.items():
                try:
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

def _pad_data(data: Tuple) -> Tuple:
    """Asegura que la tupla de datos tenga el número correcto de campos (12)."""
    REQUIRED_FIELDS = 12
    if len(data) >= REQUIRED_FIELDS:
        return data[:REQUIRED_FIELDS]
    return data + (None,) * (REQUIRED_FIELDS - len(data))


def extraer_datos(pdf_path: str, debug_mode: bool = False) -> Tuple[Any, ...]:
    """
    Función principal de extracción de datos. Retorna una tupla de 12 campos + log (13 elementos).
    """
    debug_output: str = ""
    extracted_data_raw: Tuple = tuple()

    try:
        lines = _get_pdf_lines(pdf_path)

        if not lines:
            debug_output += "Error: No se pudo leer texto del documento (PDF o Imagen)."
            return (*_pad_data(extracted_data_raw), debug_output)

        if debug_mode:
            debug_output += f"🔍 DEBUG MODE ACTIVATED: Document read successfully.\n\n"
            for i, linea in enumerate(lines):
                debug_output += f"Line {i:02d}: {linea}\n"
            debug_output += "\n"

        # 1. Mapeo y Carga DINÁMICA del Extractor
        full_class_path = find_extractor_for_file(pdf_path)
        doc_path_for_extractor = pdf_path

        ExtractorClass = None
        if full_class_path:
            print("entramos en full_class_path:")
            debug_output += f"➡️ Extractor encontrado en mapeo: {full_class_path}\n"
            try:
                ExtractorClass = _load_extractor_class_dynamic(full_class_path)
            except RuntimeError as e:
                debug_output += f"❌ ERROR en la carga dinámica del extractor: {e}\n"
                pass # Continúa al extractor genérico

        if ExtractorClass:
            print("entramos en ExtractorClass:")
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
                return (*_pad_data(extracted_data_raw), debug_output)

            except Exception as e:
                debug_output += f"❌ ERROR: Falló la ejecución del extractor para '{full_class_path}'. Error: {e}\n"
                # Continúa al extractor genérico

        # 3. Extractor Genérico (Fallback)
        print("entramos en Extractor Genérico:")
        debug_output += "➡️ No specific invoice type detected or specific extractor failed. Using generic extraction function (BaseInvoiceExtractor).\n"
        generic_extractor = BaseInvoiceExtractor(lines, doc_path_for_extractor)
        extracted_data_raw = generic_extractor.extract_all()
        debug_output += "✅ Extracción exitosa con Extractor Genérico.\n"
        return (*_pad_data(extracted_data_raw), debug_output)

    except Exception as e:
        traceback_str = traceback.format_exc()
        debug_output += f"❌ FATAL ERROR durante la extracción: {e}\n{traceback_str}"
        return (*ERROR_DATA[:-1], debug_output)