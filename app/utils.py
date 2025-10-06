import re

# --- Constantes ---
VAT_RATE = 0.21

MONTH_MAP = {
    'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04',
    'mayo': '05', 'junio': '06', 'julio': '07', 'agosto': '08',
    'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'
}

# --- Funciones de Ayuda (Comunes) ---

def extract_and_format_date(lineas):
    """
    Extracts a date from a line that might contain "Madrid Barajas, a DD Mes晤"
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

def _extract_from_line(line, regex_pattern, group=1):
    """Helper to extract data using a regex from a single line."""
    match = re.search(regex_pattern, line, re.IGNORECASE)
    if match:
        return match.group(group)
    return None

def _extract_from_lines_with_keyword(lines, keyword_patterns, regex_pattern, group=1, look_ahead=0):
    """
    Helper to find one of several keywords and extract data from that line or a subsequent one.
    keyword_patterns can be a string or a list of strings/regex patterns.
    """
    if isinstance(keyword_patterns, str):
        keyword_patterns = [keyword_patterns]

    for i, line in enumerate(lines):
        for kp in keyword_patterns:
            if re.search(kp, line, re.IGNORECASE):
                target_line_idx = i + look_ahead
                if 0 <= target_line_idx < len(lines):
                    target_line = lines[target_line_idx]
                else:
                    target_line = line
                return _extract_from_line(target_line, regex_pattern, group)
    return None

def _extract_amount(line, is_stellantis=False):
    """
    Helper to extract an amount string (e.g., '1.234,56' or '71,00').
    Handles comma as a decimal separator and specific Stellantis sum.
    """
    values = re.findall(r'\d+(?:[.,]\d{3})*[.,]\d{2}', line)
    return values[-1] if values else None



def _extract_nif_cif(line):
    """
    Extracts a NIF/CIF from a line, handling common Spanish formats.
    Prioritizes formats starting with letters followed by digits.
    """
    # Pattern for CIFs like B12345678 or A-12345678 or B.123.456.7.A
    # This is more specific for the desired CIF format "B30378129"
    cif_specific_pattern = r'\b([A-Z][-\.]?\d{7,8}[A-Z]?)\b'
    match_specific_cif = re.search(cif_specific_pattern, line, re.IGNORECASE)
    if match_specific_cif:
        return match_specific_cif.group(1).replace('.', '').replace('-', '')

    # Pattern for DNI (8 digits + 1 letter, or with dots/hyphens)
    dni_pattern = r'(\d{8}[A-Z])|(\d{1,3}(?:\.\d{3}){2}-?[A-Z])'
    dni_match = re.search(dni_pattern, line, re.IGNORECASE)
    if dni_match:
        if dni_match.group(1):
            return dni_match.group(1)
        elif dni_match.group(2):
            return dni_match.group(2).replace('.', '').replace('-', '')

    # Fallback for other CIF patterns if the specific one doesn't match
    cif_with_separators_pattern = r'([A-Z][-\.]?\d{1,3}(?:[\.\-]?\d{3}){2,3}[A-Z]?)'
    cif_sep_match = re.search(cif_with_separators_pattern, line, re.IGNORECASE)
    if cif_sep_match:
        return cif_sep_match.group(1).replace('.', '').replace('-', '')

    cif_without_separators_pattern = r'([A-Z]{1,3}\d{7,8}[A-Z]?)'
    cif_no_sep_match = re.search(cif_without_separators_pattern, line, re.IGNORECASE)
    if cif_no_sep_match:
        return cif_no_sep_match.group(1)
        
    return None

def _calculate_base_from_total(total_amount_str, vat_rate=VAT_RATE):
    """
    Calculates the taxable base by removing VAT from the total amount.
    """
    if not total_amount_str:
        return None
    try:
        numeric_total_str = total_amount_str.replace(',', '.')
        total_amount = float(numeric_total_str)
        base_calc = total_amount / (1 + vat_rate)
        return f"{base_calc:.2f}".replace('.', ',')
    except ValueError:
        print(f"⚠️ Warning: Could not calculate base for total amount '{total_amount_str}'. Invalid numeric format.")
        return None
def _calculate_total_from_base(base_amount_str, vat_rate=VAT_RATE):
    
    if not base_amount_str:
        return None, None

    try:
        # 1. Preparación para la conversión numérica
        # Reemplazamos la coma por un punto para que float() pueda interpretar correctamente.
        numeric_base_str = base_amount_str.replace(',', '.')
        
        # 2. Conversión a número flotante
        base_amount = float(numeric_base_str)
        
        # 3. Cálculo del IVA y del importe total
        # Cantidad de IVA = Base Imponible * Tasa de IVA
        vat_amount = base_amount * vat_rate
        # Importe Total = Base Imponible + Cantidad de IVA
        total_amount = base_amount + vat_amount
        
        # 4. Formateo de los resultados
        # Formateamos ambos números a una cadena con dos decimales y volvemos a usar la coma.
        formatted_vat_amount = f"{vat_amount:.2f}".replace('.', ',')
        formatted_total_amount = f"{total_amount:.2f}".replace('.', ',')
        
        return formatted_total_amount
    
    except ValueError:
        # 5. Manejo de errores
        print(f"⚠️ Warning: Could not calculate VAT and total for base amount '{base_amount_str}'. Invalid numeric format.")
        return None, None
