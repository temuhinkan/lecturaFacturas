from typing import Dict, Any, List, Optional
import re
# La clase BaseInvoiceExtractor será INYECTADA en tiempo de ejecución (soluciona ImportError en main_extractor_gui.py).

# 🚨 EXTRACTION_MAPPING: Define la lógica de extracción.
# 'type': 'FIXED' (Fila Fija, línea absoluta 1-based), 'VARIABLE' (Variable, relativa a un texto), o 'FIXED_VALUE' (Valor Fijo, valor constante).
# 'segment': Posición de la palabra en la línea (1-based), o un rango (ej. "3-5").

EXTRACTION_MAPPING: Dict[str, Dict[str, Any]] = {
    'TIPO': {'type': 'FIXED_VALUE', 'value': 'COMPRA'},
    # CORREGIDO: Line 9 (Fecha:) -> Line 7 (08/04/2025). Offset -2
    'FECHA':  {'type': 'VARIABLE', 'ref_text': 'Fecha:', 'offset': -2, 'segment': 1},
    # CORRECTO: Line 16 (Factura nº:) -> Line 6 (F00489/2025). Offset -10
    'NUM_FACTURA': {'type': 'VARIABLE', 'ref_text': 'Factura nº:', 'offset': -10, 'segment': 1},
    'EMISOR': {'type': 'FIXED_VALUE', 'value': 'PEDRO GARRIDO RODRÍGUEZ'},
    'CIF_EMISOR': {'type': 'FIXED_VALUE', 'value': '75.388.055-N'},
    'CLIENTE': {'type': 'FIXED_VALUE', 'value': 'NEWSATELITE SL'},
    'CIF': {'type': 'FIXED_VALUE', 'value': 'B85629020'},
    # Lógica VARIABLE para los totales (AJUSTADA AL LOG):
    # BASE: Line 27 (BASE IMPONIBLE) -> Line 29 (30,00€). Offset +2
    'BASE': {'type': 'VARIABLE', 'ref_text': 'BASE IMPONIBLE', 'offset': +2, 'segment': 1},
    # IVA: Line 34 (IVA (21,00%)) -> Line 35 (6,30€). Usamos 'IVA (' para evitar coincidir con otra línea de 'IVA'. Offset +1
    'IVA': {'type': 'VARIABLE', 'ref_text': 'IVA (', 'offset': +1, 'segment': 1},
    # IMPORTE: Line 28 (TOTAL) -> Line 31 (36,30€). Offset +3
    'IMPORTE': {'type': 'VARIABLE', 'ref_text': 'BASE IMPONIBLE', 'offset': +4, 'segment': 1},
}

class PoyoExtractor:
    
    # Usamos *args y **kwargs para máxima compatibilidad con el __init__ de BaseInvoiceExtractor.
    def __init__(self, lines: List[str] = None, pdf_path: str = None, *args, **kwargs):
        # En el entorno real, esto llamaría a super().__init__(lines=lines, pdf_path=pdf_path, ...)
        pass

    # --- NUEVA FUNCIÓN DE LIMPIEZA ---
    def _clean_and_convert_float(self, value: Optional[str]) -> Optional[float]:
        """Limpia cadenas para obtener un float (maneja puntos, comas y símbolos de moneda)."""
        if value is None or str(value).strip() == '':
            return None
        
        cleaned_value = str(value).strip()
        
        # 1. Eliminar símbolos de moneda y caracteres no numéricos irrelevantes
        # Esto elimina el '€' de '30,00€'
        cleaned_value = cleaned_value.replace('€', '').replace('$', '').replace('%', '').replace(':', '').replace('(', '').replace(')', '').replace('[', '').replace(']', '').replace('?', '').replace('!', '').replace(' ', '')
        
        # 2. Manejar separadores de miles y decimales comunes en español
        # Si contiene coma (,) y punto (.)
        if ',' in cleaned_value and '.' in cleaned_value:
            # Asumir que el punto es separador de miles y la coma es decimal (1.234,56 -> 1234.56)
            cleaned_value = cleaned_value.replace('.', '').replace(',', '.')
        # Si solo contiene coma
        elif ',' in cleaned_value:
            # Asumir que la coma es separador decimal (1234,56 -> 1234.56)
            cleaned_value = cleaned_value.replace(',', '.')

        try:
            return float(cleaned_value)
        except ValueError:
            return None
    # --- FIN FUNCIÓN DE LIMPIEZA ---


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
            
            key_lower = key.lower()

            # --- APLICAR LIMPIEZA NUMÉRICA A LOS TOTALES ---
            if key_lower in ['base', 'iva', 'importe']:
                cleaned_value = self._clean_and_convert_float(value)
                extracted_data[key_lower] = cleaned_value
            # --- FIN LIMPIEZA NUMÉRICA ---
            
            elif value is not None:
                extracted_data[key_lower] = value
            else:
                extracted_data[key_lower] = None

        return extracted_data