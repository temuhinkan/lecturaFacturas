
# 🚨 MAPPING SUGERIDO PARA main_extractor_gui.py
# Copie la siguiente línea y péguela en el diccionario EXTRACTION_MAPPING en main_extractor_gui.py:
#
# "nueva_clave": "extractors.nombre_archivo_extractor.GeneratedExtractor", 
#
# Ejemplo (si el archivo generado es 'autolux_extractor.py'):
# "autolux": "extractors.autolux_extractor.GeneratedExtractor",

from typing import Dict, Any, List, Optional
import re
# La clase BaseInvoiceExtractor será INYECTADA en tiempo de ejecución (soluciona ImportError en main_extractor_gui.py).

# 🚨 EXTRACTION_MAPPING: Define la lógica de extracción.
# 'type': 'FIXED' (Fila Fija, línea absoluta 1-based), 'VARIABLE' (Variable, relativa a un texto), o 'FIXED_VALUE' (Valor Fijo, valor constante).
# 'segment': Posición de la palabra en la línea (1-based), o un rango (ej. "3-5").

EXTRACTION_MAPPING: Dict[str, Dict[str, Any]] = {
    'TIPO': {'type': 'FIXED_VALUE', 'value': 'Venta'},
    'FECHA': {'type': 'FIXED', 'segment': 1, 'line': 8},
    'EMISOR': {'type': 'FIXED_VALUE', 'value': 'New Satélite, S.L.'},
    'CLIENTE': {'type': 'FIXED', 'segment': 1, 'line': 11},
    'CIF': {'type': 'FIXED_VALUE', 'value': 'B85629020'},
    'MODELO': {'type': 'FIXED', 'segment': 1, 'line': 22},
    'MATRICULA': {'type': 'FIXED', 'segment': 1, 'line': 25},
    'BASE': {'type': 'FIXED', 'segment': 2, 'line': 28},
    'IMPORTE': {'type': 'FIXED', 'segment': 3, 'line': 30},

}

class GeneratedExtractor(BaseInvoiceExtractor):
    
    # 🚨 CORRECCIÓN: ACEPTAR explícitamente lines y pdf_path.
    # Usamos *args y **kwargs para máxima compatibilidad con el __init__ de BaseInvoiceExtractor.
    def __init__(self, lines: List[str] = None, pdf_path: str = None, *args, **kwargs):
        # El constructor GeneratedExtractor no necesita llamar a super().__init__ 
        # si BaseInvoiceExtractor maneja su propia inicialización o si el extractor 
        # generado solo necesita la función extract_data. 
        # Si BaseInvoiceExtractor TIENE lógica en __init__, DEBERÍAMOS LLAMARLA.
        try:
             # Intentamos llamar al padre con los argumentos necesarios
             super().__init__(lines=lines, pdf_path=pdf_path, *args, **kwargs)
        except TypeError:
             # Si el padre tiene un constructor simple, lo llamamos sin argumentos 
             # (o simplemente no hacemos nada si el padre es un stub vacío)
             try:
                 super().__init__()
             except:
                 pass
        
        # En el extractor generado, toda la lógica de extracción se realiza en extract_data, 
        # por lo que no necesitamos almacenar lines aquí.

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
            segment_input = mapping['segment'] # Puede ser int o str de rango ("3-5")
            
            try:
                line_segments = re.split(r'\s+', lines[line_index].strip())
                line_segments = [seg for seg in line_segments if seg]
                
                # Check for range support
                if isinstance(segment_input, str) and re.match(r'^\d+-\d+$', segment_input):
                    start_s, end_s = segment_input.split('-')
                    start_idx = int(start_s) - 1 # 0-based start
                    end_idx = int(end_s) # 0-based exclusive end
                    
                    if 0 <= start_idx < end_idx and end_idx <= len(line_segments):
                        return ' '.join(line_segments[start_idx:end_idx]).strip()
                
                # Simple segment index (assuming it's an integer)
                segment_index_0based = int(segment_input) - 1
                
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
