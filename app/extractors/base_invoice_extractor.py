# Contenido COMPLETO para el archivo: extractors/base_invoice_extractor.py

import re
from typing import Tuple, List, Optional, Any, Dict

# Se asume que estos imports están disponibles o se manejan en el entorno
# from utils import _clean_and_convert_float 

# --- Mapeo Genérico para Fallback ---
BASE_EXTRACTION_MAPPING: Dict[str, Any] = {
    'TIPO': {'type': 'FIXED_VALUE', 'value': 'COMPRA'},
    'FECHA': [
        {'type': 'VARIABLE', 'ref_text': 'Fecha', 'offset': 0, 'segment': 2},
        {'type': 'VARIABLE', 'ref_text': 'Fecha de venta', 'offset': 1, 'segment': 1},
        {'type': 'VARIABLE', 'ref_text': 'Fecha:', 'offset': 1, 'segment': 1},
        {'type': 'VARIABLE', 'ref_text': 'Data/Hora', 'offset': 1, 'segment': 1},
        {'type': 'VARIABLE', 'ref_text': 'edido', 'offset': 0, 'segment': 4},
        {'type': 'FIXED', 'line': 1, 'segment': '2-99'}
    ],
    'NUM_FACTURA': [{'type': 'VARIABLE', 'ref_text': 'FACTURA', 'offset': 0, 'segment': 2},
                    {'type': 'VARIABLE', 'ref_text': '[FACTURA', 'offset': 1, 'segment': 1}],

    'EMISOR': [{'type': 'VARIABLE', 'ref_text': '"NIF:', 'offset': 0, 'segment': 2},
               {'type': 'VARIABLE', 'ref_text': 'NIF', 'offset': 1, 'segment': "2-4"},
              {'type': 'FIXED_VALUE', 'value': 'Emisor Desconocido'}] ,
    'CIF_EMISOR': {'type': 'VARIABLE', 'ref_text': 'CIF', 'offset': 0, 'segment': 2},
    'CLIENTE': {'type': 'FIXED_VALUE', 'value': 'NEWSATELITE S.L'},
    'CIF': {'type': 'FIXED_VALUE', 'value': 'B85629020'},
    'MODELO': {'type': 'VARIABLE', 'ref_text': 'Modelo', 'offset': 0, 'segment': 2},
    'MATRICULA': {'type': 'VARIABLE', 'ref_text': 'Matrícula', 'offset': 0, 'segment': 2},
    # Importes (se busca 'TOTAL' como valor genérico de prueba)
    'IMPORTE': [{'type': 'VARIABLE', 'ref_text': 'TOTAL', 'offset': 0, 'segment': 2},
                {'type': 'VARIABLE', 'ref_text': 'TOTAL', 'offset': 2, 'segment': 2},
                {'type': 'VARIABLE', 'ref_text': 'Total', 'offset': 1, 'segment': 1},
                {'type': 'VARIABLE', 'ref_text': 'Importe total EUR', 'offset': 1, 'segment': 1}],
    # Valores por defecto para fallback si la búsqueda falla
    'BASE': [{'type': 'VARIABLE', 'ref_text': 'BASE', 'offset': 0, 'segment': 2},
             {'type': 'VARIABLE', 'ref_text': 'EXT', 'offset': -1, 'segment': 1},
             {'type': 'VARIABLE', 'ref_text': 'TOTAL', 'offset': 0, 'segment': 3},
             {'type': 'VARIABLE', 'ref_text': 'Subtotal', 'offset': 1, 'segment': 1},
             {'type': 'VARIABLE', 'ref_text': 'Valor neto EUR', 'offset': 2, 'segment': 1}],

    'IVA': [{'type': 'VARIABLE', 'ref_text': 'IVA', 'offset': 0, 'segment': 2},
            {'type': 'VARIABLE', 'ref_text': 'TOTAL', 'offset': 1, 'segment': 1},
            {'type': 'VARIABLE', 'ref_text': 'IVA', 'offset': 1, 'segment': 1},
            {'type': 'VARIABLE', 'ref_text': 'IVA', 'offset': 3, 'segment': 1}],
    'TASAS': {'type': 'VARIABLE', 'ref_text': 'SUPLIDOS', 'offset': 0, 'segment': 2},
}

