# 🚨 MAPPING SUGERIDO PARA main_extractor_gui.py
# Copie la siguiente línea y péguela en el diccionario EXTRACTION_MAPPING en main_extractor_gui.py:
#
# "nueva_clave": "extractors.nombre_archivo_extractor.BoxesExtractor", 
#
# Ejemplo (si el archivo generado es 'boxes_extractor.py'):
# "pinchete": "extractors.boxes_extractor.BoxesExtractor",

from typing import Dict, Any, List, Optional
import re
# La clase BaseInvoiceExtractor será INYECTADA en tiempo de ejecución (soluciona ImportError en main_extractor_gui.py).

# 🚨 EXTRACTION_MAPPING: Define la lógica de extracción.
# 'type': 'FIXED' (Fila Fija, línea absoluta 1-based), 'VARIABLE' (Variable, relativa a un texto), o 'FIXED_VALUE' (Valor Fijo, valor constante).
# 'segment': Posición de la palabra en la línea (1-based), o un rango (ej. "3-5").

import database
EXTRACTOR_KEY = "boxes"

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


# 🚨 CORRECCIÓN CRÍTICA: Renombrar la clase a BoxesExtractor
# Asumimos que hereda de BaseInvoiceExtractor
class BoxesExtractor:
    
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
    
    def validar_matricula(self,matricula: str) -> bool:
        """
        Valida una matrícula con el formato: 4 números, 3 consonantes (puede tener guion).

        Formato esperado: NNNN-CCC o NNNNCCC
        N = Dígito (0-9)
        C = Consonante (B, C, D, F, G, H, J, K, L, M, N, Ñ, P, Q, R, S, T, V, W, X, Y, Z)
        """
        # Expresión regular:
        # ^[0-9]{4} -> Inicia con 4 dígitos
        # -?        -> Cero o un guion medio
        # [BCDFGHJKLMNÑPQRSTVWXYZ]{3}$ -> Finaliza con 3 letras que sean solo consonantes (mayúsculas)

        # Nota: Se incluyen las consonantes más comunes en español. Se asume mayúsculas.
        patron = r"^[0-9]{4}-?[BCDFGHJKLMNÑPQRSTVWXYZ]{3}$"
        
        return re.match(patron, matricula.upper()) is not None
    
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
            value = None
            if isinstance(mapping, list):
                # Si 'mapping' es una lista, iteramos sobre los intentos
                for single_mapping in mapping:
                    print(f"Intentando extraer {key} con: {single_mapping}")
            
                    # Obtener el valor
                    temp_value = get_value(single_mapping)
                    print("temp_value",temp_value)
                    # 2. Verificar la validación del campo si el valor no es None
                    is_valid = True
                    if key in VALIDATORS:
                        if temp_value is not None:
                            # Validar el valor obtenido
                            if not VALIDATORS[key](temp_value):
                                is_valid = False
                                print(f"Valor '{temp_value}' para {key} falló la validación.") 
                        
                        print("is_valid",is_valid)
                    # 3. Si es válido (o si la clave no requiere validación), lo guardamos y salimos del bucle.
                    if is_valid and temp_value is not None:
                       value = temp_value
                       print(f"Éxito en {key} con el valor: {value}")
                       break # ¡Valor encontrado! Salimos del bucle interno
            else:
                # Si 'mapping' es un diccionario simple (el comportamiento anterior)
                value = get_value(mapping)
            key_lower = key.lower()
            VALIDATORS = {
            "MATRICULA": self.validar_matricula, 
            }
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