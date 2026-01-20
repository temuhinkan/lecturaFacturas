from typing import Dict, Any, List, Optional
import re

# La clase BaseInvoiceExtractor será INYECTADA en tiempo de ejecución (soluciona ImportError en main_extractor_gui.py).

# 🚨 EXTRACTION_MAPPING: Define la lógica de extracción.
# 'VARIABLE_ALL': (NUEVO TIPO) Busca todas las coincidencias y concatena.
# Se usan LISTAS para manejar múltiples formatos (intentos).
import database
EXTRACTOR_KEY = "aema"

EXTRACTION_MAPPING: Dict[str, Dict[str, Any]] = database.get_extractor_configuration(EXTRACTOR_KEY)
print("EXTRACTION_MAPPING",EXTRACTION_MAPPING)

EXTRACTION_MAPPING_PROCESSED = {}
for key, value in EXTRACTION_MAPPING.items():
    if isinstance(value, list) and len(value) > 0:
        # Tomar el primer diccionario de la lista
        EXTRACTION_MAPPING_PROCESSED[key] = value[0]
    elif isinstance(value, dict):
        # Si ya es un diccionario, usarlo directamente
        EXTRACTION_MAPPING_PROCESSED[key] = value
    else:
        # Manejar otros casos o ignorar
        EXTRACTION_MAPPING_PROCESSED[key] = None

# Reemplaza el mapeo original con el procesado
EXTRACTION_MAPPING = EXTRACTION_MAPPING_PROCESSED


EXTRACTION_MAPPING: Dict[str, Any] = {
    'TIPO': {'type': 'FIXED_VALUE', 'value': 'COMPRA'},
    'FECHA':[{'type': 'VARIABLE', 'ref_text': 'Fecha Operación', 'offset': +1, 'segment': 1},
             {'type': 'VARIABLE', 'ref_text': 'Fecha:', 'offset': -1, 'segment': 1}],
    'NUM_FACTURA':  {'type': 'VARIABLE', 'ref_text': 'Número', 'offset': +1, 'segment': 1},
    'EMISOR': {'type': 'FIXED_VALUE', 'value': 'NEUMÁTICOS AEMA, S.A.'},
    'CIF_EMISOR': {'type': 'FIXED_VALUE', 'value': 'A28625036'},
    'CLIENTE': {'type': 'FIXED_VALUE', 'value': 'NEWSATELITE S.L'},
    'CIF': {'type': 'FIXED_VALUE', 'value': 'B85629020'},
    
    # --- Mapeos Corregidos ---
    
    'MATRICULA': [
        # Intento 1 (Factura 226): Matrícula en la MISMA línea.
        {'type': 'VARIABLE_ALL', 'ref_text': 'Matrícula', 'offset': 0, 'segment': 2},
        # Intento 2 (Factura 509): Matrícula en línea SIGUIENTE. (Funciona en la traza anterior)
        {'type': 'VARIABLE_ALL', 'ref_text': 'Matrícula', 'offset': 1, 'segment': 1}, 
    ], 
    
    'MODELO': [
           # Intento 1 (Factura 226): Modelo en la MISMA línea que 'Marca/Modelo:'. Segmento '2-99'. (Funciona en la traza anterior)
           {'type': 'VARIABLE_ALL', 'ref_text': 'Marca/Modelo', 'offset': 0, 'segment': '2-99'},
           # Intento 2 (Factura 509): Modelo en la línea SIGUIENTE de 'Modelo'. Buscamos 'Modelo' (sin :) y usamos offset 1, segmento 1.
           {'type': 'VARIABLE_ALL', 'ref_text': 'Modelo', 'offset': 1, 'segment': 1},
        
    ], 
    # --- FIN Mapeos Corregidos ---
    
    'BASE': {'type': 'VARIABLE', 'ref_text': 'FORMA DE PAGO', 'offset': +8, 'segment': 1},
    'IVA': {'type': 'VARIABLE', 'ref_text': 'FORMA DE PAGO', 'offset': -1, 'segment': 1},
    'IMPORTE': {'type': 'VARIABLE', 'ref_text': 'FORMA DE PAGO', 'offset': +5, 'segment': 1},
}