class BaseInvoiceExtractor:
    """
    Clase base para todos los extractores. 
    Contiene la lógica de extracción genérica (fallback) con trazas de depuración.
    """
    # Atributos estáticos
    EMISOR_CIF = 'B00000000'
    EMISOR_NAME = 'BaseInvoiceExtractor'
    
    def __init__(self, lines: List[str], pdf_path: str = None, *args, **kwargs):
        self.lines = lines
        self.pdf_path = pdf_path
        self.cif = self.EMISOR_CIF
        
        try:
            import re
            self.re = re
        except ImportError:
            self.re = None

    def is_valid(self):
        return True

    # --- FUNCIONES AUXILIARES (Lógica de Mapeo) ---
    def _clean_and_convert_float(self, value: Optional[str]) -> Optional[float]:
        """Limpia cadenas para obtener un float."""
        if value is None or str(value).strip() == '':
            return None
        # ... (Lógica de limpieza y conversión a float, omitida por brevedad) ...
        cleaned_value = str(value).strip()
        cleaned_value = cleaned_value.replace('€', '').replace('$', '').replace('%', '').replace(':', '').replace('(', '').replace(')', '').replace('[', '').replace(']', '').replace('?', '').replace('!', '').replace(' ', '').replace('EUROS','')
        temp_value = cleaned_value
        
        # Lógica de separador de miles/decimales
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
            
    def _find_reference_line(self, ref_text: str) -> Optional[int]:
        """Busca línea de referencia (primera coincidencia)."""
        ref_text_lower = ref_text.lower()
        print(f"DEBUG FALLBACK: Buscando referencia '{ref_text}'...")
        for i, line in enumerate(self.lines):
            if ref_text_lower in line.lower():
                print(f"DEBUG FALLBACK: Referencia '{ref_text}' encontrada en línea {i}.")
                return i
        print(f"DEBUG FALLBACK: Referencia '{ref_text}' NO encontrada.")
        return None
        
    def _get_value(self, mapping: Dict[str, Any]) -> Optional[str]:
        """Obtiene un solo valor (FIXED, VARIABLE o FIXED_VALUE) usando el mapeo."""
        
        if mapping.get('type') == 'FIXED_VALUE':
            print(f"DEBUG FALLBACK: Aplicando FIXED_VALUE para el valor fijo '{mapping.get('value')}'.")
            return str(mapping.get('value'))
            
        line_index = None
        
        # (Lógica para obtener line_index a partir de FIXED o VARIABLE, omitida por brevedad) ...
        if mapping.get('type') == 'FIXED':
            print(f"DEBUG FALLBACK: Aplicando mapeo FIXED (línea absoluta).")
            abs_line_1based = mapping.get('line')
            if abs_line_1based is not None and abs_line_1based > 0:
                line_index = abs_line_1based - 1 
            
        elif mapping.get('type') == 'VARIABLE':
            ref_text = mapping.get('ref_text', '')
            offset = mapping.get('offset', 0)
            
            ref_index = self._find_reference_line(ref_text)
            
            if ref_index is not None:
                line_index = ref_index + offset
                print(f"DEBUG FALLBACK: Mapeo VARIABLE. Ref. index: {ref_index}, Offset: {offset}, Línea final: {line_index}.")
        
        if line_index is None or not (0 <= line_index < len(self.lines)):
            return None
            
        segment_input = mapping.get('segment')
        if segment_input is None: return None
        
        try:
            if self.re:
                line_segments = self.re.split(r'\s+', self.lines[line_index].strip())
            else:
                line_segments = self.lines[line_index].strip().split()

            line_segments = [seg for seg in line_segments if seg]
            
            value = None
            
            if self.re and isinstance(segment_input, str) and self.re.match(r'^\d+-\d+$', segment_input):
                start_s, end_s = segment_input.split('-')
                start_idx = int(start_s) - 1
                end_idx = int(end_s)
                
                if 0 <= start_idx < end_idx and end_idx <= len(line_segments):
                    value = ' '.join(line_segments[start_idx:end_idx]).strip()
            
            else:
                segment_index_0based = int(segment_input) - 1
                if segment_index_0based >= 0 and segment_index_0based < len(line_segments):
                    value = line_segments[segment_index_0based].strip()
                    
            if value:
                print(f"DEBUG FALLBACK: Valor extraído de segmento '{segment_input}': '{value[:50]}...'.")
                return value
                    
        except Exception:
            pass
            
        return None
        
    def _get_all_values(self, mapping: Dict[str, Any]) -> Optional[str]:
        # MOCKUP simple para VARIABLE_ALL
        return self._get_value({k: v for k, v in mapping.items() if k != 'type'})

    def _get_all_values_from_attempts(self, attempts: List[Dict[str, Any]]) -> Optional[str]:
        print(f"DEBUG FALLBACK: Intentando extracción con múltiples mapeos.")
        for mapping in attempts:
            value = self._get_value(mapping)
            if value is not None and value:
                return value
        return None
        
    def _find_date_fallback(self) -> Optional[str]:
        """
        Intenta encontrar la fecha de forma genérica en el documento 
        si las reglas de mapeo fallaron.
        """
        print(f"DEBUG FALLBACK: Intentando búsqueda de fecha genérica en todo el documento...")
        try:
            # Reutilizamos la lógica robusta de utils.extract_and_format_date
            date_value = extract_and_format_date(self.lines)
            if date_value:
                print(f"DEBUG FALLBACK: Fecha genérica ENCONTRADA: {date_value}")
                return date_value
            else:
                print(f"DEBUG FALLBACK: Búsqueda de fecha genérica FALLIDA.")
                return None
        except Exception as e:
            print(f"DEBUG FALLBACK: Error en búsqueda genérica de fecha: {e}")
            return None

    # --- MÉTODOS DE EXTRACCIÓN PRINCIPALES ---

    def extract_data(self, lines: List[str]) -> Dict[str, Any]:
        """Implementa la extracción basada en mapeo genérico."""
        extracted_data = {}
        print("\nDEBUG FALLBACK: --- INICIANDO EXTRACCIÓN GENÉRICA (BaseInvoiceExtractor) ---")

        # 4. Aplicar el mapeo genérico
        for key, mapping in BASE_EXTRACTION_MAPPING.items():
            
            value = None
            key_lower = key.lower()
            
            if mapping is None:
                extracted_data[key_lower] = None
                continue
                
            print(f"\nDEBUG FALLBACK: Procesando campo '{key}'...")
                
            # Intento de extracción por reglas de mapeo
            if isinstance(mapping, list):
                if mapping and mapping[0].get('type') == 'VARIABLE_ALL':
                    value = self._get_all_values_from_attempts(mapping)
                else:
                    for single_mapping in mapping:
                        value = self._get_value(single_mapping)
                        if value is not None:
                            break 
            
            elif isinstance(mapping, dict):
                 value = self._get_value(mapping)

            # APLICAR FALLBACK SOLO A LA FECHA
            if key == 'FECHA' and (value is None or value.strip() == ''):
                value = self._find_date_fallback()

            
            # --- LIMPIEZA NUMÉRICA Y ASIGNAR FLOAT ---
            if key_lower in ['base', 'iva', 'importe', 'tasas']:
                cleaned_value = self._clean_and_convert_float(value)
                extracted_data[key_lower] = cleaned_value
                print(f"DEBUG FALLBACK: Resultado FINAL para '{key}': {cleaned_value} (FLOAT).")
                
            # --- ASIGNAR VALOR A CAMPOS NO NUMÉRICOS ---
            elif value is not None:
                extracted_data[key.lower()] = value
                print(f"DEBUG FALLBACK: Resultado FINAL para '{key}': '{value}'.")
            else:
                extracted_data[key.lower()] = None
                print(f"DEBUG FALLBACK: Resultado FINAL para '{key}': None.")

        return extracted_data

    def extract_all(self) -> Tuple[Any, ...]:
        """Método de fallback llamado por logic.py para obtener la tupla de 13 campos."""
        data_dict = self.extract_data(self.lines)

        # Mapeo de dict a tupla (Tupla de 13 elementos)
        return (
            data_dict.get('tipo'), data_dict.get('fecha'), data_dict.get('num_factura'),
            data_dict.get('emisor', self.EMISOR_NAME), data_dict.get('cif_emisor', self.EMISOR_CIF), 
            data_dict.get('cliente'), data_dict.get('cif'), data_dict.get('modelo'), 
            data_dict.get('matricula'), data_dict.get('importe'), 
            data_dict.get('base'), data_dict.get('iva'), data_dict.get('tasas')
        )