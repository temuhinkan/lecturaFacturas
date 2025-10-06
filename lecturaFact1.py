import os
import re
import csv
import PyPDF2
import argparse

# --- Helper Functions for Common Patterns ---
vat_rate=0.21

MONTH_MAP = {
    'enero': '01',
    'febrero': '02',
    'marzo': '03',
    'abril': '04',
    'mayo': '05',
    'junio': '06',
    'julio': '07',
    'agosto': '08',
    'septiembre': '09',
    'octubre': '10',
    'noviembre': '11',
    'diciembre': '12'
}

# --- Corrected extract_and_format_date function ---
def extract_and_format_date(lineas):
    """
    Extracts a date from a line that might contain "Madrid Barajas, a DD Mes YYYY"
    and formats it to DD-MM-YYYY.
    """
    date_found = None
    # Regex to capture Day, Month Name, and Year
    # It looks for "a" (optional), space, Day (1 or 2 digits), space, Month Name (text), space, Year (4 digits)
    # The (?:a\s+)? makes 'a ' optional.
    # We allow more general preceding text before the day to be robust.
    date_regex = r'(?:^|\W)(?:a\s+)?(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})(?:$|\W)'

    for linea in lineas:
        match = re.search(date_regex, linea, re.IGNORECASE)
        if match:
            # group(1) is day, group(2) is month_name, group(3) is year
            day, month_name, year = match.groups()
            
            # Normalize month name to lowercase for mapping
            month_name_lower = month_name.lower()
            
            if month_name_lower in MONTH_MAP:
                month_num = MONTH_MAP[month_name_lower]
                # Format day to ensure two digits if it's single (e.g., '6' becomes '06')
                formatted_day = day.zfill(2)
                
                date_found = f"{formatted_day}-{month_num}-{year}"
                break # Stop after finding the first date
            else:
                # Optional: print a warning if a month name isn't recognized
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
    Helper to find one of several keywords and extract data from that line or a subsequent line.
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
                    target_line = line # Fallback to current line if look_ahead is out of bounds

                return _extract_from_line(target_line, regex_pattern, group)
    return None

def _extract_amount(line, is_stellantis=False):
    """
    Helper to extract an amount string (e.g., '1.234,56' or '71,00').
    Handles comma as decimal separator and Stellantis-specific sum.
    """
    # More flexible regex to capture numbers that end with ',XX'
    # It looks for one or more digits, optionally followed by (dot and three digits) zero or more times,
    # then a comma and two digits. 
    values = re.findall(r'\d+(?:[.,]\d{3})*[.,]\d{2}', line)
    if is_stellantis and len(values) >= 2:
        try:
            # Convert to dot-decimal for calculation, then back to comma-decimal for output
            val1 = float(values[0].replace('.', '').replace(',', '.'))
            val2 = float(values[1].replace('.', '').replace(',', '.'))
            return str(f"{val1 + val2:.2f}").replace('.', ',')
        except ValueError:
            pass # Fallback to default if conversion fails

    # Take the last found value as it's often the total
    return values[-1] if values else None


def _extract_nif_cif(line):
    """
    Extracts NIF/CIF from a line, handling common Spanish formats.
    It's been updated to be more flexible for DNI-like numbers with dots/hyphens.
    """
    # Pattern for DNI: 8 digits, 1 letter (optionally with dots and hyphen for readability)
    dni_pattern = r'(\d{1,3}(?:\.\d{3}){2}-?[A-Z])|(\d{8}[A-Z])'

    # Pattern for NIF/CIFs with common separators like B-92.329.663
    # This regex ensures the structure: Letter + optional separator + 1-3 digits + (optional separator + 3 digits) repeated 2-3 times + optional trailing letter
    cif_with_separators_pattern = r'([A-Z][-\.]?\d{1,3}(?:[\.\-]?\d{3}){2,3}[A-Z]?)'

    # Pattern for NIF/CIFs without separators like A87527800, ESN0040262H
    # Allows 1 to 3 leading letters, 7 or 8 digits, and an optional trailing letter
    cif_without_separators_pattern = r'([A-Z]{1,3}\d{7,8}[A-Z]?)'


    # First, try to find the DNI-like pattern
    dni_match = re.search(dni_pattern, line, re.IGNORECASE)
    if dni_match:
        if dni_match.group(1):
            cleaned_dni = dni_match.group(1).replace('.', '').replace('-', '')
            return cleaned_dni
        elif dni_match.group(2):
            return dni_match.group(2)

    # Then, try to find CIFs with separators (e.g., B-92.329.663)
    cif_sep_match = re.search(cif_with_separators_pattern, line, re.IGNORECASE)
    if cif_sep_match:
        cleaned_cif = cif_sep_match.group(1).replace('.', '').replace('-', '')
        return cleaned_cif

    # Finally, try to find CIFs without separators (e.g., A87527800)
    cif_no_sep_match = re.search(cif_without_separators_pattern, line, re.IGNORECASE)
    if cif_no_sep_match:
        return cif_no_sep_match.group(1) # No need to clean if no separators are allowed in pattern

    return None

#def _extract_nif_cif(line):
#    """
#    Extracts NIF/CIF from a line, handling multiple common Spanish formats.
#   It first tries to find patterns preceded by common keywords (NIF, CIF).
#    If no match is found, it then tries to find the NIF/CIF patterns anywhere in the line.
#    """
#    # Define the NIF/CIF patterns with increased flexibility
#    # This pattern is now more generalized for Spanish NIF/CIFs.
#    # It allows:
#    # - 1 to 3 leading letters (e.g., A, ES, ESN)
#    # - 7 to 8 digits (e.g., 4900012, 87527800)
#    # - An optional trailing letter (e.g., H, Z)
#    # This covers R4900012H, A87527800, 12345678A, and ESN0040262H
#    nif_cif_patterns = r'[A-Z]{1,3}\d{7,8}[A-Z]?'
#
#    # Attempt 1: Search for NIF/CIF with a preceding keyword
#    # The prefix pattern was already correct after our last fix.
#    # We use a non-greedy quantifier (.*?) to match the minimum characters between prefix and NIF if needed,
#    # and then capture the NIF using the flexible pattern.
#    cif_match = re.search(
#        r'(?:NIF\s*\(número\s*de\s*identificación\s*fiscal\):\s*|NIF:\s*|CIF:\s*|C\.I\.F\.:?\s*)' # Prefixes
#        r'(' + nif_cif_patterns + r')', # Capturing group for the NIF/CIF pattern
#        line,
#        re.IGNORECASE
#    )
#
#   if cif_match:
#        return cif_match.group(1)
    
    # Attempt 2: If no keyword prefix is found, try to find the NIF/CIF pattern anywhere in the line.
    # We add word boundaries \b to prevent matching parts of other words if possible,
    # but be careful as the format itself can be tricky.
    cif_match = re.search(r'\b(' + nif_cif_patterns + r')\b', line, re.IGNORECASE)
    
    # If the above fails (e.g., NIF is stuck to other text), try without strict word boundaries
    if not cif_match:
        cif_match = re.search(r'(' + nif_cif_patterns + r')', line, re.IGNORECASE)

    if cif_match:
        return cif_match.group(1)
        
    return None

