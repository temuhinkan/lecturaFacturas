import os
import sys
import importlib
import importlib.util
import tempfile
import traceback
from typing import Tuple, List, Optional, Any, Dict
import re

# Importaciones para extracción de PDF y OCR
import fitz # PyMuPDF
try:
    from PIL import Image
    import pytesseract
except ImportError:
    Image = None
    pytesseract = None

# Dependencias del proyecto
from config import ERROR_DATA, TESSERACT_CMD_PATH, DEFAULT_VAT_RATE_STR
import database
from extractors.base_invoice_extractor import BaseInvoiceExtractor

# --- Configuración de OCR (Tesseract) ---
if sys.platform == "win32" and pytesseract and TESSERACT_CMD_PATH:
    try:
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD_PATH
    except Exception as e:
        print(f"Error al configurar Tesseract: {e}")

# --- Mapeo Global de Extractores (Cargado de BBDD) ---
EXTRACTION_MAPPING: Dict[str, str] = database.get_extraction_mapping()

# --- Funciones de Utilidad de Reglas (Optimizadas fuera de bucles) ---

def find_reference_line(lines: List[str], ref_text: str) -> Optional[int]:
    """Busca el índice de una línea que contiene un texto de referencia."""
    ref_text_lower = ref_text.lower()
    for i, line in enumerate(lines):
        if ref_text_lower in line.lower():
            return i
    return None

def apply_extraction_rule(lines: List[str], mapping: Dict[str, Any]) -> Optional[str]:
    """Aplica la lógica de una regla específica sobre el texto extraído."""
    if mapping.get('type') == 'FIXED_VALUE':
        return mapping.get('value')
        
    line_index = None
    if mapping.get('type') == 'FIXED':
        abs_line = mapping.get('line')
        if abs_line and abs_line > 0:
            line_index = abs_line - 1 
    elif mapping.get('type') == 'VARIABLE':
        ref_index = find_reference_line(lines, mapping.get('ref_text', ''))
        if ref_index is not None:
            line_index = ref_index + mapping.get('offset', 0)
            
    if line_index is None or not (0 <= line_index < len(lines)):
        return None
        
    try:
        segments = re.split(r'\s+', lines[line_index].strip())
        segments = [s for s in segments if s]
        segment_input = mapping.get('segment', 1)
        
        # Manejo de rangos (ej. '1-3')
        if isinstance(segment_input, str) and '-' in segment_input:
            start_s, end_s = segment_input.split('-')
            start_idx, end_idx = int(start_s) - 1, int(end_s)
            if 0 <= start_idx < end_idx <= len(segments):
                return ' '.join(segments[start_idx:end_idx]).strip()
        
        # Segmento simple
        idx = int(segment_input) - 1
        return segments[idx] if 0 <= idx < len(segments) else None
    except Exception:
        return None

# --- Funciones Principales de Lógica ---

def _get_pdf_lines(pdf_path: str) -> List[str]:
    """Extrae el texto de un PDF o Imagen. Punto único de OCR."""
    lines: List[str] = []
    file_extension = os.path.splitext(pdf_path)[1].lower()
    
    # 1. Intento de lectura directa (PDF con capa de texto)
    if file_extension == ".pdf":
        try:
            doc = fitz.open(pdf_path)
            texto = "".join([page.get_text() or '' for page in doc])
            doc.close()
            lines = [l for l in texto.splitlines() if l.strip()]
            if lines: return lines
        except Exception:
            pass

    # 2. OCR (Fallback para imágenes o PDFs escaneados)
    if Image and pytesseract:
        try:
            if file_extension in ['.jpg', '.jpeg', '.png', '.tiff', '.tif']:
                ocr_text = pytesseract.image_to_string(Image.open(pdf_path), lang='spa')
            elif file_extension == ".pdf":
                doc = fitz.open(pdf_path)
                if len(doc) > 0:
                    page = doc.load_page(0)
                    pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))
                    temp_path = os.path.join(tempfile.gettempdir(), f"ocr_tmp_{os.getpid()}.png")
                    pix.save(temp_path)
                    ocr_text = pytesseract.image_to_string(Image.open(temp_path), lang='spa')
                    if os.path.exists(temp_path): os.remove(temp_path)
                doc.close()
            
            lines = [l for l in ocr_text.splitlines() if l.strip()]
        except Exception as e:
            print(f"Error crítico en OCR: {e}")
            
    return lines

