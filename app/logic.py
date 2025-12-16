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
# from config import EXTRACTION_MAPPING, TESSERACT_CMD_PATH, ERROR_DATA, DEFAULT_VAT_RATE_STR
from config import ERROR_DATA, TESSERACT_CMD_PATH, DEFAULT_VAT_RATE_STR # La constante EXTRACTION_MAPPING ya no se importa
# Asegurarse de que 'import database' está presente (si no lo está, agréguelo)
import database
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
# OBTENER MAPEO DE EXTRACTORES DE LA BBDD (Módulo Global)
# ----------------------------------------------------------------------
# 🚨 ESTA ES LA CLAVE: Define la variable a nivel de módulo llamando a la BBDD.
EXTRACTION_MAPPING: Dict[str, str] = database.get_extraction_mapping()
print(f"DEBUG FLOW: Mapeo de extractores cargado de BBDD al módulo LOGIC. {len(EXTRACTION_MAPPING)} entradas.")
# ----------------------------------------------------------------------

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
    """Identifica el extractor adecuado por nombre de archivo o buscando CIFs conocidos en el texto."""
    
    # Dependencias necesarias (asumo que ya existen en tu entorno)
    # import os
    # import re
    # from typing import Optional, Dict, Any
    # from . import database # Asumo que database es accesible
    # from ._utils import _get_pdf_lines # Asumo que _get_pdf_lines está definido en alguna utilidad
    
    nombre_archivo = os.path.basename(file_path).lower()
    
    # --- 1. Búsqueda por palabra clave en el nombre del archivo (Rápida) ---
    print("DEBUG FLOW: find_extractor_for_file: Iniciando búsqueda por nombre.")
    for keyword, class_path in EXTRACTION_MAPPING.items():
        if keyword in nombre_archivo:
            print(f"DEBUG FLOW: Coincidencia por nombre '{keyword}'. Extractor: {class_path}")
            return class_path

    # --- 2. Búsqueda por contenido (CIF/NIF conocidos) ---
    print("DEBUG FLOW: No se encontró por nombre. Escaneando CIFs en el documento...")
    
    try:
        # Llamar a la función de lectura SOLO una vez y reutilizar 'lines'
        lines = _get_pdf_lines(file_path)
        if not lines: return None
        
        texto_completo = "\n".join(lines).upper()
        
        # CIF de tu empresa que siempre debemos ignorar como emisor
        CIF_CLIENTE_FIJO = "B85629020" 
        
        # Expresión regular para capturar cualquier CIF/NIF (Letra + 7/8 dígitos + opcional)
        patron_cif = re.compile(r'[A-Z]\d{7,8}[A-Z0-9]?')
        cifs_encontrados = patron_cif.findall(texto_completo)
        
        # Limpiamos, estandarizamos y eliminamos duplicados del documento
        cifs_limpios = set([
            c.replace('-', '').replace('.', '').strip()
            for c in cifs_encontrados
        ])
        
        if not cifs_limpios:
            print("DEBUG FLOW: No se detectó ningún patrón de CIF en el texto.")
            return None

        print(f"DEBUG FLOW: CIFs detectados en el PDF: {cifs_limpios}")
        print(f"VERIFICACION DE CIFS")

        # Se mantiene la función get_value aquí, ya que depende de 'lines'
        # --- Funciones Auxiliares (reubicadas para claridad/contexto) ---
        def find_reference_line(ref_text: str) -> Optional[int]:
            ref_text_lower = ref_text.lower()
            for i, line in enumerate(lines):
                if ref_text_lower in line.lower():
                    return i
            return None
            
        def get_value(mapping: Dict[str, Any]) -> Optional[str]:
            
            # 1. Caso FIXED_VALUE (valor constante)
            if mapping['type'] == 'FIXED_VALUE':
                return mapping.get('value')
                
            line_index = None
            
            # 2. Determinar el índice de la línea final (0-based)
            if mapping['type'] == 'FIXED':
                abs_line_1based = mapping.get('line')
                if abs_line_1based is not None and abs_line_1based > 0:
                    line_index = abs_line_1based - 1 
                    
            elif mapping['type'] == 'VARIABLE':
                ref_text = mapping.get('ref_text', '')
                offset = mapping.get('offset', 0)
                
                ref_index = find_reference_line(ref_text)
                
                if ref_index is not None:
                    line_index = ref_index + offset
                
            if line_index is None or not (0 <= line_index < len(lines)):
                return None
                
            # 3. Obtener el segmento
            segment_input = mapping['segment']
            
            try:
                # Dividir por espacios para obtener segmentos de la línea
                line_segments = re.split(r'\s+', lines[line_index].strip())
                line_segments = [seg for seg in line_segments if seg]
                
                # Manejar rangos de segmentos (ej. '1-3')
                if isinstance(segment_input, str) and re.match(r'^\d+-\d+$', segment_input):
                    start_s, end_s = segment_input.split('-')
                    start_idx = int(start_s) - 1 # 0-based start
                    end_idx = int(end_s)        # 0-based exclusive end
                    
                    if 0 <= start_idx < end_idx and end_idx <= len(line_segments):
                        return ' '.join(line_segments[start_idx:end_idx]).strip()
                    
                # Manejar segmento simple (ej. 1)
                segment_index_0based = int(segment_input) - 1
                
                if segment_index_0based < len(line_segments):
                    return line_segments[segment_index_0based].strip()
            except Exception:
                # Si falla al parsear el segmento o el índice, simplemente devuelve None
                return None
                
            return None
        # --- Fin Funciones Auxiliares ---


        # Iteramos sobre todos los extractores conocidos
        for keyword, class_path in EXTRACTION_MAPPING.items():
            print("class_path ", class_path, " keyword", keyword)

            try:
                # Obtenemos la configuración de extracción para este extractor
                EXTRACTION_MAPPING_CAMPIOS: Dict[str, Dict[str, Any]] = database.get_extractor_configuration(keyword)
                
                # Verificamos si este extractor tiene un mapeo para el CIF del emisor
                cif_emisor_mappings = EXTRACTION_MAPPING_CAMPIOS.get('CIF_EMISOR', [])

                if not cif_emisor_mappings:
                    # Si no hay mapeo de CIF_EMISOR para este extractor, pasamos al siguiente
                    continue
                
                # Iteramos sobre todos los posibles mappings para 'CIF_EMISOR' (Solución al error)
                for cif_mapping in cif_emisor_mappings:
                    
                    # 'cif_mapping' ahora es el diccionario simple esperado por get_value
                    value = get_value(cif_mapping)
                    
                    if value:
                        # Limpiar el CIF extraído para compararlo con los cifs_limpios del documento
                        cif_objetivo = value.replace('-', '').replace('.', '').strip().upper() 
                        
                        print(f"DEBUG FLOW: Evaluando {keyword}. CIF objetivo: {cif_objetivo}")

                        # Verificación
                        if cif_objetivo in cifs_limpios and cif_objetivo != CIF_CLIENTE_FIJO:
                            print(f"DEBUG FLOW: ¡Match encontrado! El CIF {cif_objetivo} está en el documento. Usando: {class_path}")
                            return class_path
                    
                    # Si no hay match con este mapping específico, continuamos probando el siguiente mapping de CIF_EMISOR
                    
            except Exception as e:
                # Este except captura errores durante la obtención/procesamiento de la configuración del extractor actual
                print(f"DEBUG FLOW: Error al procesar la configuración del extractor '{keyword}': {e}")
                continue # Continuar con el siguiente extractor

    except Exception as e:
        # Este except captura errores generales (ej. error en _get_pdf_lines o en la expresión regular inicial)
        print(f"DEBUG FLOW: Error en búsqueda exhaustiva de CIF: {e}")

    print("DEBUG FLOW: No se encontró ningún CIF emisor conocido. Se usará el extractor genérico.")
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
        # ==============================================================================
        # [INICIO] NUEVO BLOQUE DE RESCATE PARA CIF (AÑADIR ESTO)
        # ==============================================================================
        # Si el CIF del emisor (índice 4) es None, intentamos buscarlo "mirando la siguiente línea"
        # La tupla es: (Tipo, Fecha, Num, Emisor, CIF_EMISOR, ...)
        
        # Convertimos a lista porque las tuplas no se pueden modificar
        data_list = list(_pad_data(extracted_data_raw))
        cif_emisor_index = 4 

        if not data_list[cif_emisor_index]: # Si no hay CIF
            print("DEBUG FLOW: CIF no encontrado por extractor base. Intentando rescate 'línea siguiente'.")
            for i, line in enumerate(lines):
                # Buscamos la etiqueta, ignorando mayúsculas/minúsculas
                if "CIF" in line.upper() or "NIF" in line.upper():
                    # Verificamos que no estemos en la última línea
                    if i + 1 < len(lines):
                        next_line = lines[i+1].strip()
                        # Regex simple para CIF/NIF español: Letra al principio, longitud aprox 9
                        if re.match(r'^[A-Z]\d{7,8}[A-Z0-9]$', next_line):
                            data_list[cif_emisor_index] = next_line
                            debug_output += f"⚠️ CIF recuperado por lógica de rescate en logic.py: {next_line}\n"
                            print(f"DEBUG FLOW: CIF rescatado: {next_line}")
                            break
        
        # Reconstruimos la tupla con los datos (posiblemente) corregidos
        extracted_data_raw = tuple(data_list)
        # ==============================================================================
        # [FIN] NUEVO BLOQUE DE RESCATE
        # ==============================================================================
        debug_output += "✅ Extracción exitosa con Extractor Genérico.\n"
        print("DEBUG FLOW: Extracción con extractor genérico completada.")
        return (*_pad_data(extracted_data_raw), debug_output)

    except Exception as e:
        traceback_str = traceback.format_exc()
        debug_output += f"❌ FATAL ERROR durante la extracción: {e}\n{traceback_str}"
        print(f"DEBUG FLOW: ERROR FATAL en extraer_datos. {e}")
        return (*ERROR_DATA[:-1], debug_output)