def _calculate_base_from_total(total_amount_str, vat_rate=0.21):
    """
    Calculates the base amount (base imponible) by removing VAT from the total amount.
    Handles comma as decimal separator in the input string.
    
    Args:
        total_amount_str (str): The total amount string (e.g., '1.234,56' or '123.45').
        vat_rate (float): The VAT rate as a decimal (e.g., 0.21 for 21%).
        
    Returns:
        str: The calculated base amount as a string (e.g., '1.020,30'),
             formatted to two decimal places with a comma as the decimal separator,
             or None if the conversion fails.
    """
    if not total_amount_str:
        return None
    try:
        # Clean the string: remove thousands separators (.), replace decimal comma (,) with dot (.)
        numeric_total_str = total_amount_str.replace(',', '.')
        total_amount = float(numeric_total_str)
        
        # Calculate base (Base = Total / (1 + VAT Rate))
        base_calc = total_amount / (1 + vat_rate)
        
        # Format the result back to a string with two decimal places and comma as decimal separator
        return f"{base_calc:.2f}".replace('.', ',')
        
    except ValueError:
        print(f"⚠️ Warning: Could not calculate base for total amount '{total_amount_str}'. Invalid number format.")
        return None
# --- Specific Extraction Functions for Each Invoice Type ---

def extract_autodoc_data(lineas):
    tipo = "COMPRA"
    cliente = "AUTODOC SE"
    numero_factura = _extract_from_lines_with_keyword(lineas, r'Número de factura:', r'(\d{6,})')
    fecha = _extract_from_lines_with_keyword(lineas, r'Fecha de factura:', r'(\d{2}[\./]\d{2}[\./]\d{4})')
    cif = None # Autodoc's CIF not consistently found near a keyword, try general NIF/CIF search
    modelo = None
    matricula = None
    importe = None
    base_imponible = None # <--- ADD THIS LINE

    for i, linea in enumerate(lineas):
        # Look for the amount
        if 'Importe total bruto' in linea and i + 1 < len(lineas):
            importe = _extract_amount(lineas[i+1])
            base_imponible = _calculate_base_from_total(importe, vat_rate)
        # Try to extract CIF from any line with NIF/CIF keyword
        if cif is None: # Only try if CIF hasn't been found yet
            extracted_cif = _extract_nif_cif(linea)
            if extracted_cif:
                cif = extracted_cif

    return tipo, fecha, numero_factura, cliente, cif, modelo, matricula, importe, base_imponible

def extract_stellantis_data(lineas):
    tipo = "COMPRA"
    cliente = "PPCR MADRID"
    numero_factura = _extract_from_lines_with_keyword(lineas, r'N° Factura', r'(\d{6,})')
    fecha = _extract_from_lines_with_keyword(lineas, r'(\d{2}/\d{2}/\d{4})', r'(\d{2}/\d{2}/\d{4})') # Date can be anywhere
    cif = None
    modelo = None
    matricula = None
    importe = None
    base_imponible = None # <--- ADD THIS LINE

    for linea in lineas:
        if 'Total Factura' in linea:
            importe = _extract_amount(linea, is_stellantis=True)
            base_imponible = _calculate_base_from_total(importe, vat_rate)
        if cif is None: # Only try if CIF hasn't been found yet
           if re.search(r'- NIF:', linea, re.IGNORECASE):
            extracted_cif = _extract_nif_cif(linea)
            if extracted_cif:
                cif = extracted_cif
            
    return tipo, fecha, numero_factura, cliente, cif, modelo, matricula, importe, base_imponible

def extract_brildor_data(lineas):
    tipo = "COMPRA"
    cliente = "Brildor SL"
    numero_factura = _extract_from_lines_with_keyword(lineas, r'Factura', r'(\d{6,})', look_ahead=2)
    fecha = _extract_from_lines_with_keyword(lineas, r'Fecha', r'(\d{2}/\d{2}/\d{4})', look_ahead=1)
    cif = None
    modelo = None
    matricula = None
    importe = None
    base_imponible = None # <--- ADD THIS LINE

    for i, linea in enumerate(lineas):
        if 'Total' in linea and i + 1 < len(lineas):
            importe = _extract_amount(lineas[i+1])
            if importe: # Only proceed if a non-empty amount string was extracted
               base_imponible = _calculate_base_from_total(importe, vat_rate)
            print(f"base_imponible: {base_imponible}")
        if cif is None: # Only try if CIF hasn't been found yet
            # For Brildor, CIF might be near 'Brildor SL' or general NIF/CIF keyword
            if re.search(r'Brildor SL', linea, re.IGNORECASE):
                extracted_cif = _extract_nif_cif(linea)
                if extracted_cif:
                    cif = extracted_cif
            # If not found yet, try general NIF/CIF keyword
    return tipo, fecha, numero_factura, cliente, cif, modelo, matricula, importe, base_imponible

def extract_hermanas_data(lineas):
    tipo = "COMPRA"
    cliente = "Hermanas del Amor de Dios Casa General"
    numero_factura = _extract_from_lines_with_keyword(lineas, r'FACTURA', r'([A-Z]{2}-\d{2}/\d{4})', look_ahead=6)
    fecha = _extract_from_lines_with_keyword(lineas, r'Fecha', r'(\d{2}/\d{2}/\d{4})')
    cif = None
    modelo = None
    matricula = None
    importe = None
    base_imponible = None # <--- ADD THIS LINE

    for linea in lineas:
        if 'CONCEPTO IMPORTE' in linea:
            importe = _extract_amount(linea)
        elif "CIF: B85629020" in linea:
            importe = _extract_amount(linea)

        base_imponible = _calculate_base_from_total(importe, vat_rate)
        if cif is None: # Only try if CIF hasn't been found yet
            if re.search(r'C.I.F.:', linea, re.IGNORECASE):
                extracted_cif = _extract_nif_cif(linea)
                if extracted_cif:
                    cif = extracted_cif
            
    return tipo, fecha, numero_factura, cliente, cif, modelo, matricula, importe, base_imponible

def extract_kiauto_data(lineas):
    tipo = "COMPRA"
    cliente = "AUTOLUX RECAMBIOS S.L"
    numero_factura = _extract_from_lines_with_keyword(lineas, r'factura', r'(\d{2}\.\d{3}\.\d{3})', look_ahead=1)
    fecha = _extract_from_lines_with_keyword(lineas, r'Fecha factura', r'(\d{2}[-/]\d{2}[-/]\d{4})', look_ahead=1)
    cif = None
    modelo = None
    matricula = None
    importe = None
    base_imponible = None # <--- ADD THIS LINE

    for i, linea in enumerate(lineas):
        if re.search(r'TOTAL FACTURA', linea, re.IGNORECASE) and i + 2 < len(lineas):
            importe = _extract_amount(lineas[i+2])
            base_imponible = _calculate_base_from_total(importe, vat_rate)
            
        if cif is None: # Only try if CIF hasn't been found yet
            # For Kiauto, CIF might be near 'AUTOLUX RECAMBIOS S.L' or general NIF/CIF keyword
            if re.search(r'AUTOLUX RECAMBIOS S\.L', linea, re.IGNORECASE):
                extracted_cif = _extract_nif_cif(linea)
                if extracted_cif:
                    cif = extracted_cif

    return tipo, fecha, numero_factura, cliente, cif, modelo, matricula, importe, base_imponible

