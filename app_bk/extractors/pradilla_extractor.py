from typing import Dict, Any, List, Optional
import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from config import DEFAULT_VAT_RATE 
import math
from typing import Tuple
import database

EXTRACTOR_KEY = "pradilla"

EXTRACTION_MAPPING: Dict[str, Dict[str, Any]] = database.get_extractor_configuration(EXTRACTOR_KEY)
# print("EXTRACTION_MAPPING",EXTRACTION_MAPPING) # Debug opcional

EXTRACTION_MAPPING_PROCESSED = {}
for key, value in EXTRACTION_MAPPING.items():
    if isinstance(value, list) and len(value) > 0:
        EXTRACTION_MAPPING_PROCESSED[key] = value[0]
    elif isinstance(value, dict):
        EXTRACTION_MAPPING_PROCESSED[key] = value
    else:
        EXTRACTION_MAPPING_PROCESSED[key] = None

# Reemplaza el mapeo original con el procesado para uso por defecto
# NOTA: En tu código original usas el EXTRACTION_MAPPING completo (listas) dentro del bucle, 
# por lo que no usaremos EXTRACTION_MAPPING_PROCESSED para la lógica principal, 
# sino el diccionario original cargado de la BBDD.

class PradillaExtractor(BaseInvoiceExtractor):
    
    def __init__(self, lines: List[str] = None, pdf_path: str = None, *args, **kwargs):
        try:
             super().__init__(lines=lines, pdf_path=pdf_path, *args, **kwargs)
        except TypeError:
             try:
                 super().__init__()
             except:
                 pass
        
    # --- FUNCIÓN DE LIMPIEZA NUMÉRICA ---
    def _clean_and_convert_float(self, value: Optional[str]) -> Optional[float]:
        if value is None or str(value).strip() == '':
            return None
        
        cleaned_value = str(value).strip()
        # Eliminar símbolos y caracteres comunes de OCR en facturas
        cleaned_value = cleaned_value.replace('€', '').replace('$', '').replace('%', '').replace(':', '').replace('(', '').replace(')', '').replace('[', '').replace(']', '').replace('?', '').replace('!', '').replace(' ', '').replace('EUROS','').replace('EUR','')
        
        temp_value = cleaned_value
        
        # CASO 1: Formato Español (1.234,56 -> 1234.56)
        if '.' in temp_value and ',' in temp_value and temp_value.rfind('.') < temp_value.rfind(','):
            temp_value = temp_value.replace('.', '').replace(',', '.')
        # CASO 2: Solo Coma (247,93 -> 247.93)
        elif ',' in temp_value:
            temp_value = temp_value.replace(',', '.')
        # CASO 3: Solo Punto (247.93) - OK
        
        try:
            return float(temp_value)
        except ValueError:
            return None

    def is_only_text_tolerant(self, value: Optional[str]) -> bool:
        if value is None or not value.strip():
            return False
        input_str = str(value)
        if not re.search(r'[a-zA-Z]', input_str):
            return False
        if re.search(r'\d', input_str):
            return False
        return True

    # --- VALIDADORES MEJORADOS Y ROBUSTOS ---

    def validar_matricula(self, matricula: str) -> Optional[str]:
        """
        Valida Y LIMPIA una matrícula. Devuelve la matrícula limpia si es válida, o None.
        Formato: 4 números, 3 consonantes (NNNNCCC o NNNN-CCC).
        """
        if not matricula:
            return None
        
        # Limpieza previa: Quitar espacios, puntos (común en OCR al final), guiones
        clean = str(matricula).upper().replace(' ', '').replace('.', '').replace(',', '').replace('|', '').strip()
        
        # Regex flexible: busca el patrón dentro de la cadena limpia
        # Busca 4 dígitos seguidos de 3 letras consonantes
        match = re.search(r"([0-9]{4}-?[BCDFGHJKLMNÑPQRSTVWXYZ]{3})", clean)
        
        if match:
            return match.group(1) # Devuelve solo la parte que coincide (ej: 1551LVR)
        return None
    
    def validar_fecha(self, fecha: str) -> Optional[str]:
        """
        Valida Y LIMPIA una fecha. Devuelve la fecha limpia si es válida, o None.
        """
        if not fecha:
            return None
            
        # Limpieza básica
        clean = str(fecha).strip().replace('|', '').replace('.', ' ').strip()
        
        # Regex para capturar la fecha dentro de texto sucio
        # (01-31) [/-] (01-12) [/-] (20xx o xx)
        patron = r"\b(0[1-9]|[12][0-9]|3[01])[/-](0[1-9]|1[0-2])[/-]([0-9]{2}|[0-9]{4})\b"
        
        match = re.search(patron, clean)
        if match:
            return match.group(0) # Devuelve la fecha encontrada (ej: 07/11/2025)
        return None

    def validar_numero_factura(self, numero_factura: str) -> Optional[str]:
        """
        Valida si contiene 8 dígitos. Devuelve SOLO los 8 dígitos si los encuentra.
        Maneja ruido como '25032883 |' -> '25032883'.
        """
        if not numero_factura:
            return None
            
        # Buscar secuencia exacta de 8 dígitos
        match = re.search(r"\b([0-9]{8})\b", str(numero_factura))
        if match:
            return match.group(1)
        return None

    def check_importes(self, base: Optional[float], iva: Optional[float], importe: Optional[float], tasas :Optional[float]) -> Tuple[float,float,float,str, str, str,]:
        tasas = tasas if tasas is not None else 0.00
        # print("valores iniciales",base,iva,importe,tasas)
        TOLERANCE = 0.01 
        missing_count = sum(v is None for v in [base, iva, importe])
        
        if missing_count == 1:
            if importe is None and base is not None and iva is not None:
                importe = base + iva + tasas
            elif iva is None and base is not None and importe is not None and importe >= base:
                iva = importe - base - tasas
            elif base is None and iva is not None and importe is not None and importe >= iva:
                base = importe - iva - tasas      
        elif missing_count == 2:
            if importe is not None and importe > 0:
                importe_sin_tasas = importe - tasas 
                if importe_sin_tasas > 0:
                    base = importe_sin_tasas / (1 + DEFAULT_VAT_RATE) 
                    iva = importe_sin_tasas - base
                else:
                    base = 0.00
                    iva = 0.00
            elif iva is None and importe is None and base is not None and base > 0:
                 # Asumimos cálculo directo si tenemos base
                iva = base * DEFAULT_VAT_RATE
                importe = base + iva + tasas

        elif missing_count == 0:
            if not math.isclose(base + iva + tasas, importe, abs_tol=TOLERANCE):
                # print(f"⚠️ Importes inconsistentes. Recalculando IVA.")
                iva = importe - base - tasas

        base = base if base is not None else 0.00
        iva = iva if iva is not None else 0.00
        importe = importe if importe is not None else 0.00
        
        def format_float_to_string(num):
            return f"{round(num, 2):.2f}".replace('.', ',')

        return base, iva, importe, format_float_to_string(base), format_float_to_string(iva), format_float_to_string(importe)

        
    def extract_data(self, lines: List[str]) -> Dict[str, Any]:
        
        extracted_data = {}
        valor_iva=None
        valor_base=None
        valor_importe=None
        valor_tasas=None
        
        def find_reference_line(ref_text: str) -> Optional[int]:
            ref_text_lower = ref_text.lower()
            for i, line in enumerate(lines):
                if line and ref_text_lower in line.lower():
                    return i
            return None

        def get_value(mapping: Dict[str, Any]) -> Optional[str]:
            if mapping['type'] == 'FIXED_VALUE':
                return mapping.get('value')
                
            line_index = None
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
                
            segment_input = mapping['segment']
            line_content = lines[line_index]
            if line_content is None: return None
            
            try:
                # Split por espacio
                line_segments = re.split(r'\s+', line_content.strip())
                line_segments = [seg for seg in line_segments if seg]
                
                if isinstance(segment_input, str) and re.match(r'^\d+-\d+$', segment_input):
                    start_s, end_s = segment_input.split('-')
                    start_idx = int(start_s) - 1
                    end_idx = int(end_s)
                    if 0 <= start_idx < end_idx and end_idx <= len(line_segments) + 1: # +1 tolerancia
                         # Corrección de rango seguro
                         safe_end = min(end_idx, len(line_segments))
                         return ' '.join(line_segments[start_idx:safe_end]).strip()
                
                segment_index_0based = int(segment_input) - 1
                if 0 <= segment_index_0based < len(line_segments):
                    return line_segments[segment_index_0based].strip()
            except Exception:
                return None
            return None

        # Mapeo de validadores actualizado
        VALIDATORS = {
            "NUM_FACTURA": self.validar_numero_factura,
            "FECHA": self.validar_fecha,
            "MATRICULA": self.validar_matricula, 
        }

        # Bucle Principal
        for key, mapping in EXTRACTION_MAPPING.items():
            value = None
            # Aseguramos que mapping sea lista para iterar uniformemente
            mapping_list = mapping if isinstance(mapping, list) else [mapping]
            
            for single_mapping in mapping_list:
                temp_value = get_value(single_mapping)
                
                if temp_value:
                    # 1. Limpieza básica PREVIA a validación (quitar ruido OCR típico)
                    temp_value = temp_value.strip().strip('|').strip('.').strip()

                    # 2. Validación y Extracción Limpia
                    is_valid = True
                    clean_extracted_value = temp_value # Por defecto asumimos que es el valor

                    if key in VALIDATORS:
                        # Los validadores ahora devuelven el valor limpio o None
                        validated_val = VALIDATORS[key](temp_value)
                        if validated_val is not None:
                            clean_extracted_value = validated_val
                            is_valid = True
                            print(f"✅ {key}: Validado '{temp_value}' -> '{clean_extracted_value}'")
                        else:
                            is_valid = False
                            print(f"❌ {key}: Falló validación para '{temp_value}'")
                    
                    if is_valid:
                        value = clean_extracted_value
                        break # Encontrado y validado, dejamos de buscar este campo

            # --- POST-PROCESAMIENTO GENÉRICO (para campos numéricos que vienen como texto) ---
            if value is not None:
                 # Patrón: "123,45 Texto" -> quedarse con 123,45
                 pattern_num_start = r"^([0-9.,]+)\s.*$"
                 if re.match(pattern_num_start, str(value)) and key not in VALIDATORS:
                      match = re.match(pattern_num_start, str(value))
                      if match:
                           value = match.group(1)

            # --- ASIGNACIÓN AL DICCIONARIO FINAL ---
            key_lower = key.lower()
            
            if key_lower in ['base', 'iva', 'importe', 'tasas']:
                cleaned_float = self._clean_and_convert_float(value)
                if key_lower == 'base': valor_base = cleaned_float
                elif key_lower == 'iva': valor_iva = cleaned_float
                elif key_lower == 'importe': valor_importe = cleaned_float
                elif key_lower == 'tasas': valor_tasas = cleaned_float
                extracted_data[key_lower] = cleaned_float
            else:
                extracted_data[key_lower] = value

        # Recálculo final de importes
        _, _, _, base_str, iva_str, importe_str = self.check_importes(valor_base, valor_iva, valor_importe, valor_tasas)
        extracted_data['base'] = base_str
        extracted_data['iva'] = iva_str
        extracted_data['importe'] = importe_str
        
        return extracted_data