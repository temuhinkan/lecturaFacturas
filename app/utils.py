import re
# Importa la constante desde el nuevo fichero de configuración
from config import DEFAULT_VAT_RATE 

# Para que el extractor pueda importarla si está en otro fichero
VAT_RATE = DEFAULT_VAT_RATE 

# --- Constantes ---
MONTH_MAP = {
    'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04',
    'mayo': '05', 'junio': '06', 'julio': '07', 'agosto': '08',
    'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'
}

# --- Funciones de Ayuda (Comunes) ---

def extract_and_format_date(lineas):
    """
    Extracts a date from a line that might contain "Madrid Barajas, a DD Mes YYYY"
    and formats it to DD-MM-YYYY.
    """
    date_found = None
    date_regex = r'(?:^|\W)(?:a\s+)?(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})(?:$|\W)'

    for linea in lineas:
        match = re.search(date_regex, linea, re.IGNORECASE)
        if match:
            day, month_name, year = match.groups()
            month_name_lower = month_name.lower()
            
            if month_name_lower in MONTH_MAP:
                month_num = MONTH_MAP[month_name_lower]
                formatted_day = day.zfill(2)
                date_found = f"{formatted_day}-{month_num}-{year}"
                break
            else:
                print(f"⚠️ Warning: Unrecognized month name '{month_name}' found in line: '{linea}'")
    
    return date_found

# AÑADIDO: Función para extraer el importe numérico
def _extract_amount(amount_str):
    """
    Extrae un importe numérico de una cadena de texto (ej. "24,79€", "30.00").
    Maneja el formato europeo (coma como separador decimal).
    """
    if not amount_str:
        return None
    
    # Patrón: Busca un número que puede tener separadores de miles (punto) y decimales (coma)
    match = re.search(r'([+-]?\s*\d{1,3}(?:\.?\d{3})*(?:,\d+)?)\s*€?\b', amount_str.strip().replace(' ', ''))
    
    if match:
        numeric_str = match.group(1)
        # 1. Quitar separadores de miles (punto)
        numeric_str = numeric_str.replace('.', '')
        # 2. Reemplazar la coma decimal por punto decimal
        numeric_str = numeric_str.replace(',', '.')
        
        try:
            return float(numeric_str)
        except ValueError:
            return None
    return None

# AÑADIDO: Función para calcular la base imponible
def _calculate_base_from_total(total_amount, vat_rate):
    """
    Calcula la base imponible a partir del importe total y la tasa de IVA.
    """
    if total_amount is not None and vat_rate is not None and vat_rate > 0:
        return total_amount / (1 + vat_rate)
    return None

# AÑADIDO: Stub para evitar error de importación
def _extract_nif_cif(line):
    """
    Función placeholder/stub si no se usa.
    """
    return None
# ----------------------------------------------


def _extract_from_line(line, regex_pattern, group=1):
    """Helper to extract data using a regex from a single line."""
    match = re.search(regex_pattern, line, re.IGNORECASE)
    if match:
        return match.group(group)
    return None

def _extract_from_lines_with_keyword(lines, keyword_patterns, regex_pattern, group=1, look_ahead=0):
    """ Helper to find one of several keywords and extract data... """
    if not isinstance(keyword_patterns, list):
        keyword_patterns = [keyword_patterns]

    for i, line in enumerate(lines):
        line_lower = line.lower()
        for pattern in keyword_patterns:
            if pattern.lower() in line_lower:
                target_index = i + look_ahead
                if 0 <= target_index < len(lines):
                    target_line = lines[target_index]
                    return _extract_from_line(target_line, regex_pattern, group)
    return None

def calculate_total_and_vat(base_amount_str: str, vat_rate: float = DEFAULT_VAT_RATE):
    """
    Calculates the total amount and the VAT amount from the taxable base.
    Uses the DEFAULT_VAT_RATE from config.py if no rate is provided.
    """
    if not base_amount_str:
        return None, None 

    try:
        # 1. Preparación para la conversión numérica
        numeric_base_str = base_amount_str.replace('.', '').replace(',', '.')
        
        # 2. Conversión a número flotante
        base_amount = float(numeric_base_str)
        
        # 3. Cálculo del IVA y del importe total
        vat_amount = base_amount * vat_rate
        total_amount = base_amount + vat_amount
        
        # 4. Formateo de los resultados
        formatted_vat_amount = f"{vat_amount:.2f}".replace('.', ',')
        formatted_total_amount = f"{total_amount:.2f}".replace('.', ',')
        
        return formatted_total_amount, formatted_vat_amount
    
    except ValueError:
        print(f"⚠️ Warning: Could not calculate total and VAT for base amount '{base_amount_str}'. Invalid numeric format.")
        return None, None