def extract_sumauto_data(lineas):
    tipo = "COMPRA"
    cliente = "Sumauto Motor, S.L."
    numero_factura = _extract_from_lines_with_keyword(lineas, r'FAC', r'([A-Z0-9_]+)')
    fecha = _extract_from_lines_with_keyword(lineas, r'Fecha de expedición', r'(\d{2}/\d{2}/\d{4})')
    cif = None
    modelo = None
    matricula = None
    importe = None
    base_imponible = None # <--- ADD THIS LINE

    for linea in lineas:
        if re.search(r'TOTAL TARIFA', linea, re.IGNORECASE):
            importe = _extract_amount(linea)
            base_imponible = _calculate_base_from_total(importe, vat_rate)
            
        # Generic CIF extraction
        if cif is None: # Only try if CIF hasn't been found yet
            extracted_cif = _extract_nif_cif(linea)
            if extracted_cif:
                cif = extracted_cif

    return tipo, fecha, numero_factura, cliente, cif, modelo, matricula, importe, base_imponible

def extract_pinchete_data(lineas):
   
    tipo = "COMPRA"
    cliente = "RECAMBIOS PINCHETE  S.L"
    numero_factura_regex_v2 = r'(FC\s*[A-Z0-9_]+\s*\d+)'
    numero_factura = _extract_from_line(lineas[0], numero_factura_regex_v2)
    fecha = _extract_from_line(lineas[0], r'(\d{2}/\d{2}/\d{4})')
    cif = None
    modelo = None
    matricula = None
    importe = None
    base_imponible = None # <--- ADD THIS LINE

    
    for i, linea in enumerate(lineas):
        
        # Generic CIF extraction
        if cif is None: # Only try if CIF hasn't been found yet
            extracted_cif = _extract_nif_cif(linea)
            if extracted_cif:
                cif = extracted_cif

        if importe is None and re.search(r'Imp.:', linea, re.IGNORECASE):
            importe = _extract_amount(linea)
            base_imponible = _calculate_base_from_total(importe, vat_rate)
            if importe: # If amount is found, we can often stop here
                break
    return tipo, fecha, numero_factura, cliente, cif, modelo, matricula, importe,base_imponible

def extract_refialias_data(lineas):
    tipo = "COMPRA"
    cliente = "REFIALIAS  S.L"
    numero_factura = _extract_from_lines_with_keyword(
    lineas,
    r'FACTURA :',  # This is just for _finding_ the line
    r'FACTURA\s*:\s*([A-Z0-9_/]+)' # This is for _extracting_ the number from the found line
    )
    fecha_regex_pattern = r'(\d{2}-\d{2}-\d{2})'
    fecha = _extract_from_lines_with_keyword(
    lineas,
    fecha_regex_pattern, # Keyword: Find a line that contains this date format
    fecha_regex_pattern  # Regex: Extract the date from that found line
    )
    cif = None
    modelo = None
    matricula = None
    importe = None
    base_imponible = None # <--- ADD THIS LINE

    
    for i, linea in enumerate(lineas):
        
        # Generic CIF extraction
        if cif is None: # Only try if CIF hasn't been found yet
            extracted_cif = _extract_nif_cif(linea)
            if extracted_cif:
                cif = extracted_cif

        if importe is None and re.search(r'I.V.A. TOTAL', linea, re.IGNORECASE):
            importe = _extract_amount(lineas[i+1])
            base_imponible = _calculate_base_from_total(importe, vat_rate)
            if importe: # If amount is found, we can often stop here
                break
    return tipo, fecha, numero_factura, cliente, cif, modelo, matricula, importe,base_imponible

def extract_leroy_data(lineas):
    tipo = "COMPRA"
    cliente = "Leroy Merlin Espana S.L.U"
    numero_factura = _extract_from_lines_with_keyword(
    lineas,
    r'Ejemplar clienteFACTURA',  # Keyword to find the line (this is fine)
    r'Ejemplar\s*clienteFACTURA\s*([A-Z0-9_/-]+)' # Regex to extract the number
)
    fecha = _extract_from_lines_with_keyword(
    lineas,               # Your list of lines
    r'Fecha de venta:',          # Keyword to find the line
    r'(\d{2}/\d{2}/\d{4})',      # Regex to extract the date (this part is correct)
    look_ahead=0                 # <--- CRUCIAL CHANGE: Look on the same line
)
    cif = None
    modelo = None
    matricula = None
    importe = None
    base_imponible = None # <--- ADD THIS LINE

    
    for i, linea in enumerate(lineas):
        # Generic CIF extraction
        if cif is None: # Only try if CIF hasn't been found yet
            extracted_cif = _extract_nif_cif(linea)
            if extracted_cif:
                cif = extracted_cif

        if importe is None and re.search(r'CAMBIO', linea, re.IGNORECASE):
            importe = _extract_amount(lineas[i+1])
            base_imponible = _calculate_base_from_total(importe, vat_rate)
            if importe: # If amount is found, we can often stop here
                break
    return tipo, fecha, numero_factura, cliente, cif, modelo, matricula, importe,base_imponible
def extract_poyo_data(lineas):
   
    tipo = "COMPRA"
    cliente = "PEDRO GARRIDO RODRÍGUEZ"
    numero_factura = None
    fecha = None
    cif = None
    modelo = None
    matricula = None
    importe = None
    base_imponible = None # <--- ADD THIS LINE

    
    for i, linea in enumerate(lineas):
        invoice_regex = r'(F[A-Z0-9_]+/[A-Z0-9_]+)' 
        date_regex = r'(\d{2}/\d{2}/\d{4})'
        if numero_factura is None and re.search(invoice_regex, linea, re.IGNORECASE):
            match = re.search(invoice_regex, linea, re.IGNORECASE)
            if match:
                numero_factura = match.group(1)
        if fecha is None and re.search(date_regex, linea):
            match= re.search(date_regex, linea)
            if match:
                fecha = match.group(1)
        # Generic CIF extraction
        if cif is None and re.search(r'DNI:', linea, re.IGNORECASE): # Only try if CIF hasn't been found yet
            extracted_cif = _extract_nif_cif(linea)
            if extracted_cif:
                cif = extracted_cif

        if importe is None and re.search(r'TOTAL', linea, re.IGNORECASE):
            print(f"Línea: {lineas[i+1]}")
            importe = _extract_amount(lineas[i+1])
            base_imponible = _calculate_base_from_total(importe, vat_rate)
            if importe: # If amount is found, we can often stop here
                break
    return tipo, fecha, numero_factura, cliente, cif, modelo, matricula, importe,base_imponible