def find_extractor_for_file(file_path: str, lines: List[str]) -> Optional[str]:
    """Identifica el extractor usando el nombre del archivo o el contenido (CIF)."""
    nombre_archivo = os.path.basename(file_path).lower()
    
    # 1. Por nombre de archivo
    for keyword, class_path in EXTRACTION_MAPPING.items():
        if keyword.lower() in nombre_archivo:
            return class_path

    # 2. Por contenido (CIF Emisor)
    if not lines: return None
    texto_completo = "\n".join(lines).upper()
    CIF_CLIENTE_FIJO = "B85629020" # Ignorar CIF propio
    
    patron_cif = re.compile(r'[A-Z]\d{7,8}[A-Z0-9]?')
    cifs_documento = set(patron_cif.findall(texto_completo))
    
    for keyword, class_path in EXTRACTION_MAPPING.items():
        try:
            config = database.get_extractor_configuration(keyword)
            if not config or 'CIF_EMISOR' not in config: continue
            
            for rule in config['CIF_EMISOR']:
                val = apply_extraction_rule(lines, rule)
                if val:
                    cif_objetivo = val.replace('-', '').replace('.', '').strip().upper()
                    if cif_objetivo in cifs_documento and cif_objetivo != CIF_CLIENTE_FIJO:
                        return class_path
        except Exception:
            continue
    return None

def _load_extractor_class_dynamic(extractor_path_str: str):
    """Carga una clase de extractor dinámicamente."""
    try:
        parts = extractor_path_str.split('.')
        module_name, class_name = ".".join(parts[:-1]), parts[-1]
        
        module_spec = importlib.util.find_spec(module_name)
        if not module_spec: raise ImportError(f"Módulo {module_name} no encontrado")
        
        module = importlib.util.module_from_spec(module_spec)
        module.__dict__['BaseInvoiceExtractor'] = BaseInvoiceExtractor
        sys.modules[module_name] = module
        module_spec.loader.exec_module(module)
        return getattr(module, class_name)
    except Exception as e:
        raise RuntimeError(f"Error cargando {extractor_path_str}: {e}")



def extraer_datos(pdf_path: str, debug_mode: bool = False, extractor_manual: str = None) -> Tuple[Any, ...]:
    """
    Función principal. 
    Si extractor_manual tiene un valor (ej: 'Leroy'), 
    busca su ruta de clase correcta (ej: 'extractors.leroy.Leroy') y fuerza su uso.
    """
    debug_output = ""
    try:
        # 1. LECTURA ÚNICA
        lines = _get_pdf_lines(pdf_path)
        if not lines:
            return (*[None]*13, "Error: No se detectó texto en el documento.")

        if debug_mode:
            debug_output += "🔍 DEBUG: Texto extraído correctamente.\n"
            for i, l in enumerate(lines[:20]):
                debug_output += f"L{i:02d}: {l}\n"

        # 2. IDENTIFICACIÓN / SELECCIÓN DE EXTRACTOR
        ExtractorClass = None
        full_class_path = None

        if extractor_manual:
            # --- CORRECCIÓN AQUÍ ---
            # Buscamos la ruta completa en el mapeo cargado de la BBDD
            if extractor_manual in EXTRACTION_MAPPING:
                full_class_path = EXTRACTION_MAPPING[extractor_manual]
            else:
                # Fallback: Si no está en el mapa, intentamos la convención estándar:
                # extractors.<nombre_minuscula>.<NombreExacto>
                # Ej: extractors.leroy.Leroy
                full_class_path = f"extractors.{extractor_manual.lower()}.{extractor_manual}"
            
            debug_output += f"⚡ FORZADO MANUAL: Usando {extractor_manual} -> Ruta: {full_class_path}...\n"
        else:
            # Lógica de detección automática habitual
            full_class_path = find_extractor_for_file(pdf_path, lines)

        # 3. CARGA DINÁMICA
        if full_class_path:
            try:
                ExtractorClass = _load_extractor_class_dynamic(full_class_path)
            except Exception as e:
                debug_output += f"⚠️ Fallo carga dinámica de {full_class_path}: {e}\n"

        # 4. EXTRACCIÓN
        if ExtractorClass:
            extractor = ExtractorClass(lines, pdf_path)
            data_dict = extractor.extract_data(lines) if hasattr(extractor, 'extract_data') else {}
            res_raw = (
                data_dict.get('tipo'), data_dict.get('fecha'), data_dict.get('num_factura'),
                data_dict.get('emisor'), data_dict.get('cif_emisor'), data_dict.get('cliente'),
                data_dict.get('cif'), data_dict.get('modelo'), data_dict.get('matricula'),
                data_dict.get('importe'), data_dict.get('base'), data_dict.get('iva'), data_dict.get('tasas')
            )
            debug_output += f"✅ Usado extractor: {full_class_path}\n"
        else:
            # Fallback Genérico si no hay manual ni automático detectado o si falló la carga
            from extractors.base_invoice_extractor import BaseInvoiceExtractor
            generic = BaseInvoiceExtractor(lines, pdf_path)
            res_raw = generic.extract_all()
            debug_output += "ℹ️ Usado extractor genérico (BaseInvoiceExtractor).\n"

        # 5. LÓGICA DE RESCATE (Igual que antes)
        res_list = list(res_raw[:13])
        # ... (aquí va tu código de rescate de CIF si lo tenías implementado, si no, dejar vacío) ...

        return (*res_list, debug_output)

    except Exception as e:
        import traceback
        return (*[None]*13, f"❌ ERROR FATAL: {e}\n{traceback.format_exc()}")