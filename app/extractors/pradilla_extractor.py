# 🚨 MAPPING SUGERIDO PARA main_extractor_gui.py
# Copie la siguiente línea y péguela en el diccionario EXTRACTION_MAPPING en main_extractor_gui.py:
#
# "nueva_clave": "extractors.pradilla_extractor.PradillaExtractor", 
#
# Ejemplo (si el archivo generado es 'pradilla_extractor.py'):
# "autolux": "extractors.pradilla_extractor.PradillaExtractor",

from typing import Dict, Any, List, Optional
import re
from config import DEFAULT_VAT_RATE 
import math
from typing import Tuple
# La clase BaseInvoiceExtractor será INYECTADA en tiempo de ejecución (soluciona ImportError en main_extractor_gui.py).

# 🚨 EXTRACTION_MAPPING: Define la lógica de extracción.
# 'type': 'FIXED' (Fila Fija, línea absoluta 1-based), 'VARIABLE' (Variable, relativa a un texto), o 'FIXED_VALUE' (Valor Fijo, valor constante).
# 'segment': Posición de la palabra en la línea (1-based), o un rango (ej. "3-5").

EXTRACTION_MAPPING: Dict[str, Dict[str, Any]] = {
    'TIPO': {'type': 'FIXED_VALUE', 'value': 'COMPRA'},
    'FECHA':[{'type': 'VARIABLE', 'ref_text': 'FECHA', 'offset': 6, 'segment': 1},
             {'type': 'VARIABLE', 'ref_text': 'FECHA', 'offset': 5, 'segment': 1},
             {'type': 'VARIABLE', 'ref_text': 'FECHA', 'offset': 3, 'segment': 1},
             {'type': 'VARIABLE', 'ref_text': 'FECHA', 'offset': 0, 'segment': 2}
             ],
    'NUM_FACTURA': [{'type': 'VARIABLE', 'ref_text': 'NºFACTURA', 'offset': 5,'segment': 1},
                    {'type': 'VARIABLE', 'ref_text': 'NºFACTURA', 'offset': 6,'segment': 1},
                    {'type': 'VARIABLE', 'ref_text': 'Nº FACTURA', 'offset': 6,'segment': 1},
                    {'type': 'VARIABLE', 'ref_text': 'NºFACTURA', 'offset': 4,'segment': 1},
                    {'type': 'VARIABLE', 'ref_text': 'N*FACTURA', 'offset': 0,'segment': 2},
                    {'type': 'VARIABLE', 'ref_text': 'N FACTURA', 'offset': 0,'segment': 3},
                    {'type': 'VARIABLE', 'ref_text': 'N%FACTURA', 'offset': 0,'segment': 2}
                    
                    ],
    'EMISOR': {'type': 'FIXED_VALUE', 'value': 'GESTORIA PRADILLA, S.L.'},
    'CIF_EMISOR': {'type': 'FIXED_VALUE', 'value': 'B-80481369'},
    'CLIENTE': {'type': 'FIXED_VALUE', 'value': 'NEW SATELITE SL'},
    'CIF': {'type': 'FIXED_VALUE', 'value': 'B-80481369'},
    'MATRICULA': [{'type': 'VARIABLE', 'ref_text': 'Matrícula', 'offset': 6,'segment': 1},
                  {'type': 'VARIABLE', 'ref_text': 'Matrícula', 'offset': -3,'segment': 1},
                  {'type': 'VARIABLE', 'ref_text': 'Matrícula', 'offset': 9,'segment': 1},
                  {'type': 'VARIABLE', 'ref_text': 'Matrícula', 'offset': 0,'segment': 2},
                  {'type': 'VARIABLE', 'ref_text': 'Matrícula', 'offset': 0,'segment': "2-3"}
                  ],
    'BASE': [{'type': 'VARIABLE',  'ref_text': 'BASEl.V.A.', 'offset': 4,'segment': '1-3'},
             {'type': 'VARIABLE',  'ref_text': 'BASEI.V.A.', 'offset': 4,'segment': "1-3"},
             {'type': 'VARIABLE',  'ref_text': 'BASEl.V.A.', 'offset': 6,'segment': '1-2'},
             {'type': 'VARIABLE',  'ref_text': 'BASE l. V.A.', 'offset': 6,'segment': '1-2'},
             {'type': 'VARIABLE',  'ref_text': 'BASE 1.V.A.', 'offset': 3,'segment': 1},
             {'type': 'VARIABLE',  'ref_text': '% 1VA', 'offset': 2,'segment': '1-3'},
             {'type': 'VARIABLE',  'ref_text': 'BASE l.V.A.', 'offset': 6,'segment': '1-3'},
             {'type': 'VARIABLE',  'ref_text': '21, 00 % 1VA', 'offset': 4,'segment': 1},
             {'type': 'VARIABLE',  'ref_text': 'BASE l.V.A.', 'offset': 4,'segment': '1-3'},
             {'type': 'VARIABLE',  'ref_text': 'BASE l.V.A.', 'offset': 6,'segment': '1-2'},
             {'type': 'VARIABLE',  'ref_text': 'BASE l.V.A.', 'offset': 1,'segment': "1-2"},
             {'type': 'VARIABLE',  'ref_text': 'BASE l.V.A.', 'offset': 1,'segment': 1},
             {'type': 'VARIABLE',  'ref_text': 'TOTAL APAGAR', 'offset': -2,'segment': 1},
             
             ],
    'IVA': [{'type': 'VARIABLE',  'ref_text': '21 ,00 %1VA', 'offset': 6,'segment': '1-2'},
            {'type': 'VARIABLE',  'ref_text': '21 , 00 %1VA', 'offset': 3,'segment': 1},
            {'type': 'VARIABLE',  'ref_text': '21,00 %1VA', 'offset': 3,'segment': "1-2"},
            {'type': 'VARIABLE',  'ref_text': '%1VA', 'offset': 5,'segment': '1-2'},
            {'type': 'VARIABLE',  'ref_text': '21, 00 %1VA', 'offset': 2,'segment': 1},
            {'type': 'VARIABLE',  'ref_text': '21, 00 %1VA', 'offset': 1,'segment': 1},
            {'type': 'VARIABLE',  'ref_text': '%1 VA', 'offset': 3,'segment': "1-2"},
            {'type': 'VARIABLE',  'ref_text': '21, 00 % 1VA', 'offset': 5,'segment': "1"},
            {'type': 'VARIABLE',  'ref_text': '% 1VA', 'offset': 1,'segment': "1-2"},
            {'type': 'VARIABLE',  'ref_text': '% 1VA', 'offset': 3,'segment': 1},
            
            ],
    'IMPORTE': [{'type': 'VARIABLE','ref_text': 'TOTAL APAGAR', 'offset': 1 ,'segment': 3},
                {'type': 'VARIABLE','ref_text': 'TOTAL A PAGAR', 'offset': 1,'segment': 2},
                {'type': 'VARIABLE','ref_text': 'TOTAL A PAGAR', 'offset': 1,'segment': 1}],
    'TASAS': [{'type': 'VARIABLE', 'ref_text': 'TOTAL A PAGAR', 'offset': -1,'segment': '1-3'},
              {'type': 'VARIABLE', 'ref_text': 'TOTAL A PAGAR', 'offset': -2,'segment': '1-2'},
              {'type': 'VARIABLE', 'ref_text': 'TOTAL A PAGAR', 'offset': -1,'segment': '1-2'},
              {'type': 'VARIABLE', 'ref_text': 'TOTAL A PAGAR', 'offset': -1,'segment': 1}, 
              {'type': 'VARIABLE', 'ref_text': 'SUruDOS', 'offset': -3,'segment': 1}],

}

