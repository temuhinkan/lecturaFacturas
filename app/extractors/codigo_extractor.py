# 🚨 MAPPING SUGERIDO PARA main_extractor_gui.py
# Copie la siguiente línea y péguela en el diccionario EXTRACTION_MAPPING en main_extractor_gui.py:
#
# "nueva_clave": "extractors.nombre_archivo_extractor.CodigoExtractor", 
#
# Ejemplo (si el archivo generado es 'codigo_extractor.py'):
# "codigo": "extractors.codigo_extractor.CodigoExtractor",

from typing import Dict, Any, List, Optional
import re
# La clase BaseInvoiceExtractor será INYECTADA en tiempo de ejecución (soluciona ImportError en main_extractor_gui.py).

# 🚨 EXTRACTION_MAPPING: Define la lógica de extracción.
# 'type': 'FIXED' (Fila Fija, línea absoluta 1-based), 'VARIABLE' (Variable, relativa a un texto), o 'FIXED_VALUE' (Valor Fijo, valor constante).
# 'segment': Posición de la palabra en la línea (1-based), o un rango (ej. "3-5").

EXTRACTION_MAPPING: Dict[str, Dict[str, Any]] = {
    'TIPO': {'type': 'FIXED_VALUE', 'value': 'COMPRA'},
    'FECHA':  {'type': 'VARIABLE', 'ref_text': 'Fecha', 'offset': 2, 'segment': "1-3"},
    'NUM_FACTURA':  {'type': 'VARIABLE', 'ref_text': 'Numero Fra', 'offset': +2, 'segment': 1},
    'EMISOR': {'type': 'FIXED_VALUE', 'value': 'CODIGO AUTO MADRID, S. L.'},
    'CIF_EMISOR': {'type': 'FIXED_VALUE', 'value': 'B·84777481'},
    'CLIENTE': {'type': 'FIXED_VALUE', 'value': 'NEWSATELITE S.L'},
    'CIF': {'type': 'FIXED_VALUE', 'value': 'B85629020'},
    #'MODELO': {'type': 'VARIABLE', 'ref_text': 'MODELO', 'offset': +7, 'segment': 1},
    #'MATRICULA': {'type': 'VARIABLE', 'ref_text': 'MATRÍCULA', 'offset': +7, 'segment': 1},
    # Lógica VARIABLE compatible para los totales:
    # BASE: 8 líneas arriba de 'Base Imponible'
    'BASE': {'type': 'VARIABLE', 'ref_text': 'Suma Neto', 'offset': -2, 'segment': 1},
    # IVA: 9 líneas arriba de 'Base Imponible'
    'IVA': {'type': 'VARIABLE', 'ref_text': 'Total IVA', 'offset': +4, 'segment': 1},
    # IMPORTE: 10 líneas arriba de 'Base Imponible'
    'IMPORTE': {'type': 'VARIABLE', 'ref_text': 'Tod91', 'offset': -2   , 'segment': 1},
}

# 🚨 CORRECCIÓN CRÍTICA: Renombrar la clase a CodigoExtractor
# Asumimos que hereda de BaseInvoiceExtractor
class CodigoExtractor:
    
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
        cleaned_value = cleaned_value.replace('€', '').replace('$', '').replace('%', '').replace(':', '').replace('(', '').replace(')', '').replace('[', '').replace(']', '').replace('?', '').replace('!', '').replace(' ', '').replace('EUROS','')
        
        # 2. Manejar separadores de miles y decimales comunes en español
        temp_value = cleaned_value
        
        # 🚨 CORRECCIÓN DEL BUG DE ESCALA: Nos aseguramos de que el resultado final solo use DOT como decimal.
        # Si hay una coma, la convertimos a punto, y si hay puntos antes de eso (miles), los eliminamos.
        
        # CASO 1: Formato Español (1.234,56 -> 1234.56)
        if '.' in temp_value and ',' in temp_value and temp_value.rfind('.') < temp_value.rfind(','):
            temp_value = temp_value.replace('.', '') # Quita el punto (separador de miles)
            temp_value = temp_value.replace(',', '.') # Cambia la coma a punto (decimal)
            
        # CASO 2: Solo Coma (247,93 -> 247.93)
        elif ',' in temp_value:
            temp_value = temp_value.replace(',', '.')
            
        # CASO 3: Solo Punto (247.93) - Ya está en formato correcto, no hacer nada.
        
        # Limpiamos el valor final
        cleaned_value = temp_value

        try:
            # 🚨 CORRECCIÓN DEL PRINT: Se usaba una sintaxis incorrecta, se corrige a f-string.
            # print("cleaned_value", cleaned_value) 
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
            
            # --- APLICAR LIMPIEZA NUMÉRICA A LOS TOTALES Y ASIGNAR FLOAT ---
            if key_lower in ['base', 'iva', 'importe', 'tasas']:
                # Asignamos el valor FLOAT limpio directamente
                cleaned_value = self._clean_and_convert_float(value)
                extracted_data[key_lower] = cleaned_value
                
            # --- ASIGNAR VALOR A CAMPOS NO NUMÉRICOS ---
            elif value is not None:
                # Solo asignamos el valor de texto original para campos no numéricos
                extracted_data[key.lower()] = value
            else:
                extracted_data[key.lower()] = None

        return extracted_data


