
from typing import Dict, Any, List, Optional
import re
# 🚨 IMPORTACIÓN DE BASE INVOICE EXTRACTOR ELIMINADA. 
# La clase será inyectada en tiempo de ejecución.

# 🚨 EXTRACTION_MAPPING: Define la lógica de extracción.
# 'type': 'FIXED' (línea absoluta 1-based), 'VARIABLE' (relativa a un texto), o 'FIXED_VALUE' (valor constante).
# 'segment': Posición de la palabra en la línea (1-based).

EXTRACTION_MAPPING: Dict[str, Dict[str, Any]] = {
    'TIPO': {'type': 'FIXED_VALUE', 'value': 'COMPRA'},
    'FECHA': {'type': 'FIXED_VALUE', 'value': '29-07-2025'},
    'NUM_FACTURA': {'type': 'FIXED', 'segment': 1, 'line': 36},
    'EMISOR': {'type': 'FIXED', 'segment': 1, 'line': 64},
    'CLIENTE': {'type': 'FIXED_VALUE', 'value': 'NEW SATELITE, S.L.'},
    'CIF': {'type': 'FIXED_VALUE', 'value': 'B02819530'},
    'MODELO': {'type': 'FIXED', 'segment': 1, 'line': 14},
    'BASE': {'type': 'FIXED', 'segment': 1, 'line': 50},
    'IVA': {'type': 'FIXED', 'segment': 1, 'line': 52},
    'IMPORTE': {'type': 'FIXED', 'segment': 1, 'line': 54},

}

class GeneratedExtractor(BaseInvoiceExtractor):
    
    # FIX: Asegura que el constructor no requiera argumentos, previniendo el error.
    def __init__(self):
        try:
            super().__init__()
        except TypeError:
             # Si BaseInvoiceExtractor no tiene __init__ o requiere argumentos que no tenemos, ignoramos.
             pass

    def extract_data(self, lines: List[str]) -> Dict[str, Any]:
        
        extracted_data = {}
        
        # Función auxiliar para buscar línea de referencia (primera coincidencia)
        def find_reference_line(ref_text: str) -> Optional[int]:
            ref_text_lower = ref_text.lower()
            for i, line in enumerate(lines):
                if ref_text_lower in line.lower():
                    return i
            return None

        # Función auxiliar para obtener el valor
        def get_value(mapping: Dict[str, Any]) -> Optional[str]:
            
            # 1. Caso FIXED_VALUE (valor constante, ej. Emisor, Tipo)
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
            segment_index_0based = mapping['segment'] - 1
            
            try:
                line_segments = re.split(r'\s+', lines[line_index].strip())
                line_segments = [seg for seg in line_segments if seg]
                
                if segment_index_0based < len(line_segments):
                    return line_segments[segment_index_0based].strip()
            except Exception:
                return None
                
            return None

        # 4. Aplicar el mapeo
        for key, mapping in EXTRACTION_MAPPING.items():
            value = get_value(mapping)
            if value is not None:
                extracted_data[key.lower()] = value
            else:
                extracted_data[key.lower()] = None

        return extracted_data