def extract_lacaravana_data(lineas):
    tipo = "COMPRA"
    cliente = "LA CARAVANA SL"
    numero_factura = None
    fecha = None
    cif = None
    modelo = None
    matricula = None
    importe = None
    base_imponible = None

    for i, linea in enumerate(lineas):
        invoice_regex = r'(F-[A-Z0-9_]+-[A-Z0-9_]+)'
        date_regex = r'(\d{2}/\d{2}/\d{4})'

        if numero_factura is None and re.search("lacaravana", linea, re.IGNORECASE):
            match = re.search(invoice_regex, linea, re.IGNORECASE)
            if match:
                numero_factura = match.group(1)
        
        if fecha is None and re.search(date_regex, linea):
            match = re.search(date_regex, linea)
            if match:
                fecha = match.group(1)
        
        # Generic CIF extraction
        if cif is None:
            extracted_cif = _extract_nif_cif(linea)
            if extracted_cif:
                cif = extracted_cif

        # Corrected importe extraction: Look for "TOTAL :" and extract from that line or the next
        if importe is None and re.search(r'TOTAL :', linea, re.IGNORECASE):
            # The total amount is on the same line as "TOTAL:" based on the PDF content
            importe = _extract_amount(lineas[i+1]) # Extract from the current line
            if importe:
                base_imponible = _calculate_base_from_total(importe, vat_rate)
                break # Stop after finding the total and base
            
    return tipo, fecha, numero_factura, cliente, cif, modelo, matricula, importe, base_imponible

def extract_malaga_data(lineas):
    tipo = "COMPRA"
    cliente = "EURO DESGUACES MALAGA S.L"
    numero_factura = None
    fecha = None
    cif = None
    modelo = None
    matricula = None
    importe = None
    base_imponible = None

    for i, linea in enumerate(lineas):
        invoice_regex = r'([0-9]+\s+\d{6,})'
        date_regex = r'(\d{2}/\d{2}/\d{4})'

        if numero_factura is None and re.search("Madrid1", linea, re.IGNORECASE):
            match = re.search(invoice_regex, linea, re.IGNORECASE)
            if match:
                numero_factura = match.group(1)
        
        if fecha is None and  re.search("Madrid1", linea, re.IGNORECASE):
            match = re.search(date_regex, lineas[i+1])
            if match:
                fecha = match.group(1)
        
        # Generic CIF extraction
        if cif is None and re.search("C.I.F.", linea, re.IGNORECASE):
            print(f"Línea : {linea}")
            extracted_cif = _extract_nif_cif(linea)
            if extracted_cif:
                cif = extracted_cif

        # Corrected importe extraction: Look for "TOTAL :" and extract from that line or the next
        if importe is None and i == len(lineas) - 1:
            # The total amount is on the same line as "TOTAL:" based on the PDF content
            importe = _extract_amount(linea) # Extract from the current line
            if importe:
                base_imponible = _calculate_base_from_total(importe, vat_rate)
                break # Stop after finding the total and base
            
    return tipo, fecha, numero_factura, cliente, cif, modelo, matricula, importe, base_imponible

def extract_beroil_data(lineas):
    tipo = "COMPRA"
    cliente = "BEROIL S.L."
    numero_factura = None
    fecha = None
    cif = None
    modelo = None
    matricula = None
    importe = None
    base_imponible = None

    for i, linea in enumerate(lineas):
        invoice_regex =  r"FACTURA NÚM:\s*([A-Z0-9_ -]+)"

        if numero_factura is None and re.search("FACTURA NÚM:", linea, re.IGNORECASE):
            match = re.search(invoice_regex, linea, re.IGNORECASE)
            if match:
                numero_factura = match.group(1)
        
        fecha = _extract_from_lines_with_keyword(lineas, [r'Fecha', r'Fecha de emisión', r'Date'], r'(\d{2}[-/]\d{2}[-/]\d{4})')
        if fecha is None: # If not found in standard numeric format, try the month-name format
            fecha = extract_and_format_date(lineas) # Assuming extract_and_format_date is available and correctly defined
        
        # Generic CIF extraction
        if cif is None and re.search("CIF:", linea, re.IGNORECASE):
            extracted_cif = _extract_nif_cif(linea)
            if extracted_cif:
                cif = extracted_cif

        # Corrected importe extraction: Look for "TOTAL :" and extract from that line or the next
        if importe is None and re.search(r"FORMA DE PAGO:", linea, re.IGNORECASE):
           
            # Check if there's a previous line to extract the amount from
            if i > 0:
               
                # The total amount is on the line immediately preceding "FORMA DE PAGO:"
                importe = _extract_amount(lineas[i-1])
               
                if importe:
                    base_imponible = _calculate_base_from_total(importe, vat_rate)
                    break # Stop after finding the total and base
            
    return tipo, fecha, numero_factura, cliente, cif, modelo, matricula, importe, base_imponible
def extract_autocasher_data(lineas):
    tipo = "COMPRA"
    cliente = "AUTOCASHER PILAS, SL"
    numero_factura = None
    fecha = None
    cif = None
    modelo = None
    matricula = None
    importe = None
    base_imponible = None

    for i, linea in enumerate(lineas):
        invoice_regex =  r"B-85629020\s*([A-Z0-9_ -]+)"

        if numero_factura is None :
            match = re.search(invoice_regex, linea, re.IGNORECASE)
            if match:
                numero_factura = match.group(1)
        
        fecha = _extract_from_lines_with_keyword(lineas,r'(\d{2}[-/]\d{2}[-/]\d{4})', r'(\d{2}[-/]\d{2}[-/]\d{4})')
        if fecha is None: # If not found in standard numeric format, try the month-name format
            fecha = extract_and_format_date(lineas) # Assuming extract_and_format_date is available and correctly defined
        
        # Generic CIF extraction
        if cif is None and re.search("CIF:", linea, re.IGNORECASE):
            extracted_cif = _extract_nif_cif(linea)
            if extracted_cif:
                cif = extracted_cif

        # Corrected importe extraction: Look for "TOTAL :" and extract from that line or the next
        if importe is None and re.search(r"TOTAL  FACTURA", linea, re.IGNORECASE):
           
            # Check if there's a previous line to extract the amount from
            if i > 0:
               
                # The total amount is on the line immediately preceding "FORMA DE PAGO:"
                importe = _extract_amount(lineas[i+1])
               
                if importe:
                    base_imponible = _calculate_base_from_total(importe, vat_rate)
                    break # Stop after finding the total and base
            
    return tipo, fecha, numero_factura, cliente, cif, modelo, matricula, importe, base_imponible

