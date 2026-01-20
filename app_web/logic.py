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

# --- Funciones de Utilidad ---

def _get_pdf_lines(pdf_path: str) -> List[str]:
    """Extrae el texto de un PDF o Imagen. Punto único de OCR."""
    lines: List[str] = []
    file_extension = os.path.splitext(pdf_path)[1].lower()
    
    if file_extension == ".pdf":
        try:
            doc = fitz.open(pdf_path)
            texto = "".join([page.get_text() or '' for page in doc])
            doc.close()
            lines = [l for l in texto.splitlines() if l.strip()]
            if lines: return lines
        except Exception:
            pass

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

def _detectar_extractor_automatico(lines: List[str]) -> Optional[str]:
    """
    Busca en el contenido del texto si coincide con algún cliente.
    """
    try:
        # Se conecta a la BD solo cuando se llama a la función, no al importar el archivo
        clientes = database.fetch_all_clients()
        texto_completo = " ".join(lines).upper()

        for cliente in clientes:
            extractor_pref = cliente.get('extractor_default')
            if not extractor_pref or extractor_pref == 'GENERICO':
                continue

            # 1. Comprobar CIF 
            cif = cliente.get('cif', '').strip().upper()
            if cif and len(cif) > 5 and cif in texto_completo:
                return extractor_pref

            # 2. Comprobar Palabras Clave
            palabras = cliente.get('palabras_clave', '')
            if palabras:
                lista_kws = [k.strip().upper() for k in palabras.split(',') if k.strip()]
                for kw in lista_kws:
                    if kw in texto_completo:
                        return extractor_pref
    except Exception as e:
        print(f"Error en detección automática: {e}")
    
    return None

# --- Función de Extracción Principal ---

def extraer_datos(pdf_path: str, debug_mode: bool = False, extractor_manual: str = None) -> Tuple[Any, ...]:
    """Extrae datos de la factura y devuelve una tupla de 13 campos + logs."""
    debug_output = ""
    
    # [CORRECCIÓN] Cargamos el mapeo AQUÍ dentro, no fuera.
    # Así aseguramos que la BD ya está iniciada antes de leerla.
    try:
        extraction_mapping = database.get_extraction_mapping()
    except Exception:
        extraction_mapping = {}

    try:
        lines = _get_pdf_lines(pdf_path)
        if not lines:
            return (*[None]*13, "Error: No se detectó texto.")

        extractor_name_to_use = None

        # 1. Estrategia: ¿Tenemos extractor manual?
        if extractor_manual and extractor_manual in extraction_mapping:
            extractor_name_to_use = extractor_manual
            debug_output += f"🔧 Modo Manual seleccionado: {extractor_name_to_use}\n"
        else:
            # 2. Estrategia: Detección Automática por contenido
            detected_name = _detectar_extractor_automatico(lines)
            if detected_name and detected_name in extraction_mapping:
                extractor_name_to_use = detected_name
                debug_output += f"🤖 Auto-detección: Encontrado patrón para extractor '{extractor_name_to_use}'\n"
            else:
                debug_output += "ℹ️ No se detectó cliente específico. Usando Genérico.\n"

        # 3. Cargar la clase correspondiente
        full_class_path = None
        if extractor_name_to_use:
            full_class_path = extraction_mapping.get(extractor_name_to_use)
        
        ExtractorClass = None
        if full_class_path:
            try:
                ExtractorClass = _load_extractor_class_dynamic(full_class_path)
            except Exception as e:
                debug_output += f"⚠️ Fallo carga dinámica ({full_class_path}): {e}\n"

        # 4. Ejecutar Extracción
        if ExtractorClass:
            extractor = ExtractorClass(lines, pdf_path)
            data_dict = extractor.extract_data(lines) if hasattr(extractor, 'extract_data') else {}
            
            res_raw = [
                data_dict.get('tipo'), data_dict.get('fecha'), data_dict.get('num_factura'),
                data_dict.get('emisor'), data_dict.get('cif_emisor'), data_dict.get('cliente'),
                data_dict.get('cif'), data_dict.get('modelo'), data_dict.get('matricula'),
                data_dict.get('importe'), data_dict.get('base'), data_dict.get('iva'), data_dict.get('tasas')
            ]
        else:
            generic = BaseInvoiceExtractor(lines, pdf_path)
            res_raw = generic.extract_all()

        res_list = list(res_raw[:13])
        return (*res_list, debug_output)

    except Exception as e:
        tb = traceback.format_exc()
        return (*[None]*13, f"❌ ERROR FATAL en logic.py: {e}\n{tb}")

def process_single_pdf(pdf_path: str) -> Tuple[bool, str]:
    """Coordina verificación de duplicados, extracción y guardado en base de datos."""
    debug_output = f"--- Procesando archivo: {os.path.basename(pdf_path)} ---\n"
    try:
        # 1. Verificar duplicados
        if database.is_invoice_processed(pdf_path):
            return False, debug_output + f"🚫 Factura ya procesada anteriormente.\n"

        # 2. Extraer
        res_raw = extraer_datos(pdf_path)
        res_list = list(res_raw[:13])
        debug_log = res_raw[13]
        debug_output += debug_log
        
        # 3. Guardar si hay datos
        if any(res_list): 
            data_dict = {
                'Tipo': res_list[0], 'Fecha': res_list[1], 'Número de Factura': res_list[2],
                'Emisor': res_list[3], 'CIF Emisor': res_list[4], 'Cliente': res_list[5],
                'CIF': res_list[6], 'Modelo': res_list[7], 'Matricula': res_list[8],
                'Importe': res_list[9], 'Base': res_list[10], 'IVA': res_list[11],
                'Tasas': res_list[12], 'Concepto': 'Importación Manual'
            }
            
            database.insert_invoice_data(data_dict, pdf_path, is_validated=0)
            debug_output += f"\n✅ Datos guardados en BD con éxito."
            return True, debug_output
        else:
            return False, debug_output + "\n❌ No se extrajeron datos válidos."

    except Exception as e:
        return False, debug_output + f"\n❌ Error: {str(e)}"