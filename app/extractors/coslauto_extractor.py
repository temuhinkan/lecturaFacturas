# 🚨 MAPPING SUGERIDO PARA main_extractor_gui.py
# Copie la siguiente línea y péguela en el diccionario EXTRACTION_MAPPING en main_extractor_gui.py:
#
# "nueva_clave": "extractors.nombre_archivo_extractor.CoslautoExtractor", 
#
# Ejemplo (si el archivo generado es 'coslauto_extractor.py'):
# "pinchete": "extractors.coslauto_extractor.CoslautoExtractor",

from typing import Dict, Any, List, Optional
import re

# ----------------------------------------------------
# 🟢 CORRECCIÓN DE IMPORTACIÓN PARA ARCHIVOS EN CARPETA SUPERIOR
import sys
import os
# Añade el directorio padre (..) a las rutas de búsqueda de módulos
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# ----------------------------------------------------

# Ahora la importación de utils debería funcionar
# La clase BaseInvoiceExtractor será INYECTADA en tiempo de ejecución (soluciona ImportError en main_extractor_gui.py).

# 🚨 EXTRACTION_MAPPING: Define la lógica de extracción.
# 'type': 'FIXED' (Fila Fija, línea absoluta 1-based), 'VARIABLE' (Variable, relativa a un texto), o 'FIXED_VALUE' (Valor Fijo, valor constante).
# 'segment': Posición de la palabra en la línea (1-based), o un rango (ej. "3-5").

EXTRACTION_MAPPING: Dict[str, Dict[str, Any]] = {
    'TIPO': {'type': 'FIXED_VALUE', 'value': 'COMPRA'},
    #'FECHA':  {'type': 'VARIABLE', 'ref_text': 'FECHA:', 'offset': 0, 'segment': 2},
    #'NUM_FACTURA':  {'type': 'VARIABLE', 'ref_text': 'Nº.', 'offset': +1, 'segment': 1},
    'EMISOR': {'type': 'FIXED_VALUE', 'value': 'COSLAUTO, SLU.'},
    'CIF_EMISOR': {'type': 'FIXED_VALUE', 'value': 'B87532248'},
    'CLIENTE': {'type': 'FIXED_VALUE', 'value': 'NEWSATELITE S.L'},
    'CIF': {'type': 'FIXED_VALUE', 'value': 'B85629020'},
    #'MODELO': {'type': 'VARIABLE', 'ref_text': 'MODELO', 'offset': +7, 'segment': 1},
    #'MATRICULA': {'type': 'VARIABLE', 'ref_text': 'MATRÍCULA', 'offset': +7, 'segment': 1},
    # Lógica VARIABLE compatible para los totales:
    # BASE: 8 líneas arriba de 'Base Imponible'
   # 'BASE': {'type': 'VARIABLE', 'ref_text': 'TOTAL BRUTO', 'offset': +3, 'segment': 1},
    # IVA: 9 líneas arriba de 'Base Imponible'
    #'IVA': {'type': 'VARIABLE', 'ref_text': 'IMPORTE IVA', 'offset': +5, 'segment': 1},
    # IMPORTE: 10 líneas arriba de 'Base Imponible'
    'IMPORTE': {'type': 'VARIABLE', 'ref_text': '€', 'offset': 0, 'segment': 1},
}