def extract_cesvimap_data(lineas):
    tipo = "COMPRA"
    cliente = "CENTRO DE EXPERIMENTACIÓN Y SEGURIDAD VIAL MAPFRE"
    numero_factura = None
    fecha = None
    cif = None
    modelo = None
    matricula = None
    importe = None
    base_imponible = None

    for i, linea in enumerate(lineas):
        invoice_regex = r"R-(\d+)"
        if numero_factura is None :
            match = re.search(invoice_regex, linea, re.IGNORECASE)
            if match:
                numero_factura = match.group(1)
        
        fecha = _extract_from_lines_with_keyword(lineas,r'(\d{2}[-/]\d{2}[-/]\d{4})', r'(\d{2}[-/]\d{2}[-/]\d{4})')
        if fecha is None: # If not found in standard numeric format, try the month-name format
            fecha = extract_and_format_date(lineas) # Assuming extract_and_format_date is available and correctly defined
        
        # Generic CIF extraction
        if cif is None and re.search("NIF:", linea, re.IGNORECASE):
            extracted_cif = _extract_nif_cif(linea)
            if extracted_cif:
                cif = extracted_cif

        # Corrected importe extraction: Look for "TOTAL :" and extract from that line or the next
        if importe is None and re.search(r"TOTAL  ", linea, re.IGNORECASE):
            importe = _extract_amount(linea)
            base_imponible = _calculate_base_from_total(importe, vat_rate)
            break # Stop after finding the total and base
            
    return tipo, fecha, numero_factura, cliente, cif, modelo, matricula, importe, base_imponible
def extract_fiel_data(lineas):
    tipo = "COMPRA"
    cliente = "COMBUSTIBLES FIEL S.L"
    numero_factura = None
    fecha = None
    cif = None
    modelo = None
    matricula = None
    importe = None
    base_imponible = None

    for i, linea in enumerate(lineas):
        invoice_regex = r"M(\d+)\s+(\d+)"

        if numero_factura is None:
            match = re.search(invoice_regex, linea, re.IGNORECASE)
            if match:
                # Reconstruct the full invoice number by combining 'M', group 1, a space, and group 2
              numero_factura = f"M{match.group(1)} {match.group(2)}"
        
        fecha = _extract_from_lines_with_keyword(lineas,r'(\d{2}[-/]\d{2}[-/]\d{4})', r'(\d{2}[-/]\d{2}[-/]\d{4})')
        if fecha is None: # If not found in standard numeric format, try the month-name format
            fecha = extract_and_format_date(lineas) # Assuming extract_and_format_date is available and correctly defined
        
        # Generic CIF extraction
        if cif is None and re.search("CIF.:", linea, re.IGNORECASE):
            extracted_cif = _extract_nif_cif(linea)
            if extracted_cif:
                cif = extracted_cif

        # Corrected importe extraction: Look for "TOTAL :" and extract from that line or the next
        if importe is None and re.search(r"Total factura  ", linea, re.IGNORECASE):
            importe = _extract_amount(linea)
            base_imponible = _calculate_base_from_total(importe, vat_rate)
            break # Stop after finding the total and base
            
    return tipo, fecha, numero_factura, cliente, cif, modelo, matricula, importe, base_imponible
def extract_pradilla_data(lineas):
    tipo = "COMPRA"
    cliente = "GESTORIA PRADILLA, S.L."
    numero_factura = None
    fecha = None
    cif = "B-80481369"
    modelo = None
    matricula = None
    importe = None
    base_imponible = None
    
    vat_rate = 0.21 # Assuming 21% VAT (IVA in Spain)
    invoice_regex = r"(\d+)" 

    for i, linea in enumerate(lineas):
        # Extract Fecha
        if fecha is None and re.search(r"FECHA", linea, re.IGNORECASE):
            # Check if there are enough lines to prevent IndexError
            if i + 2 < len(lineas):
                print(f"line: {lineas[i+2]} ")
                fecha = _extract_from_line(lineas[i+2], r'(\d{2}[-/]\d{2}[-/]\d{4})')
                print(f"fecha: {fecha} ")
                if fecha is None: # If not found in standard numeric format, try the month-name format
                    fecha = extract_and_format_date(lineas[i+2]) # Assuming extract_and_format_date is available and correctly defined
           

        # Extract Numero Factura
        # Moved the invoice_regex definition outside the loop for efficiency
        if numero_factura is None and re.search(r"NºFACTURA", linea, re.IGNORECASE):
            # Check if there are enough lines to prevent IndexError
            if i + 2 < len(lineas):
                match = re.search(invoice_regex, lineas[i+2], re.IGNORECASE)
                if match:
                    numero_factura = f"{match.group(1)}"
            # If not enough lines, 'numero_factura' will remain None.

        # Extract Importe and Base Imponible
        if importe is None and re.search(r"TOTAL A PAGAR ", linea, re.IGNORECASE):
            # Check if there are enough lines to prevent IndexError
            if i + 1 < len(lineas):
                importe = _extract_amount(lineas[i+1])
                if importe is not None:
                    base_imponible = _calculate_base_from_total(importe, vat_rate)
                    break # Stop after finding the total and base

    return tipo, fecha, numero_factura, cliente, cif, modelo, matricula, importe, base_imponible
def extract_boxes_data(lineas, pdf_path): # Add pdf_path as an argument
    tipo = "COMPRA"
    cliente = "BOXES INTEGRALCAR, S.L" # 
    numero_factura = None
    fecha = None
    cif = "B-84962851" # 
    modelo = None
    matricula = None
    importe = None
    base_imponible = None
    
    vat_rate = 0.21 # Assuming 21% VAT (IVA in Spain)
    

    # Extract numero_factura from filename
    if pdf_path:
        nombre_archivo = os.path.basename(pdf_path)
        match_invoice_num = re.search(r'FRA(\d+)-', nombre_archivo, re.IGNORECASE)
        if match_invoice_num:
            numero_factura = match_invoice_num.group(1)

    for i, linea in enumerate(lineas):
        # Extract Fecha
        if fecha is None and re.search(r"Conforme Cliente", linea, re.IGNORECASE):
            print(f"linea {linea}")
            fecha = _extract_from_line(linea, r'(\d{2}[-/]\d{2}[-/]\d{4})')
            
        # Extract Importe and Base Imponible
        if importe is None and re.search(r"TOTAL FACTURA", linea, re.IGNORECASE): # 
            importe = _extract_amount(linea) # 
            if importe is not None:
                base_imponible = _calculate_base_from_total(importe, vat_rate) # 
                break # Stop after finding the total and base

    return tipo, fecha, numero_factura, cliente, cif, modelo, matricula, importe, base_imponible

