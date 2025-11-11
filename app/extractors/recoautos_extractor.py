# 🚨 MAPPING SUGERIDO PARA main_extractor_gui.py
# Copie la siguiente línea y péguela en el diccionario EXTRACTION_MAPPING en main_extractor_gui.py:
#
# "nueva_clave": "extractors.nombre_archivo_extractor.RecoautosExtractor", 
#
# Ejemplo (si el archivo generado es 'recoautos_extractor.py'):
# "sumauto": "extractors.recoautos_extractor.RecoautosExtractor",

from typing import Dict, Any, List, Optional
import re
# La clase BaseInvoiceExtractor será INYECTADA en tiempo de ejecución (soluciona ImportError en main_extractor_gui.py).

# 🚨 EXTRACTION_MAPPING: Define la lógica de extracción.
# 'type': 'FIXED' (Fila Fija, línea absoluta 1-based), 'VARIABLE' (Variable, relativa a un texto), o 'FIXED_VALUE' (Valor Fijo, valor constante).
# 'segment': Posición de la palabra en la línea (1-based), o un rango (ej. "3-5").

    EXTRACTION_MAPPING: Dict[str, Dict[str, Any]] = {
        'TIPO': {'type': 'FIXED_VALUE', 'value': 'COMPRA'},
        'FECHA':  {'type': 'VARIABLE', 'ref_text': 'Fecha', 'offset': +2, 'segment': 1},
        'NUM_FACTURA': {'type': 'VARIABLE', 'ref_text': 'Factura Nº', 'offset': -3, 'segment': 1},
        'EMISOR': {'type': 'FIXED_VALUE', 'value': 'RECICLADOS AUTO4 SL'},
        'CIF_EMISOR': {'type': 'FIXED_VALUE', 'value': 'B40243719'},
        'CLIENTE': {'type': 'FIXED_VALUE', 'value': 'NEWSATELITE S.L'},
        'CIF': {'type': 'FIXED_VALUE', 'value': 'B85629020'},
        #'MODELO': {'type': 'VARIABLE', 'ref_text': 'Matrícula', 'offset': +1, 'segment': 2},
        #'MATRICULA': {'type': 'VARIABLE', 'ref_text': 'Modelo', 'offset': +1, 'segment': 2},
        # Lógica VARIABLE compatible para los totales:
        # BASE: 8 líneas arriba de 'Base Imponible'
        'BASE': {'type': 'VARIABLE', 'ref_text': 'TOTAL FACTURA', 'offset': -1, 'segment': 1},
        # IVA: 9 líneas arriba de 'Base Imponible'
        'IVA': {'type': 'VARIABLE', 'ref_text': 'IVA' , 'offset': +3, 'segment': 1},
        # IMPORTE: 10 líneas arriba de 'Base Imponible'
        'IMPORTE': {'type': 'VARIABLE', 'ref_text': 'TOTAL FACTURA', 'offset': +1, 'segment': 1},
    }

# 🚨 CORRECCIÓN CRÍTICA: Renombrar la clase a PincheteExtractor
# Asumimos que hereda de BaseInvoiceExtractor
class RecoautosExtractor:
    
    # Usamos *args y **kwargs para máxima compatibilidad con el __init__ de BaseInvoiceExtractor.
    def __init__(self, lines: List[str] = None, pdf_path: str = None, *args, **kwargs):
        # En el entorno real, esto llamaría a super().__init__(lines=lines, pdf_path=pdf_path, ...)
        pass

    def extract_data(self, lines: List[str]) -> Dict[str, Any]:
        
        extracted_data = {}
        
        # Función auxiliar para buscar línea de referencia (primera coincidencia)
        def find_reference_line(ref_text: str) -> Optional[int]:
            ref_text_lower = ref_text.lower()
            for i, line in enumerate(lines):
                # Buscamos la etiqueta de referencia
                if ref_text_lower in line.lower():
                    return i
            return None

        # Función auxiliar para obtener el valor
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
                return None
                
            return None

        # 4. Aplicar el mapeo
        for key, mapping in EXTRACTION_MAPPING.items():
            value = get_value(mapping)
            if key =='FECHA':
                print("FECHA",value)
                if value == 'NEW':
                    print("dentro cif emisor",value)
                    mapping_v1F = {'type': 'VARIABLE', 'ref_text': 'FECHA', 'offset': -3, 'segment': 1}
                    fecha = get_value(mapping_v1F)
                    value=fecha
            
            if value is not None:
                extracted_data[key.lower()] = value
            else:
                extracted_data[key.lower()] = None

        return extracted_data