# 🚨 CORRECCIÓN CRÍTICA: Renombrar la clase a CoslautoExtractor
# Asumimos que hereda de BaseInvoiceExtractor
class CoslautoExtractor:
    
           
    # Usamos *args y **kwargs para máxima compatibilidad con el __init__ de BaseInvoiceExtractor.
    def __init__(self, lines: List[str] = None, pdf_path: str = None, *args, **kwargs):
        # En el entorno real, esto llamaría a super().__init__(lines=lines, pdf_path=pdf_path, ...)
        pass

    def calculate_base_and_vat_from_total(self,total_amount_str: str):
    
        if not total_amount_str:
            return None, None 

        try:
            # ...
            numeric_total_str = total_amount_str.replace('.', '').replace(',', '.')
            total_amount = float(numeric_total_str)
            
            # 🟢 CRÍTICO: Corregir 0,21 a 0.21 (sintaxis de Python)
            base_amount = total_amount / (1 + 0.21) 
            
            # Importe del IVA = Total - Base
            vat_amount = total_amount - base_amount
            # ...
            
            formatted_base_amount = f"{base_amount:.2f}".replace('.', ',')
            formatted_vat_amount = f"{vat_amount:.2f}".replace('.', ',')
            
            return formatted_base_amount, formatted_vat_amount

        except ValueError:
            return None, None
        except Exception:
            return None, None

        except ValueError:
            # Ocurre si la cadena no se puede convertir a float
            return None, None
        except Exception:
            # Maneja cualquier otro error
            return None, None

    # --- NUEVA FUNCIÓN DE LIMPIEZA ---
    def _clean_and_convert_float(self, value: Optional[str]) -> Optional[float]:
        """Limpia cadenas para obtener un float (maneja puntos, comas y símbolos de moneda)."""
        if value is None or str(value).strip() == '':
            return None
        
        cleaned_value = str(value).strip()
        
        # 1. Eliminar símbolos de moneda y caracteres no numéricos irrelevantes
        # Esto elimina el '€' de '30,00€'
        cleaned_value = cleaned_value.replace('€', '').replace('$', '').replace('%', '').replace(':', '').replace('(', '').replace(')', '').replace('[', '').replace(']', '').replace('?', '').replace('!', '').replace(' ', '').replace('EUROS','')
        
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

       # ------------------------------------------------------------------
        # 🟢 CAMBIO 2: LÓGICA CONDICIONAL PARA NUM_FACTURA
        # ------------------------------------------------------------------
        num_factura = None
        fecha = None
        ref_text_fac = 'Cargo'
        ref_text_fec = 'FECHA'
        segment = 1
        
        # 1. Intentar la primera regla: offset +1
        mapping_v1F = {'type': 'VARIABLE', 'ref_text': ref_text_fac, 'offset': +1, 'segment': segment}
        num_factura = get_value(mapping_v1F)
        print("num_factura",num_factura)
        if not num_factura.startswith("CA"):
                num_factura = None
        
        # 2. Si no se encuentra, intentar la segunda regla: offset +3
        if num_factura is None:
            mapping_v2F = {'type': 'VARIABLE', 'ref_text': ref_text_fac, 'offset': +3, 'segment': segment}
            num_factura = get_value(mapping_v2F)
            if not num_factura.startswith("CA"):
                num_factura = None
        if num_factura is None:
            mapping_v3F = {'type': 'VARIABLE', 'ref_text': ref_text_fac, 'offset': +4, 'segment': segment}
            num_factura = get_value(mapping_v3F)
        
        extracted_data['num_factura'] = num_factura

        mapping_v1FE = {'type': 'VARIABLE', 'ref_text': ref_text_fec, 'offset': +2, 'segment': segment}
        fecha = get_value(mapping_v1FE)
        if fecha is not None:
            # Asegúrate de que la cadena tenga al menos un carácter antes de acceder a [0]
            if fecha and not fecha[0].isdigit():
                fecha = None
        # 2. Si no se encuentra, intentar la segunda regla: offset +3
        if fecha is None:
            mapping_v2FE = {'type': 'VARIABLE', 'ref_text': ref_text_fec, 'offset': +5, 'segment': segment}
            fecha = get_value(mapping_v2FE)
            
        extracted_data['fecha'] = fecha
        # ------------------------------------------------------------------


        # 4. Aplicar el mapeo para el resto de campos (no se procesa NUM_FACTURA)
        for key, mapping in EXTRACTION_MAPPING.items():
            value = get_value(mapping)
            key_lower = key.lower()
            if key == 'IMPORTE':
                base,iva = self.calculate_base_and_vat_from_total(value)
                print("base",base,"iva",iva)
                extracted_data['base'] = base
                extracted_data['iva'] = iva
            # --- APLICAR LIMPIEZA NUMÉRICA A LOS TOTALES Y ASIGNAR FLOAT ---
            if key_lower in ['importe', 'tasas']:
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