def extract_hergar_data(lineas):
    tipo = "COMPRA"
    cliente = "GESTORIA PRADILLA, S.L."
    numero_factura = None
    fecha = None
    cif = "A-78009172"
    modelo = None
    matricula = None
    importe = None
    base_imponible = None
    
    vat_rate = 0.21 # Assuming 21% VAT (IVA in Spain)
    invoice_regex = r"(\d+)" 

    for i, linea in enumerate(lineas):
        # Extract Fecha
        if fecha is None and re.search(r"FECHA:", linea, re.IGNORECASE):
            # Check if there are enough lines to prevent IndexError
                print(f"line: {linea} ")
                fecha = _extract_from_line(linea, r'(\d{2}[-/]\d{2}[-/]\d{4})')
                print(f"fecha: {linea} ")
           

        # Extract Numero Factura
        # Moved the invoice_regex definition outside the loop for efficiency
        if numero_factura is None and re.search(r"Nº.", linea, re.IGNORECASE):
            # Check if there are enough lines to prevent IndexError
                match = re.search(invoice_regex, linea, re.IGNORECASE)
                if match:
                    numero_factura = f"{match.group(1)}"
            # If not enough lines, 'numero_factura' will remain None.

        # Extract Importe and Base Imponible
        if importe is None and re.search(r"TOTAL FACTURA ", linea, re.IGNORECASE):
            # Check if there are enough lines to prevent IndexError
            if i + 1 < len(lineas):
                importe = _extract_amount(lineas[i+1])
                if importe is not None:
                    base_imponible = _calculate_base_from_total(importe, vat_rate)
                    break # Stop after finding the total and base

    return tipo, fecha, numero_factura, cliente, cif, modelo, matricula, importe, base_imponible

def extract_musas_data(lineas):
    tipo = "COMPRA"
    cliente = "LasMusas, S.L."
    numero_factura = None
    fecha = None
    cif = "B81583445"
    modelo = None
    matricula = None
    importe = None
    base_imponible = None
    
    vat_rate = 0.21 # Assuming 21% VAT (IVA in Spain)
    invoice_regex = r"([A-Z0-9\s]+)"
    for i, linea in enumerate(lineas):
        
        # --- Generic CIF extraction ---
        if cif is None: # Only try if CIF hasn't been found yet
            extracted_cif = _extract_nif_cif(linea)
            if extracted_cif != "B85629020":
                cif = extracted_cif

        # Extract Fecha  
        if fecha is None and re.search(r"Fecha", linea, re.IGNORECASE):
            # Check if there are enough lines to prevent IndexError
                fecha = _extract_from_line(linea, r'(\d{2}[-/]\d{2}[-/]\d{4})')
            

        # Extract Numero Factura
        # Moved the invoice_regex definition outside the loop for efficiency
        if numero_factura is None and re.search(r"FACTURA Nº", linea, re.IGNORECASE):
                # Check if there are enough lines to prevent IndexError
                match = re.search(invoice_regex, lineas[i+1], re.IGNORECASE)
                if match:
                    numero_factura = f"{match.group(1)}"
            # If not enough lines, 'numero_factura' will remain None.
        
        # Extract Importe and Base Imponible
        if importe is None and re.search(r"TOTAL A", linea, re.IGNORECASE):
            # Check if there are enough lines to prevent IndexError
            if i + 1 < len(lineas):
                importe = _extract_amount(lineas[i+1])
                if importe is not None:
                    base_imponible = _calculate_base_from_total(importe, vat_rate)
                    break # Stop after finding the total and base
    return tipo, fecha, numero_factura, cliente, cif, modelo, matricula, importe, base_imponible
def extract_aema_data(lineas):
    tipo = "COMPRA"
    cliente = " NEUMÁTICOS AEMA, S.A."
    numero_factura = None
    fecha = None
    cif = None
    modelo = None
    matricula = None
    importe = None
    base_imponible = None
    invoice_regex = r"Fecha:([A-Z0-9-]+)\sNúmero:"
    vat_rate = 0.21 # Assuming 21% VAT (IVA in Spain)
    for i, linea in enumerate(lineas):
        # Extract Fecha
        if fecha is None and re.search(r"Fecha:", linea, re.IGNORECASE):
            # Check if there are enough lines to prevent IndexError
                print(f"line: {linea} ")
                fecha = _extract_from_line(linea, r'(\d{2}[-/]\d{2}[-/]\d{4})')
                print(f"fecha: {linea} ")
           
        if cif is None: # Only try if CIF hasn't been found yet
            extracted_cif = _extract_nif_cif(linea)
            if extracted_cif != "B85629020":
                cif = extracted_cif
        # Extract Numero Factura
        # Moved the invoice_regex definition outside the loop for efficiency


        if numero_factura is None and re.search(r"Número:FACTURA DE VENTA", linea, re.IGNORECASE):
            print(f"numero_factura (current line): {linea}")
            
            # Use the more specific invoice_regex to find the number within its context
            match = re.search(invoice_regex, linea, re.IGNORECASE)
            
            print(f"match object: {match}")
            
            if match:
                numero_factura = match.group(1) # Extract only the captured invoice number
                print(f"Successfully extracted numero_factura: {numero_factura}")
            else:
                print("No invoice number found with the new regex.")

        # Extract Importe and Base Imponible
        if importe is None and re.search(r"Retención", linea, re.IGNORECASE):
            # Check if there are enough lines to prevent IndexError
            if i + 1 < len(lineas):
                importe = _extract_amount(lineas[i+1]).replace('.', '')
                if importe is not None:
                    base_imponible = _calculate_base_from_total(importe, vat_rate)
                    break # Stop after finding the total and base

    return tipo, fecha, numero_factura, cliente, cif, modelo, matricula, importe, base_imponible