class AemaExtractor:
    
    def __init__(self, lines: List[str] = None, pdf_path: str = None, *args, **kwargs):
        pass
    
    def _clean_and_convert_float(self, value: Optional[str]) -> Optional[float]:
        """Limpia cadenas para obtener un float (maneja puntos, comas y símbolos de moneda)."""
        if value is None or str(value).strip() == '':
            return None
        
        cleaned_value = str(value).strip()
        
        cleaned_value = cleaned_value.replace('€', '').replace('$', '').replace('%', '').replace(':', '').replace('(', '').replace(')', '').replace('[', '').replace(']', '').replace('?', '').replace('!', '').replace(' ', '').replace('EUROS','')
        temp_value = cleaned_value
        
        if '.' in temp_value and ',' in temp_value and temp_value.rfind('.') < temp_value.rfind(','):
            temp_value = temp_value.replace('.', '') 
            temp_value = temp_value.replace(',', '.')
        elif ',' in temp_value:
            temp_value = temp_value.replace(',', '.')
        
        cleaned_value = temp_value

        try:
            return float(cleaned_value)
        except ValueError:
            return None

    def extract_data(self, lines: List[str]) -> Dict[str, Any]:
        
        extracted_data = {}
        
        # Función auxiliar para buscar línea de referencia (primera coincidencia)
        def find_reference_line(ref_text: str) -> Optional[int]:
            ref_text_lower = ref_text.lower()
            for i, line in enumerate(lines):
                if ref_text_lower in line.lower():
                    return i
            return None
            
        # Función auxiliar para buscar *todos* los índices de línea de referencia (CON TRAZAS)
        def find_all_reference_lines(ref_text: str) -> List[int]:
            ref_text_lower = ref_text.lower()
            print(f'TRAZA: Buscando texto de referencia: "{ref_text_lower}"')
            
            # Usamos una expresión regular para buscar el texto de referencia con límites de palabra (\b)
            pattern = re.compile(r'\b' + re.escape(ref_text_lower) + r'\b', re.IGNORECASE)
            indices = [i for i, line in enumerate(lines) if pattern.search(line)]
            
            print(f'TRAZA: Índices de línea encontrados para "{ref_text_lower}": {indices}')
            return indices


        # Función auxiliar para obtener un solo valor (Simple o Fixed)
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
            
            try:
                line_segments = re.split(r'\s+', lines[line_index].strip())
                line_segments = [seg for seg in line_segments if seg]
                
                if isinstance(segment_input, str) and re.match(r'^\d+-\d+$', segment_input):
                    start_s, end_s = segment_input.split('-')
                    start_idx = int(start_s) - 1
                    end_idx = int(end_s)
                    
                    if 0 <= start_idx < end_idx and end_idx <= len(line_segments):
                        return ' '.join(line_segments[start_idx:end_idx]).strip()
                
                segment_index_0based = int(segment_input) - 1
                
                if segment_index_0based < len(line_segments):
                    return line_segments[segment_index_0based].strip()
            except Exception:
                return None
                
            return None


        # Función auxiliar para obtener *múltiples* valores y concatenarlos (VARIABLE_ALL) (CON TRAZAS)
        def get_all_values(mapping: Dict[str, Any]) -> Optional[str]:
            print(f'TRAZA: Intentando mapeo VARIABLE_ALL: {mapping}')
            ref_text = mapping.get('ref_text', '')
            offset = mapping.get('offset', 0)
            segment_input = mapping['segment']
            
            ref_indices = find_all_reference_lines(ref_text)
            
            if not ref_indices:
                print('TRAZA: Extracción fallida. No se encontraron índices de referencia.')
                return None
            
            all_values = []
            
            for ref_index in ref_indices:
                line_index = ref_index + offset
                
                if 0 <= line_index < len(lines):
                    try:
                        line_segments = re.split(r'\s+', lines[line_index].strip())
                        line_segments = [seg for seg in line_segments if seg]
                        
                        value = None
                        
                        if isinstance(segment_input, str) and re.match(r'^\d+-\d+$', segment_input):
                            start_s, end_s = segment_input.split('-')
                            start_idx = int(start_s) - 1
                            end_idx = min(int(end_s), len(line_segments)) 
                            
                            if 0 <= start_idx < end_idx:
                                value = ' '.join(line_segments[start_idx:end_idx]).strip()
                        
                        else:
                            segment_index_0based = int(segment_input) - 1
                            if segment_index_0based < len(line_segments):
                                value = line_segments[segment_index_0based].strip()

                        if value and value not in all_values:
                            all_values.append(value)
                            
                    except Exception:
                        continue 
                        
            if all_values:
                result = ', '.join(all_values)
                print(f'TRAZA: Resultado de extracción exitoso: {result}')
                return result
            
            print('TRAZA: Extracción fallida. No se obtuvieron valores.')
            return None

        # Función auxiliar para manejar múltiples intentos de VARIABLE_ALL
        def get_all_values_from_attempts(attempts: List[Dict[str, Any]]) -> Optional[str]:
            for mapping in attempts:
                if mapping.get('type') == 'VARIABLE_ALL':
                    # Intentamos la extracción
                    value = get_all_values(mapping)
                    # Si encontramos algo, lo devolvemos inmediatamente para no mezclar formatos
                    if value is not None and value:
                        return value
            return None

        # 4. Aplicar el mapeo
        for key, mapping in EXTRACTION_MAPPING.items():
            value = None
            key_lower = key.lower()
            
            if isinstance(mapping, list):
                if mapping and mapping[0].get('type') == 'VARIABLE_ALL':
                    # Es una lista de intentos para extracciones múltiples (MATRICULA, MODELO)
                    value = get_all_values_from_attempts(mapping)
                else:
                    # Es una lista de intentos para extracción simple (ej. FECHA)
                    for single_mapping in mapping:
                        value = get_value(single_mapping)
                        if value is not None:
                            break 
            
            elif isinstance(mapping, dict) and mapping.get('type') == 'VARIABLE_ALL':
                value = get_all_values(mapping)
                
            else:
                value = get_value(mapping)
            
            # --- LIMPIEZA POST-EXTRACCIÓN PARA MODELO ---
            if key.lower() == 'modelo' and value is not None:
                # 1. Eliminamos la parte de los kilómetros (" Ktms.:...")
                value = re.sub(r'\s+Ktms\.:.*$', '', str(value).strip())
                # 2. Limpiamos posibles dobles comas si la expresión regular falla en un caso
                value = value.replace(', ,', ',').replace(',,', ',').replace('  ', ' ').strip()
            
            if key =='NUM_FACTURA':
                if value == 'FACTURA':
                    mapping_v1F = {'type': 'VARIABLE', 'ref_text': 'Número', 'offset': -1, 'segment': 1}
                    num_factura = get_value(mapping_v1F)
                    value=num_factura
            # --- APLICAR LIMPIEZA NUMÉRICA A LOS TOTALES Y ASIGNAR FLOAT ---
            if key_lower in ['base', 'iva', 'importe', 'tasas']:
                cleaned_value = self._clean_and_convert_float(value)
                extracted_data[key_lower] = cleaned_value
                
            # --- ASIGNAR VALOR A CAMPOS NO NUMÉRICOS ---
            elif value is not None:
                extracted_data[key.lower()] = value
            else:
                extracted_data[key.lower()] = None

        return extracted_data