class PradillaExtractor(BaseInvoiceExtractor):
    
    # 🚨 CORRECCIÓN: ACEPTAR explícitamente lines y pdf_path.
    def __init__(self, lines: List[str] = None, pdf_path: str = None, *args, **kwargs):
        try:
             # Intentamos llamar al padre con los argumentos necesarios
             super().__init__(lines=lines, pdf_path=pdf_path, *args, **kwargs)
        except TypeError:
             try:
                 super().__init__()
             except:
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
    def is_only_text_tolerant(self, value: Optional[str]) -> bool:
        """
        Verifica si la cadena NO contiene NINGÚN dígito numérico (0-9).
        Permite letras, espacios, puntos, comas, acentos y símbolos comunes.
        """
        if value is None or not value.strip():
            return False
            
        input_str = str(value)
        
        # 1. Verificar si contiene al menos una letra (para descartar solo símbolos)
        # Patrón: Busca cualquier letra del alfabeto (A-Z, a-z)
        if not re.search(r'[a-zA-Z]', input_str):
            # Si no hay letras, comprobamos si la cadena es solo puntuación/símbolos.
            # Si no hay letras, por lo general no queremos considerarla "texto".
            return False
            
        # 2. Verificar que NO contenga NINGÚN dígito numérico.
        # Patrón: r'\d' busca cualquier dígito numérico (0-9).
        if re.search(r'\d', input_str):
            return False # ❌ Contiene al menos un número.
        else:
            # ✅ No contiene números y sí contiene al menos una letra.
            return True
        
        
        # --- FIN FUNCIÓN DE LIMPIEZA ---
    # Asume que DEFAULT_VAT_RATE es accesible (está importado en config.py y utils.py)


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
    
    def validar_fecha(self,fecha: str) -> bool:
        """
        Valida una fecha con formato DD/MM/AAAA o DD-MM-AA, etc.

        Permite:
        - DD/MM/AAAA o DD-MM-AAAA (4 dígitos para el año)
        - DD/MM/AA o DD-MM-AA (2 dígitos para el año)
        - Separador: '/' o '-'
        """
        # Expresión regular:
        # ^(0[1-9]|[12][0-9]|3[01]) -> Día (01-31)
        # [/-]                      -> Separador: '/' o '-'
        # (0[1-9]|1[0-2])           -> Mes (01-12)
        # [/-]                      -> Separador: '/' o '-'
        # ([0-9]{2}|[0-9]{4})$      -> Año (2 o 4 dígitos)
        
        # Esta regex comprueba el *formato*, pero no valida si el día 31 existe en el mes 02 (febrero).
        patron = r"^(0[1-9]|[12][0-9]|3[01])[/-](0[1-9]|1[0-2])[/-]([0-9]{2}|[0-9]{4})$"
        
        return re.match(patron, fecha) is not None

    def validar_numero_factura(self,numero_factura: str) -> bool:
        """
        Valida si una cadena es un número de factura de exactamente 8 dígitos.
        """
        # Expresión regular:
        # ^[0-9]{8}$ -> Inicia y termina con 8 dígitos numéricos exactos
        patron = r"^[0-9]{8}$"
        
        # También se podría hacer sin re: return len(numero_factura) == 8 and numero_factura.isdigit()
        return re.match(patron, numero_factura) is not None

    def check_importes(self, base: Optional[float], iva: Optional[float], importe: Optional[float], tasas :Optional[float]) -> Tuple[float,float,float,str, str, str,]:
        """
        Gestiona valores faltantes (None) y verifica la consistencia entre Base, IVA, Tasas e Importe Total.
        Devuelve los tres valores como floats (recalculados) y strings formateados.
        """
        
        # 1. FIX: Asegurar que 'tasas' es 0.00 si es None, para evitar el error 'NoneType'
        tasas = tasas if tasas is not None else 0.00 # 🚨 SOLUCIÓN AL ERROR
        
        print("valores iniciales",base,iva,importe,tasas)
        TOLERANCE = 0.01 
        missing_count = sum(v is None for v in [base, iva, importe])
        # --- Lógica de Recálculo (Prioriza el cálculo si falta 1 valor) ---
        print("missing_count",missing_count)
        if missing_count == 1:
            if importe is None and base is not None and iva is not None:
                # Caso 1: Falta Importe Total
                importe = base + iva + tasas
            elif iva is None and base is not None and importe is not None and importe >= base:
                # Caso 2: Falta IVA
                iva = importe - base - tasas
            elif base is None and iva is not None and importe is not None and importe >= iva:
                # Caso 3: Falta Base
                base = importe - iva - tasas
                
        elif missing_count == 2:
            print("entro aqqui")
            # Caso 4: Falta Base e IVA (Calculamos usando Importe, Tasas y la tasa por defecto)
            if importe is not None and importe > 0:
                print("entro aqqui1")
                # Importe sin tasas = Importe Total - Tasas
                importe_sin_tasas = importe - tasas 
                
                if importe_sin_tasas > 0:
                    # CORRECCIÓN DE LA FÓRMULA: Base = (Importe sin tasas) / (1 + Tasa_IVA)
                    base = importe_sin_tasas / (1 + DEFAULT_VAT_RATE) 
                    iva = importe_sin_tasas - base
                else:
                    base = 0.00
                    iva = 0.00
            elif iva is None and importe is None and base is not None and base > 0 and tasas is not None and tasas > 0:
                iva = base * DEFAULT_VAT_RATE
                importe = base + iva + tasas
                
        # --- Verificación de Consistencia (Si todos están presentes) ---
        elif missing_count == 0:
            # CORRECCIÓN: La verificación debe incluir las tasas: base + iva + tasas vs importe
            if not math.isclose(base + iva + tasas, importe, abs_tol=TOLERANCE):
                # Inconsistencia: Recalculamos el Importe Total para asegurar la coherencia
                print(f"⚠️ Importes inconsistentes ({base} + {iva} + {tasas} != {importe}). Recalculando Importe.")
                #importe = base + iva + tasas
                iva= importe - base - tasas

        # --- 3. Limpieza final y Formato ---
        
        # Asignar 0.00 a cualquier valor que siga siendo None (base/iva, no aplica a importe/tasas en esta lógica)
        base = base if base is not None else 0.00
        iva = iva if iva is not None else 0.00
        importe = importe if importe is not None else 0.00
        
        def format_float_to_string(num):
            # Asegura el redondeo y la coma como separador decimal
            return f"{round(num, 2):.2f}".replace('.', ',')

        base_str = format_float_to_string(base)
        iva_str = format_float_to_string(iva)
        importe_str = format_float_to_string(importe)

        # 🚨 DEVOLVER: (Float_Base, Float_IVA, Float_Importe), (Str_Base, Str_IVA, Str_Importe)
        return base, iva, importe, base_str, iva_str, importe_str

        
    def extract_data(self, lines: List[str]) -> Dict[str, Any]:
        
        extracted_data = {}
        valor_iva=None
        valor_base=None
        valor_importe=None
        valor_tasas=None
        # Función auxiliar para buscar línea de referencia (primera coincidencia)
        def find_reference_line(ref_text: str) -> Optional[int]:
            ref_text_lower = ref_text.lower()
            for i, line in enumerate(lines):
                if line and ref_text_lower in line.lower():
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
            
            # 🚨 INICIO DE CORRECCIÓN: EVITAR 'NoneType' object has no attribute 'strip'
            line_content = lines[line_index]
            if line_content is None:
                return None
            # 🚨 FIN DE CORRECCIÓN
            
            try:
                # Usamos line_content, que está garantizado que no es None.
                line_segments = re.split(r'\s+', line_content.strip())
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
        VALIDATORS = {
            "NUM_FACTURA": self.validar_numero_factura,
            "FECHA": self.validar_fecha,
            # ¡CORRECCIÓN CRUCIAL AQUI! Usar validar_matricula para MATRICULA
            "MATRICULA": self.validar_matricula, 
            }
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
                    
                    # 4. Procesamiento post-extracción (SOLO si se encontró un valor)
                    pattern_A = r"^([0-9.,]+)\s*,\s*(.*)$"
                    pattern_B = r"^([0-9.,]+)\s*,\s*(.+)$"
                    if value is not None:
                        pattern_text = r'[a-zA-ZáéíóúÁÉÍÓÚñÑ]'
                        if (bool(re.search(pattern_text, str(value)))):
                            match_A = re.match(pattern_A, value)
                            match_B = re.match(pattern_B, value)
                            if match_A:
                                numeric_part = match_A.group(1).strip()
                                value=numeric_part
                            elif match_B:
                                numeric_part = match_B.group(1).strip()
                                value=numeric_part
                            elif self.is_only_text_tolerant(value):
                                mapping_v2FE = {'type': 'VARIABLE', 'ref_text': 'BASE l.V.A.', 'offset': 1, 'segment': '1-2'}
                                value = get_value(mapping_v2FE)
                    print(value)
                    
                    if value is not None:
                        # ¡Valor encontrado! Salimos del bucle interno
                        break 
            else:
                # Si 'mapping' es un diccionario simple (el comportamiento anterior)
                value = get_value(mapping)
            key_lower = key.lower()
            print(key.lower(),value)
            if key_lower in ['base', 'iva', 'importe', 'tasas']:
                # Asignamos el valor FLOAT limpio directamente
                cleaned_value = self._clean_and_convert_float(value)
                if key_lower == 'base':
                    valor_base=cleaned_value
                elif key_lower == 'iva':
                    valor_iva=cleaned_value
                elif key_lower == 'importe':
                    valor_importe=cleaned_value
                elif key_lower == 'tasas':
                    valor_tasas=cleaned_value
                extracted_data[key_lower] = cleaned_value
                
            # --- ASIGNAR VALOR A CAMPOS NO NUMÉRICOS ---
            elif value is not None:
                # Solo asignamos el valor de texto original para campos no numéricos
                extracted_data[key.lower()] = value
            else:
                extracted_data[key.lower()] = None

        valor_base_num, valor_iva_num, valor_importe_num, base_str, iva_str, importe_str=self.check_importes(valor_base,valor_iva,valor_importe,valor_tasas)
        extracted_data['base'] = base_str
        extracted_data['iva'] = iva_str
        extracted_data['importe'] = importe_str
        return extracted_data