def extract_autodescuento_data(lineas):
    tipo = "COMPRA"
    cliente = "AUTODESCUENTO SL" # Corrected typo in client name
    numero_factura = None
    fecha = None
    cif = None
    modelo = None # Not found in this example, will remain None
    matricula = None # Not found in this example, will remain None
    importe = None
    base_imponible = None
    
    # New regex for invoice number: look for digits at the end of the line
    # This will be used when the 'Número' trigger is found
    # It matches one or more digits, potentially preceded by space, at the end of the line.
    invoice_number_regex = r'(\d+)\s*$' # Use \b for word boundary, \s*$ for end of string

    vat_rate = 0.21 # Assuming 21% VAT (IVA in Spain)

    # Variables to hold lines for easier debugging/context
    # linea_10 = "CIF/DNI: Serie Cliente B85629020 Número Fecha"
    # linea_11 = "4300003562 03/06/2025 5021"
    # linea_18 = "119,79 Forma de pago Líquido(EUR):"

    for i, linea in enumerate(lineas):
        # Extract Fecha
        # The date is on Line 11, but 'Fecha:' is on Line 10.
        # We need to find "Fecha:" on Line 10 and then extract the date from Line 11.
        if fecha is None and re.search(r"Fecha\s*$", lineas[i], re.IGNORECASE): # Match "Fecha" at end of current line
            if i + 1 < len(lineas): # Ensure there's a next line
                # Regex for date: Looks for DD/MM/YYYY
                date_match = re.search(r'(\d{2}[-/]\d{2}[-/]\d{4})', lineas[i+1])
                if date_match:
                    fecha = date_match.group(1)
                    # print(f"DEBUG: Found date: {fecha} from line: {lineas[i+1]}")
                # else:
                    # print(f"DEBUG: No date found on line {i+1} after 'Fecha:' trigger.")

        # Extract CIF
        if cif is None and re.search(r"CIF.: ", linea, re.IGNORECASE):
            extracted_cif = _extract_nif_cif(linea)
            # You might want to filter out 'B85629020' if it's considered a dummy/provider CIF
            # However, in this case, it appears to be the *provider's* CIF, which might be correct.
            # If you specifically want the *client's* CIF (if different), you'd need more context.
            if extracted_cif:
                cif = extracted_cif
                # print(f"DEBUG: Extracted CIF: {cif} from line: {linea}")


        # Extract Numero Factura
        # Trigger is "Número" on Line 10, number is "5021" on Line 11
        if numero_factura is None and re.search(r"Número", linea, re.IGNORECASE):
            print(f"DEBUG: Trigger line matched: {lineas[i+1]} {i} {len([lineas])}")
            if i + 1 < len([lineas]): # Simplified check for example
                # The invoice number is the last sequence of digits on line 11
                # Use the updated regex here
                match = re.search(invoice_number_regex, lineas[i+1]) # Using the example line directly
                print(f"match: {match}")
                
                print(f"DEBUG: Match object: {match}")
                
                if match:
                    numero_factura = match.group(1) # This should capture '5021'
                    print(f"DEBUG: Successfully extracted numero_factura: {numero_factura} from line: {lineas[i+1]}")
                else:
                    print(f"DEBUG: No invoice number found on line {lineas[i+1]} with regex '{lineas[i+1]}'.")

        # Extract Importe and Base Imponible
        # Amount is on the same line as "Forma de pago Líquido(EUR):"
        if importe is None and re.search(r"Forma de pago Líquido\(EUR\):", linea, re.IGNORECASE):
            # Extract the amount from the beginning of the line
            amount_match = re.search(r'^([\d\.,]+)', linea.strip()) # Capture number at start of line
            if amount_match:
                importe_str = amount_match.group(1)
                importe = _extract_amount(importe_str) # Use the robust _extract_amount
                if importe is not None:
                    base_imponible = _calculate_base_from_total(importe, vat_rate)
                    # print(f"DEBUG: Extracted importe: {importe}, base_imponible: {base_imponible} from line: {linea}")
                    # We can break here if the total is always the last main piece of info
                    # break

    return tipo, fecha, numero_factura, cliente, cif, modelo, matricula, importe, base_imponible



def extract_generic_data(lineas):
    """ Generic extraction for other invoice types. """
    tipo, fecha, numero_factura, cliente, cif, modelo, matricula, importe = "COMPRA", None, None, None, None, None, None, None
    base_imponible = None

    # --- Initial extractions using _extract_from_lines_with_keyword ---
   
    fecha = _extract_from_lines_with_keyword(lineas, [r'Fecha', r'Fecha de emisión', r'Date'], r'(\d{2}[-/]\d{2}[-/]\d{4})')
    if fecha is None: # If not found in standard numeric format, try the month-name format
        fecha = extract_and_format_date(lineas) # Assuming extract_and_format_date is available and correctly defined

    # Invoice number extraction (flexible for various "Factura" keywords and formats)
    numero_factura = _extract_from_lines_with_keyword(lineas, [r'FACTURA', r'Nº Factura', r'Número de factura', r'FACTURA DE VENTA',r'Factura Número', r'Invoice No\.?',], r'([A-Z0-9_-]+)')
    # Add explicit check for FXXX/YYYY format if it's not caught by the above generic.
    if numero_factura is None:
        invoice_f_slash_regex = r'(F[A-Z0-9_]+/[A-Z0-9_]+)'
        for line in lineas:
            match = re.search(invoice_f_slash_regex, line, re.IGNORECASE)
            if match:
                numero_factura = match.group(1)
                break


    # --- Loop through lines for more specific extractions ---
    for i, linea in enumerate(lineas):

        # --- Cliente (Customer) ---
        # The regex 'Cliente\s*:\s*(.*)|Customer\s*:\s*(.*)' is more specific and should work if found
        if cliente is None: # Only try to find if not already found
            cliente_match = re.search(r'Cliente\s*:\s*(.*)|Customer\s*:\s*(.*)', linea, re.IGNORECASE)
            if cliente_match:
                # Ensure at least one group matched before stripping
                if cliente_match.group(1) is not None:
                    cliente = cliente_match.group(1).strip()
                elif cliente_match.group(2) is not None:
                    cliente = cliente_match.group(2).strip()
                # You can add more general client name extraction here if needed
                # e.g., if there's a fixed "REFIALIAS S.L" on a specific line.

        # --- Generic CIF extraction ---
        if cif is None: # Only try if CIF hasn't been found yet
            extracted_cif = _extract_nif_cif(linea)
            if extracted_cif != "B85629020":
                cif = extracted_cif

        # --- Modelo (Model) ---
    
        if modelo is None and re.search(r'Modelo|Model', linea, re.IGNORECASE):
           
            
            # First, try the structured "Modelo: X" pattern
            modelo_match = re.search(r'Modelo\s*:\s*(.*)|Model\s*:\s*(.*)', linea, re.IGNORECASE)
            if modelo_match:
                # Safely assign, ensuring a group was captured
                if modelo_match.group(1) is not None:
                    modelo = modelo_match.group(1).strip()
                elif modelo_match.group(2) is not None:
                    modelo = modelo_match.group(2).strip()
            
            
            if modelo is None: # Only try if not found by structured pattern
                
                car_model_pattern = r'(\d{9,15})(RENAULT|VOLKSWAGEN|FORD|BMW|MERCEDES|AUDI|SEAT|OPEL)\s*([A-Z0-9\s-]+)?'
                model_in_line_match = re.search(car_model_pattern, linea, re.IGNORECASE)
                if model_in_line_match:
                    modelo = (model_in_line_match.group(2) + " " + (model_in_line_match.group(3) or "")).strip()


        
        if matricula is None and re.search(r'Matrícula|License Plate', linea, re.IGNORECASE):
            # Specific pattern for Spanish matriculas (e.g., 1234 ABC, M-1234-AB, etc.)
            # This is a robust pattern for new Spanish plates (4 digits, 3 letters)
            matricula_pattern = r'(\d{4}\s*[A-Z]{3})' # For 1234 ABC format
            match_plate = re.search(matricula_pattern, linea, re.IGNORECASE)
            if match_plate:
                matricula = match_plate.group(1).strip()
            else:
                # If not found with standard new format, try older formats or just general strong alphanumeric
                # For example, "2416KZM" fits a more generic AAAAABC/AABBC format
                # Let's target alphanumeric strings that are likely license plates
                matricula_match_generic = re.search(r'\b([A-Z0-9]{4,8}[A-Z]{0,3})\b', linea, re.IGNORECASE)
                # This is more heuristic and could catch non-plates, but might catch 2416KZM
                if matricula_match_generic and len(matricula_match_generic.group(1)) >= 6: # Basic length check
                    matricula = matricula_match_generic.group(1).strip()
                
                # Check for "2416KZM" specifically (line 20)
                if matricula is None:
                    # This is very specific to line 20 in your example document
                    # It captures 4 digits then 3 letters at the end of a line
                    specific_plate_pattern = r'(\d{4}[A-Z]{3})\s*$'
                    specific_match = re.search(specific_plate_pattern, linea, re.IGNORECASE)
                    if specific_match:
                        matricula = specific_match.group(1).strip()


        # --- Importe and Base Imponible ---
        if importe is None and re.search(r'Total Factura|Importe Total|Total a pagar|Amount Due|TOTAL FACTURA', linea, re.IGNORECASE):
            total_factura_amount_match = re.search(r'TOTAL FACTURA\s*.*?(\d{1,3}(?:\.\d{3})*,\d{2})\s*€?', linea, re.IGNORECASE)
            
            if total_factura_amount_match:
                extracted_total_amount_str = total_factura_amount_match.group(1)
                
                if extracted_total_amount_str:
                    importe = extracted_total_amount_str
                    # Ensure vat_rate is defined (e.g., 0.21)
                    vat_rate = 0.21 # As per previous context
                    base_imponible = _calculate_base_from_total(importe, vat_rate)
                    
                    # If importe and base are found, and this is the main total, we can break.
                    break # Break the loop as main data is found
                else:
                    print(f"⚠️ Warning: 'TOTAL FACTURA' found, but no valid amount extracted from line: '{linea}'")
            else:
                # Fallback to generic _extract_amount if the specific 'TOTAL FACTURA' pattern didn't work
                # This might happen if 'Total Factura' is found, but not followed by amount in the same way.
                extracted_total_amount_str = _extract_amount(linea)
                if extracted_total_amount_str:
                    importe = extracted_total_amount_str
                    vat_rate = 0.21
                    base_imponible = _calculate_base_from_total(importe, vat_rate)
                    break # Break if a generic amount was found

    return tipo, fecha, numero_factura, cliente, cif, modelo, matricula, importe, base_imponible


