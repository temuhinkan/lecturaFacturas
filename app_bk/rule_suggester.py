import database # Necesario para acceder a las reglas existentes
from typing import Optional, Dict, Any, List
import re

# --- 1. Generación de REGEX Básica por Tipo de Dato ---

def generate_basic_regex_for_value(value: str, field_name: str) -> str:
    """
    Genera una REGEX básica basada en el campo y el valor.
    Esto es crucial para que la heurística compare "tipos" de datos.
    """
    # Limpiamos el valor para evitar errores
    value = str(value).strip()

    if field_name == 'fecha':
        # Patrón para fechas (dd/mm/aaaa, dd-mm-aaaa, etc.)
        return r'\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}'
    
    elif field_name in ['base', 'iva', 'importe', 'tasas']:
        # Patrón para valores monetarios/numéricos (con o sin separador de miles y con coma o punto decimal)
        # Ejemplo: 1.234,56 o 1234.56
        return r'[\d\s\.,]+'
    
    elif field_name in ['cif', 'nif', 'vat']:
        # Patrón para identificadores (letras y números)
        return r'[A-Z0-9]{4,}' 
    
    else:
        # Para otros campos (texto, emisor, etc.), buscamos el valor literal, escapando
        # caracteres especiales para que sea una búsqueda exacta del valor.
        return re.escape(value)


# --- 2. Lógica de Sugerencia de Regla (Heurística) ---

def suggest_best_rule(target_field: str, selected_value: str) -> Optional[Dict[str, Any]]:
    """
    Analiza las reglas existentes para el campo (en la BBDD) y sugiere la mejor plantilla
    para el valor seleccionado, reutilizando anclas (ref_text) conocidas.
    """
    # 1. Generar la REGEX básica del valor seleccionado para identificar su "tipo"
    base_value_regex = generate_basic_regex_for_value(selected_value, target_field)
    
    try:
        # 2. Obtener todas las reglas existentes para el campo (ASUMIMOS la implementación en database.py)
        all_rules = database.fetch_all_rules_for_field(target_field)
        
        if all_rules:
            # 3. Iterar y buscar la regla más compatible (Heurística)
            for rule_list in all_rules:
                # all_rules puede devolver reglas agrupadas, tomamos la primera de cada grupo
                if not rule_list: continue 
                existing_rule = rule_list[0]
                
                # Criterio Heurístico: Buscamos una regla que ya tenga un ANCLA (ref_text)
                # y que su patrón de extracción ('value_regex') coincida con el tipo de dato
                # (base_value_regex).
                
                existing_value_regex = existing_rule.get('value_regex', '')
                
                # Reutilizar si encontramos una regla con ancla que coincide en el patrón de valor
                if existing_rule.get('ref_text') and existing_value_regex == base_value_regex:
                    
                    # Sugerir la regla existente, pero con el nuevo valor de ejemplo
                    suggested_rule = existing_rule.copy()
                    suggested_rule['value'] = selected_value
                    
                    print(f"DEBUG SUGGEST: Coincidencia fuerte encontrada para '{target_field}'. Reutilizando ancla: '{suggested_rule['ref_text']}'.")
                    return suggested_rule

        # 4. Si no se encuentra una coincidencia fuerte, generamos una plantilla genérica.
        
        # Plantilla básica: el valor es el texto y la REGEX del valor, pero pedimos al usuario
        # que seleccione también el ancla (ref_text).
        return {
            # Sugerimos el valor como 'ref_text' inicial para que el usuario pueda ajustarlo.
            'ref_text': selected_value, 
            'ref_regex': re.escape(selected_value), # Búsqueda exacta del texto seleccionado
            'value': selected_value,
            'value_regex': base_value_regex, # La REGEX genérica del tipo de dato
            'distance_lines': 0, # Mismo segmento/línea
            'distance_segment': 1 # Siguiente segmento
        }
        
    except Exception as e:
        print(f"Error en suggest_best_rule: {e}")
        # En caso de error de BBDD o lógica, devolver la plantilla genérica
        return {
            'ref_text': '',
            'ref_regex': '',
            'value': selected_value,
            'value_regex': base_value_regex,
            'distance_lines': 0, 
            'distance_segment': 1
        }