# --- Dispatcher Mapping ---
EXTRACTION_FUNCTIONS = {
    "autodoc": extract_autodoc_data,
    "stellantis": extract_stellantis_data,
    "brildor": extract_brildor_data,
    "hermanas": extract_hermanas_data,
    "kiauto": extract_kiauto_data,
    "sumauto": extract_sumauto_data,
    "amor": extract_hermanas_data,
    "pinchete": extract_pinchete_data,
    "refialias": extract_refialias_data,
    "leroy":extract_leroy_data,
    "poyo":extract_poyo_data,
    "caravana":extract_lacaravana_data,
    "malaga":extract_malaga_data,
    "beroil":extract_beroil_data,
    "autocasher":extract_autocasher_data,
    "cesvimap":extract_cesvimap_data,
    "fiel":extract_fiel_data,
    "pradilla":extract_pradilla_data,
    "boxes":extract_boxes_data,
    "hergar":extract_hergar_data,
    "musas":extract_musas_data,
    "muas":extract_musas_data,
    "aema":extract_aema_data,
    "autodescuento":extract_autodescuento_data
}

# --- Main PDF Processing Logic ---

def extraer_datos(pdf_path, debug_mode=False):
    """ Detects the invoice type and applies the correct extraction function. """
    print(f"✅ Entrando en extraer_datos() con archivo: {pdf_path} y debug_mode: {debug_mode}")
    
    try:
        with open(pdf_path, 'rb') as archivo:
            pdf = PyPDF2.PdfReader(archivo)
            texto = ''
            for pagina in pdf.pages:
                texto += pagina.extract_text() or ''
            lineas = texto.splitlines()
    except Exception as e:
        print(f"❌ Error al leer el PDF {pdf_path}: {e}")
        return "COMPRA", None, None, None, None, None, None, None # Return default empty data

    if debug_mode:
        print("\n🔍 MODO DEBUG ACTIVADO: Mostrando todas las líneas del archivo\n")
        for i, linea in enumerate(lineas):
            print(f"Línea {i}: {linea}")

    nombre_archivo = os.path.basename(pdf_path).lower()

    for keyword, func in EXTRACTION_FUNCTIONS.items():
        if keyword in nombre_archivo:
            print(f"➡️ Detectado '{keyword}' en el nombre del archivo. Usando la función de extracción específica.")
            # Pass pdf_path to the specific extraction function if it's 'boxes'
            if keyword == "boxes":
                return func(lineas, pdf_path)
            else:
                return func(lineas) # Other functions might not need pdf_path
    
    
    print("➡️ No se detectó un tipo de factura específico. Usando la función de extracción genérica.")
    return extract_generic_data(lineas)

# --- Command-Line Argument Parsing and CSV Output ---

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Procesar un archivo PDF o todos los PDFs en una carpeta.')
    parser.add_argument('ruta', help='Ruta a un archivo PDF o a una carpeta con archivos PDF')
    parser.add_argument('--debug', action='store_true', help='Activar modo depuración (True/False)')
    args = parser.parse_args()

    ruta = args.ruta
    debug_mode = args.debug
    archivos_pdf = []

    if os.path.isfile(ruta) and ruta.lower().endswith('.pdf'):
        archivos_pdf.append(ruta)
    elif os.path.isdir(ruta):
        archivos_pdf = [os.path.join(ruta, archivo) for archivo in os.listdir(ruta) if archivo.lower().endswith('.pdf')]

    if not archivos_pdf:
        print("❌ No se encontraron archivos PDF para procesar.")
        exit()

    csv_path = os.path.join(os.path.dirname(ruta), 'facturas_resultado.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Archivo', 'Tipo', 'Fecha', 'Número de Factura', 'Cliente', 'CIF', 'Modelo', 'Matricula', "Base","iva",'Importe'])

        for archivo in archivos_pdf:
            print(f"\n--- Procesando archivo: {os.path.basename(archivo)} ---")
            tipo, fecha, numero_factura, cliente, cif, modelo, matricula, importe, base_imponible= extraer_datos(archivo, debug_mode)
            
            formatted_importe = 'No encontrado'
            if importe is not None:
                try:
                    # Ensure conversion to dot-decimal for formatting
                    print(f"importe: {importe}")
                    numeric_importe = float(str(importe).replace(',', '.')) 
                    print(f"importe: {numeric_importe}")
                    formatted_importe = f"{numeric_importe:.2f} €".replace('.', ',') # Format back to comma-decimal
                except ValueError:
                    formatted_importe = str(importe) # Keep as is if conversion fails

            writer.writerow([
                os.path.basename(archivo),
                tipo or 'No encontrado',
                fecha or 'No encontrada',
                numero_factura or 'No encontrado',
                cliente or 'No encontrado',
                cif or 'No encontrado',
                modelo or 'No encontrado',
                matricula or 'No encontrado',
                base_imponible or 'No encontrado',
                vat_rate or 'No encontrado',
                formatted_importe
            ])

    print(f"\n✅ ¡Hecho! Revisa el archivo de resultados en: {csv_path}")