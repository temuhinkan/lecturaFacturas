import os
import re
import csv
import PyPDF2
import argparse

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
    if is_stellantis and len(values) >= 2:
        try:
            val1 = float(values[0].replace('.', '').replace(',', '.'))
            val2 = float(values[1].replace('.', '').replace(',', '.'))
            return str(f"{val1 + val2:.2f}").replace('.', ',')
        except ValueError:
            pass
    return values[-1] if values else None

def _extract_nif_cif(line):
    """
    Extracts NIF/CIF from a line, handling common Spanish formats.
    """
    dni_pattern = r'(\d{1,3}(?:\.\d{3}){2}-?[A-Z])|(\d{8}[A-Z])'
    cif_with_separators_pattern = r'([A-Z][-\.]?\d{1,3}(?:[\.\-]?\d{3}){2,3}[A-Z]?)'
    cif_without_separators_pattern = r'([A-Z]{1,3}\d{7,8}[A-Z]?)'

    dni_match = re.search(dni_pattern, line, re.IGNORECASE)
    if dni_match:
        if dni_match.group(1):
            return dni_match.group(1).replace('.', '').replace('-', '')
        elif dni_match.group(2):
            return dni_match.group(2)

    cif_sep_match = re.search(cif_with_separators_pattern, line, re.IGNORECASE)
    if cif_sep_match:
        return cif_sep_match.group(1).replace('.', '').replace('-', '')

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

# --- Base Extractor Class ---

class BaseInvoiceExtractor:
    def __init__(self, lines, pdf_path=None):
        self.lines = lines
        self.pdf_path = pdf_path
        self.tipo = "COMPRA"
        self.emisor = "No encontrado" # The invoice issuer
        self.cliente = "NEW SATELITE, S.L." # The client is fixed for all invoices
        self.numero_factura = None
        self.fecha = None
        self.cif = None
        self.modelo = None
        self.matricula = None
        self.importe = None
        self.base_imponible = None
        self.vat_rate = VAT_RATE

    def extract_all(self):
        """Main method to perform all extractions."""
        self._extract_fecha()
        self._extract_numero_factura()
        self._extract_emisor() # Now extracts the issuer
        self._extract_cif()
        self._extract_modelo()
        self._extract_matricula()
        self._extract_importe_and_base()
        return (self.tipo, self.fecha, self.numero_factura, self.emisor, # Returns issuer instead of client
                self.cliente, self.cif, self.modelo, self.matricula, self.importe, self.base_imponible)

    def _extract_fecha(self):
        """Extracts the date using common patterns."""
        self.fecha = _extract_from_lines_with_keyword(
            self.lines,
            [r'Fecha', r'Fecha de emisión', r'Date'],
            r'(\d{2}[-/]\d{2}[-/]\d{4})'
        )
        if self.fecha is None:
            self.fecha = extract_and_format_date(self.lines)

    def _extract_numero_factura(self):
        """Extracts the invoice number using common patterns."""
        self.numero_factura = _extract_from_lines_with_keyword(
            self.lines,
            [r'FACTURA', r'Nº Factura', r'Número de factura', r'FACTURA DE VENTA', r'Factura Número', r'Invoice No\.?'],
            r'([A-Z0-9_-]+)'
        )
        if self.numero_factura is None:
            invoice_f_slash_regex = r'(F[A-Z0-9_]+/[A-Z0-9_]+)'
            for line in self.lines:
                match = re.search(invoice_f_slash_regex, line, re.IGNORECASE)
                if match:
                    self.numero_factura = match.group(1)
                    break

    def _extract_emisor(self):
        """
        Extracts the issuer's name (supplier) using common patterns.
        This method will be overridden by specific classes.
        """
        # Tries to find the company name near the top of the document
        # or near keywords like "CIF", "NIF", "Tlf", "e-mail"
        for i, line in enumerate(self.lines[:10]): # Limit search to the first 10 lines
            # Look for company name patterns (uppercase, S.L., S.A., etc.)
            emisor_match = re.search(r'([A-Z\s.,&/-]+(?:S\.L\.|S\.A\.|S\.L\.U|C\.B\.|C\.P\.)?)', line)
            if emisor_match and len(emisor_match.group(1).strip()) > 5: # Avoid capturing very short strings
                self.emisor = emisor_match.group(1).strip()
                # If we find a CIF/NIF on the same line or nearby, we consider it a good indication of the issuer
                if _extract_nif_cif(line):
                    break
                # Also search near keywords that are usually with the issuer
                for sub_line in self.lines[max(0, i-2):i+3]: # Search in a small range around
                    if re.search(r'(CIF|NIF|Tlf|e-mail|Teléfono|Dirección|C\.I\.F\.)', sub_line, re.IGNORECASE):
                        break # We found an issuer context, the emisor_match is probably correct
                if self.emisor != "No encontrado":
                    break
        # If not found with a company pattern, try generic patterns that were previously used for client
        if self.emisor == "No encontrado":
            for line in self.lines[:10]: # Retry in the first lines
                # Look for a name that is not "CLIENTE" or "CUSTOMER" if they are present
                if re.search(r'^\s*(?!CLIENTE|CUSTOMER)(?P<emisor_name>[A-Z\s.,&/-]+(?:S\.L\.|S\.A\.|S\.L\.U|C\.B\.|C\.P\.)?)\s*$', line, re.IGNORECASE):
                     self.emisor = re.match(r'^\s*(?!CLIENTE|CUSTOMER)(?P<emisor_name>[A-Z\s.,&/-]+(?:S\.L\.|S\.A\.|S\.L\.U|C\.B\.|C\.P\.)?)\s*$', line, re.IGNORECASE).group('emisor_name').strip()
                     if len(self.emisor) > 5: # Ensure it's not a very short string
                         break

    def _extract_cif(self):
        """
        Extracts the issuer's CIF using common patterns,
        ignoring the fixed client CIF (B85629020).
        """
        for line in self.lines:
            extracted_cif = _extract_nif_cif(line)
            if extracted_cif:
                # Ignore the client's CIF if found
                if extracted_cif == "B85629020":
                    continue # Skip to the next line
                self.cif = extracted_cif
                break

    def _extract_modelo(self):
        """Extracts the vehicle model using common patterns."""
        for line in self.lines:
            modelo_match = re.search(r'Modelo\s*:\s*(.*)|Model\s*:\s*(.*)', line, re.IGNORECASE)
            if modelo_match:
                self.modelo = (modelo_match.group(1) or modelo_match.group(2)).strip()
                break
            if self.modelo is None:
                car_model_pattern = r'(\d{9,15})(RENAULT|VOLKSWAGEN|FORD|BMW|MERCEDES|AUDI|SEAT|OPEL)\s*([A-Z0-9\s-]+)?'
                model_in_line_match = re.search(car_model_pattern, line, re.IGNORECASE)
                if model_in_line_match:
                    self.modelo = (model_in_line_match.group(2) + " " + (model_in_line_match.group(3) or "")).strip()
                    break

    def _extract_matricula(self):
        """Extracts the license plate using common patterns."""
        for line in self.lines:
            matricula_pattern = r'(\d{4}\s*[A-Z]{3})' # New Spanish format (e.g., 1234 ABC)
            match_plate = re.search(matricula_pattern, line, re.IGNORECASE)
            if match_plate:
                self.matricula = match_plate.group(1).strip()
                break
            else:
                matricula_match_generic = re.search(r'\b([A-Z0-9]{4,8}[A-Z]{0,3})\b', line, re.IGNORECASE)
                if matricula_match_generic and len(matricula_match_generic.group(1)) >= 6:
                    self.matricula = matricula_match_generic.group(1).strip()
                    break
                specific_plate_pattern = r'(\d{4}[A-Z]{3})\s*$' # Pattern for '2416KZM'
                specific_match = re.search(specific_plate_pattern, line, re.IGNORECASE)
                if specific_match:
                    self.matricula = specific_match.group(1).strip()
                    break

    def _extract_importe_and_base(self):
        """Extracts the total amount and calculates the taxable base using common patterns."""
        for line in self.lines:
            if re.search(r'Total Factura|Importe Total|Total a pagar|Amount Due|TOTAL FACTURA|TOTAL', line, re.IGNORECASE):
                extracted_total_amount_str = _extract_amount(line)
                if extracted_total_amount_str:
                    self.importe = extracted_total_amount_str
                    self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)
                    break

# --- Specific Extractor Classes (inherit from BaseInvoiceExtractor) ---

class AutodocExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        # self.cliente is already "NEW SATELITE, S.L." by default
        # self.emisor will be set here

    def _extract_emisor(self):
        # For Autodoc, the issuer is "AUTODOC SE"
        self.emisor = "AUTODOC SE"

    def _extract_numero_factura(self):
        self.numero_factura = _extract_from_lines_with_keyword(self.lines, r'Número de factura:', r'(\d{6,})')

    def _extract_fecha(self):
        self.fecha = _extract_from_lines_with_keyword(self.lines, r'Fecha de factura:', r'(\d{2}[\./]\d{2}[\./]\d{4})')

    def _extract_importe_and_base(self):
        for i, line in enumerate(self.lines):
            if 'Importe total bruto' in line and i + 1 < len(self.lines):
                self.importe = _extract_amount(self.lines[i+1])
                if self.importe:
                    self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)
                    break

class StellantisExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        # self.cliente is already "NEW SATELITE, S.L." by default

    def _extract_emisor(self):
        # For Stellantis, the issuer is "PPCR MADRID"
        self.emisor = "PPCR MADRID"

    def _extract_numero_factura(self):
        self.numero_factura = _extract_from_lines_with_keyword(self.lines, r'N° Factura', r'(\d{6,})')

    def _extract_fecha(self):
        self.fecha = _extract_from_lines_with_keyword(self.lines, r'(\d{2}/\d{2}/\d{4})', r'(\d{2}/\d{2}/\d{4})')

    def _extract_importe_and_base(self):
        for line in self.lines:
            if 'Total Factura' in line:
                self.importe = _extract_amount(line, is_stellantis=True)
                if self.importe:
                    self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)
                    break
    
    def _extract_cif(self):
        for line in self.lines:
            if re.search(r'- NIF:', line, re.IGNORECASE):
                extracted_cif = _extract_nif_cif(line)
                if extracted_cif and extracted_cif != "B85629020":
                    self.cif = extracted_cif
                    break

class BrildorExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        # self.cliente is already "NEW SATELITE, S.L." by default

    def _extract_emisor(self):
        # For Brildor, the issuer is "Brildor SL"
        self.emisor = "Brildor SL"

    def _extract_numero_factura(self):
        self.numero_factura = _extract_from_lines_with_keyword(self.lines, r'Factura', r'(\d{6,})', look_ahead=2)

    def _extract_fecha(self):
        self.fecha = _extract_from_lines_with_keyword(self.lines, r'Fecha', r'(\d{2}/\d{2}/\d{4})', look_ahead=1)

    def _extract_importe_and_base(self):
        for i, line in enumerate(self.lines):
            if 'Total' in line and i + 1 < len(self.lines):
                self.importe = _extract_amount(self.lines[i+1])
                if self.importe:
                    self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)
                    break
    
    def _extract_cif(self):
        for line in self.lines:
            if re.search(r'Brildor SL', line, re.IGNORECASE):
                extracted_cif = _extract_nif_cif(line)
                if extracted_cif and extracted_cif != "B85629020":
                    self.cif = extracted_cif
                    break
            if self.cif is None: 
                super()._extract_cif() 


class HermanasExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        # self.cliente is already "NEW SATELITE, S.L." by default

    def _extract_emisor(self):
        # For Hermanas, the issuer is "Hermanas del Amor de Dios Casa General"
        self.emisor = "Hermanas del Amor de Dios Casa General"

    def _extract_numero_factura(self):
        self.numero_factura = _extract_from_lines_with_keyword(self.lines, r'FACTURA', r'([A-Z]{2}-\d{2}/\d{4})', look_ahead=6)

    def _extract_fecha(self):
        self.fecha = _extract_from_lines_with_keyword(self.lines, r'Fecha', r'(\d{2}/\d{2}/\d{4})')

    def _extract_importe_and_base(self):
        for line in self.lines:
            if 'CONCEPTO IMPORTE' in line:
                self.importe = _extract_amount(line)
            elif "CIF: B85629020" in line:
                self.importe = _extract_amount(line)
            if self.importe:
                self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)
                break
    
    def _extract_cif(self):
        for line in self.lines:
            if re.search(r'C.I.F.:', line, re.IGNORECASE):
                extracted_cif = _extract_nif_cif(line)
                if extracted_cif and extracted_cif != "B85629020":
                    self.cif = extracted_cif
                    break

class KiautoExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        # self.cliente is already "NEW SATELITE, S.L." by default

    def _extract_emisor(self):
        # For Kiauto, the issuer is "AUTOLUX RECAMBIOS S.L"
        self.emisor = "AUTOLUX RECAMBIOS S.L"

    def _extract_numero_factura(self):
        self.numero_factura = _extract_from_lines_with_keyword(self.lines, r'factura', r'(\d{2}\.\d{3}\.\d{3})', look_ahead=1)

    def _extract_fecha(self):
        self.fecha = _extract_from_lines_with_keyword(self.lines, r'Fecha factura', r'(\d{2}[-/]\d{2}[-/]\d{4})', look_ahead=1)

    def _extract_importe_and_base(self):
        for i, line in enumerate(self.lines):
            if re.search(r'TOTAL FACTURA', line, re.IGNORECASE) and i + 2 < len(self.lines):
                self.importe = _extract_amount(self.lines[i+2])
                if self.importe:
                    self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)
                    break
    
    def _extract_cif(self):
        for line in self.lines:
            if re.search(r'AUTOLUX RECAMBIOS S\.L', line, re.IGNORECASE):
                extracted_cif = _extract_nif_cif(line)
                if extracted_cif and extracted_cif != "B85629020":
                    self.cif = extracted_cif
                    break


class SumautoExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        # self.cliente is already "NEW SATELITE, S.L." by default

    def _extract_emisor(self):
        # For Sumauto, the issuer is "Sumauto Motor, S.L."
        self.emisor = "Sumauto Motor, S.L."

    def _extract_numero_factura(self):
        self.numero_factura = _extract_from_lines_with_keyword(self.lines, r'FAC', r'([A-Z0-9_]+)')

    def _extract_fecha(self):
        self.fecha = _extract_from_lines_with_keyword(self.lines, r'Fecha de expedición', r'(\d{2}/\d{2}/\d{4})')

    def _extract_importe_and_base(self):
        for line in self.lines:
            if re.search(r'TOTAL TARIFA', line, re.IGNORECASE):
                self.importe = _extract_amount(line)
                if self.importe:
                    self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)
                    break

class PincheteExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        # self.cliente is already "NEW SATELITE, S.L." by default

    def _extract_emisor(self):
        # For Pinchete, the issuer is "RECAMBIOS PINCHETE S.L"
        self.emisor = "RECAMBIOS PINCHETE S.L"

    def _extract_numero_factura(self):
        numero_factura_regex_v2 = r'(FC\s*[A-Z0-9_]+\s*\d+)'
        self.numero_factura = _extract_from_line(self.lines[0], numero_factura_regex_v2)

    def _extract_fecha(self):
        self.fecha = _extract_from_line(self.lines[0], r'(\d{2}/\d{2}/\d{4})')

    def _extract_importe_and_base(self):
        for i, line in enumerate(self.lines):
            if re.search(r'Imp.:', line, re.IGNORECASE):
                self.importe = _extract_amount(line)
                if self.importe:
                    self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)
                    break

class RefialiasExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        # self.cliente is already "NEW SATELITE, S.L." by default

    def _extract_emisor(self):
        # For Refialias, the issuer is "REFIALIAS S.L"
        self.emisor = "REFIALIAS S.L"

    def _extract_numero_factura(self):
        self.numero_factura = _extract_from_lines_with_keyword(
            self.lines, r'FACTURA :', r'FACTURA\s*:\s*([A-Z0-9_/]+)'
        )

    def _extract_fecha(self):
        fecha_regex_pattern = r'(\d{2}-\d{2}-\d{2})'
        self.fecha = _extract_from_lines_with_keyword(
            self.lines, fecha_regex_pattern, fecha_regex_pattern
        )

    def _extract_importe_and_base(self):
        for i, line in enumerate(self.lines):
            if re.search(r'I.V.A. TOTAL', line, re.IGNORECASE):
                self.importe = _extract_amount(self.lines[i+1])
                if self.importe:
                    self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)
                    break

class LeroyExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        # self.cliente is already "NEW SATELITE, S.L." by default

    def _extract_emisor(self):
        # For Leroy, the issuer is "Leroy Merlin Espana S.L.U"
        self.emisor = "Leroy Merlin Espana S.L.U"

    def _extract_numero_factura(self):
        self.numero_factura = _extract_from_lines_with_keyword(
            self.lines, r'Ejemplar clienteFACTURA', r'Ejemplar\s*clienteFACTURA\s*([A-Z0-9_/-]+)'
        )

    def _extract_fecha(self):
        self.fecha = _extract_from_lines_with_keyword(
            self.lines, r'Fecha de venta:', r'(\d{2}/\d{2}/\d{4})', look_ahead=0
        )

    def _extract_importe_and_base(self):
        for i, line in enumerate(self.lines):
            if re.search(r'CAMBIO', line, re.IGNORECASE):
                self.importe = _extract_amount(self.lines[i+1])
                if self.importe:
                    self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)
                    break

class PoyoExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        # self.cliente is already "NEW SATELITE, S.L." by default

    def _extract_emisor(self):
        # For Poyo, the issuer is "PEDRO GARRIDO RODRÍGUEZ"
        self.emisor = "PEDRO GARRIDO RODRÍGUEZ"

    def _extract_numero_factura(self):
        invoice_regex = r'(F[A-Z0-9_]+/[A-Z0-9_]+)'
        for line in self.lines:
            match = re.search(invoice_regex, line, re.IGNORECASE)
            if match:
                self.numero_factura = match.group(1)
                break

    def _extract_fecha(self):
        date_regex = r'(\d{2}/\d{2}/\d{4})'
        for line in self.lines:
            match = re.search(date_regex, line)
            if match:
                self.fecha = match.group(1)
                break
    
    def _extract_cif(self):
        for line in self.lines:
            if re.search(r'DNI:', line, re.IGNORECASE):
                extracted_cif = _extract_nif_cif(line)
                if extracted_cif and extracted_cif != "B85629020":
                    self.cif = extracted_cif
                    break

    def _extract_importe_and_base(self):
        for i, line in enumerate(self.lines):
            if re.search(r'TOTAL', line, re.IGNORECASE):
                self.importe = _extract_amount(self.lines[i+1])
                if self.importe:
                    self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)
                    break

class LacaravanaExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        # self.cliente is already "NEW SATELITE, S.L." by default

    def _extract_emisor(self):
        # For Lacaravana, the issuer is "LA CARAVANA SL"
        self.emisor = "LA CARAVANA SL"

    def _extract_numero_factura(self):
        invoice_regex = r'(F-[A-Z0-9_]+-[A-Z0-9_]+)'
        for line in self.lines:
            if re.search("lacaravana", line, re.IGNORECASE): # Search for "lacaravana" keyword
                match = re.search(invoice_regex, line, re.IGNORECASE)
                if match:
                    self.numero_factura = match.group(1)
                    break

    def _extract_fecha(self):
        date_regex = r'(\d{2}/\d{2}/\d{4})'
        for line in self.lines:
            match = re.search(date_regex, line)
            if match:
                self.fecha = match.group(1)
                break

    def _extract_importe_and_base(self):
        for i, line in enumerate(self.lines):
            if re.search(r'TOTAL :', line, re.IGNORECASE):
                self.importe = _extract_amount(self.lines[i+1])
                if self.importe:
                    self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)
                    break

class MalagaExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        # self.cliente is already "NEW SATELITE, S.L." by default

    def _extract_emisor(self):
        # For Malaga, the issuer is "EURO DESGUACES MALAGA S.L"
        self.emisor = "EURO DESGUACES MALAGA S.L"

    def _extract_numero_factura(self):
        invoice_regex = r'([0-9]+\s+\d{6,})'
        for line in self.lines:
            if re.search("Madrid1", line, re.IGNORECASE): # Specific keyword for this invoice
                match = re.search(invoice_regex, line, re.IGNORECASE)
                if match:
                    self.numero_factura = match.group(1)
                    break

    def _extract_fecha(self):
        date_regex = r'(\d{2}/\d{2}/\d{4})'
        for i, line in enumerate(self.lines):
            if re.search("Madrid1", line, re.IGNORECASE): # Specific keyword
                match = re.search(date_regex, self.lines[i+1])
                if match:
                    self.fecha = match.group(1)
                    break
    
    def _extract_cif(self):
        for line in self.lines:
            if re.search("C.I.F.", line, re.IGNORECASE):
                extracted_cif = _extract_nif_cif(line)
                if extracted_cif and extracted_cif != "B85629020":
                    self.cif = extracted_cif
                    break

    def _extract_importe_and_base(self):
        if self.lines: # The amount is on the last line
            last_line = self.lines[-1]
            self.importe = _extract_amount(last_line)
            if self.importe:
                self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)


class BeroilExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        # self.cliente is already "NEW SATELITE, S.L." by default

    def _extract_emisor(self):
        # For Beroil, the issuer is "BEROIL, S.L.U"
        # We search for "BEROIL, S.L.U" which is usually at the beginning
        for line in self.lines:
            if re.search(r"BEROIL,\s*S\.L\.U", line, re.IGNORECASE):
                self.emisor = "BEROIL, S.L.U"
                break

    def _extract_numero_factura(self):
        invoice_regex = r"FACTURA NÚM:\s*([A-Z0-9_ -]+)"
        for line in self.lines:
            if re.search("FACTURA NÚM:", line, re.IGNORECASE):
                match = re.search(invoice_regex, line, re.IGNORECASE)
                if match:
                    self.numero_factura = match.group(1)
                    break

    def _extract_fecha(self):
        super()._extract_fecha()
        if self.fecha is None:
            self.fecha = extract_and_format_date(self.lines)

    def _extract_cif(self):
        for line in self.lines:
            if re.search(r"NIF\s*B\d+", line, re.IGNORECASE):
                extracted_cif = _extract_nif_cif(line)
                if extracted_cif and extracted_cif != "B85629020":
                    self.cif = extracted_cif
                    break
            if self.cif is None:
                super()._extract_cif()


    def _extract_importe_and_base(self):
        for i, line in enumerate(self.lines):
            if re.search(r"FORMA DE PAGO:", line, re.IGNORECASE) and i > 0:
                self.importe = _extract_amount(self.lines[i-1])
                if self.importe:
                    self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)
                    break

class AutocasherExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        # self.cliente is already "NEW SATELITE, S.L." by default

    def _extract_emisor(self):
        # For Autocasher, the issuer is "AUTOCASHER PILAS, SL"
        self.emisor = "AUTOCASHER PILAS, SL"

    def _extract_numero_factura(self):
        invoice_regex = r"B-85629020\s*([A-Z0-9_ -]+)"
        for line in self.lines:
            match = re.search(invoice_regex, line, re.IGNORECASE)
            if match:
                self.numero_factura = match.group(1)
                break

    def _extract_fecha(self):
        self.fecha = _extract_from_lines_with_keyword(self.lines, r'(\d{2}[-/]\d{2}[-/]\d{4})', r'(\d{2}[-/]\d{2}[-/]\d{4})')
        if self.fecha is None:
            self.fecha = extract_and_format_date(self.lines)

    def _extract_cif(self):
        for line in self.lines:
            if re.search("CIF:", line, re.IGNORECASE):
                extracted_cif = _extract_nif_cif(line)
                if extracted_cif and extracted_cif != "B85629020":
                    self.cif = extracted_cif
                    break

    def _extract_importe_and_base(self):
        for i, line in enumerate(self.lines):
            if re.search(r"TOTAL  FACTURA", line, re.IGNORECASE) and i + 1 < len(self.lines):
                self.importe = _extract_amount(self.lines[i+1])
                if self.importe:
                    self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)
                    break

class CesvimapExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        # self.cliente is already "NEW SATELITE, S.L." by default

    def _extract_emisor(self):
        # For Cesvimap, the issuer is "CENTRO DE EXPERIMENTACIÓN Y SEGURIDAD VIAL MAPFRE"
        self.emisor = "CENTRO DE EXPERIMENTACIÓN Y SEGURIDAD VIAL MAPFRE"

    def _extract_numero_factura(self):
        invoice_regex = r"R-(\d+)"
        for line in self.lines:
            match = re.search(invoice_regex, line, re.IGNORECASE)
            if match:
                self.numero_factura = match.group(1)
                break

    def _extract_fecha(self):
        self.fecha = _extract_from_lines_with_keyword(self.lines, r'(\d{2}[-/]\d{2}[-/]\d{4})', r'(\d{2}[-/]\d{2}[-/]\d{4})')
        if self.fecha is None:
            self.fecha = extract_and_format_date(self.lines)

    def _extract_cif(self):
        for line in self.lines:
            if re.search("NIF:", line, re.IGNORECASE):
                extracted_cif = _extract_nif_cif(line)
                if extracted_cif and extracted_cif != "B85629020":
                    self.cif = extracted_cif
                    break

    def _extract_importe_and_base(self):
        for line in self.lines:
            if re.search(r"TOTAL\s*", line, re.IGNORECASE):
                self.importe = _extract_amount(line)
                if self.importe:
                    self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)
                    break

class FielExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        # self.cliente is already "NEW SATELITE, S.L." by default

    def _extract_emisor(self):
        # For Fiel, the issuer is "COMBUSTIBLES FIEL, S.L."
        for line in self.lines:
            if re.search(r"COMBUSTIBLES FIEL,\s*S\.L\.", line, re.IGNORECASE):
                self.emisor = "COMBUSTIBLES FIEL, S.L."
                break

    def _extract_numero_factura(self):
        invoice_regex = r"M(\d+)\s+(\d+)"
        for line in self.lines:
            match = re.search(invoice_regex, line, re.IGNORECASE)
            if match:
                self.numero_factura = f"M{match.group(1)} {match.group(2)}"
                break

    def _extract_fecha(self):
        self.fecha = _extract_from_lines_with_keyword(self.lines, r'(\d{2}[-/]\d{2}[-/]\d{4})', r'(\d{2}[-/]\d{2}[-/]\d{4})')
        if self.fecha is None:
            self.fecha = extract_and_format_date(self.lines)

    def _extract_cif(self):
        for line in self.lines:
            if re.search(r"Cif:\s*([A-Z]\d+)", line, re.IGNORECASE):
                extracted_cif = _extract_nif_cif(line)
                if extracted_cif and extracted_cif != "B85629020":
                    self.cif = extracted_cif
                    break
            if self.cif is None:
                super()._extract_cif()


    def _extract_importe_and_base(self):
        for line in self.lines:
            if re.search(r"Total factura\s*", line, re.IGNORECASE):
                self.importe = _extract_amount(line)
                if self.importe:
                    self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)
                    break

class PradillaExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        # self.cliente is already "NEW SATELITE, S.L." by default
        self.cif = "B-80481369" # Fixed CIF for this issuer

    def _extract_emisor(self):
        # For Pradilla, the issuer is "GESTORIA PRADILLA, S.L."
        self.emisor = "GESTORIA PRADILLA, S.L."

    def _extract_numero_factura(self):
        invoice_regex = r"(\d+)"
        for i, line in enumerate(self.lines):
            if re.search(r"NºFACTURA", line, re.IGNORECASE) and i + 2 < len(self.lines):
                match = re.search(invoice_regex, self.lines[i+2], re.IGNORECASE)
                if match:
                    self.numero_factura = match.group(1)
                    break

    def _extract_fecha(self):
        for i, line in enumerate(self.lines):
            if re.search(r"FECHA", line, re.IGNORECASE) and i + 2 < len(self.lines):
                self.fecha = _extract_from_line(self.lines[i+2], r'(\d{2}[-/]\d{2}[-/]\d{4})')
                if self.fecha is None:
                    self.fecha = extract_and_format_date([self.lines[i+2]])
                if self.fecha:
                    break

    def _extract_importe_and_base(self):
        for i, line in enumerate(self.lines):
            if re.search(r"TOTAL A PAGAR", line, re.IGNORECASE) and i + 1 < len(self.lines):
                self.importe = _extract_amount(self.lines[i+1])
                if self.importe:
                    self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)
                    break

class BoxesExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path): # pdf_path is needed for this class
        super().__init__(lines, pdf_path)
        # self.cliente is already "NEW SATELITE, S.L." by default
        self.cif = "B-84962851" # Fixed CIF for this issuer

    def _extract_emisor(self):
        # For Boxes, the issuer is "BOXES INTEGRALCAR, S.L"
        self.emisor = "BOXES INTEGRALCAR, S.L"

    def _extract_numero_factura(self):
        if self.pdf_path:
            nombre_archivo = os.path.basename(self.pdf_path)
            match_invoice_num = re.search(r'FRA(\d+)-', nombre_archivo, re.IGNORECASE)
            if match_invoice_num:
                self.numero_factura = match_invoice_num.group(1)

    def _extract_fecha(self):
        for line in self.lines:
            if re.search(r"Conforme Cliente", line, re.IGNORECASE):
                self.fecha = _extract_from_line(line, r'(\d{2}[-/]\d{2}[-/]\d{4})')
                if self.fecha:
                    break
    
    def _extract_modelo(self):
        # For Boxes, the model is on a line like "Modelo: CAPTUR"
        for line in self.lines:
            modelo_match = re.search(r'Modelo:\s*(.*)', line, re.IGNORECASE)
            if modelo_match:
                self.modelo = modelo_match.group(1).strip()
                break

    def _extract_matricula(self):
        # For Boxes, the license plate is on a line like "Matrícula: 2416KZM"
        for line in self.lines:
            matricula_match = re.search(r'Matrícula:\s*([A-Z0-9]+)', line, re.IGNORECASE)
            if matricula_match:
                self.matricula = matricula_match.group(1).strip()
                break

    def _extract_importe_and_base(self):
        for line in self.lines:
            if re.search(r"TOTAL FACTURA", line, re.IGNORECASE):
                self.importe = _extract_amount(line)
                if self.importe:
                    self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)
                    break

class HergarExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        # self.cliente is already "NEW SATELITE, S.L." by default
        self.cif = "A-78009172" # Fixed CIF for this issuer

    def _extract_emisor(self):
        # For Hergar, the issuer is "GESTIÓN DE RESIDUOS S.A."
        self.emisor = "GESTIÓN DE RESIDUOS S.A."

    def _extract_numero_factura(self):
        invoice_regex = r"(\d+)"
        for line in self.lines:
            if re.search(r"Nº\.", line, re.IGNORECASE):
                match = re.search(invoice_regex, line, re.IGNORECASE)
                if match:
                    self.numero_factura = match.group(1)
                    break

    def _extract_fecha(self):
        for line in self.lines:
            if re.search(r"FECHA:", line, re.IGNORECASE):
                self.fecha = _extract_from_line(line, r'(\d{2}[-/]\d{2}[-/]\d{4})')
                if self.fecha:
                    break

    def _extract_importe_and_base(self):
        for i, line in enumerate(self.lines):
            if re.search(r"TOTAL FACTURA\s*", line, re.IGNORECASE) and i + 1 < len(self.lines):
                self.importe = _extract_amount(self.lines[i+1])
                if self.importe:
                    self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)
                    break

class MusasExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        # self.cliente is already "NEW SATELITE, S.L." by default
        self.cif = "B81583445" # Fixed CIF for this issuer

    def _extract_emisor(self):
        # For Musas, the issuer is "LasMusas, S.L."
        self.emisor = "LasMusas, S.L."

    def _extract_numero_factura(self):
        invoice_regex = r"([A-Z0-9\s]+)"
        for i, line in enumerate(self.lines):
            if re.search(r"FACTURA Nº", line, re.IGNORECASE) and i + 1 < len(self.lines):
                match = re.search(invoice_regex, self.lines[i+1], re.IGNORECASE)
                if match:
                    self.numero_factura = match.group(1)
                    break

    def _extract_fecha(self):
        for line in self.lines:
            if re.search(r"Fecha", line, re.IGNORECASE):
                self.fecha = _extract_from_line(line, r'(\d{2}[-/]\d{2}[-/]\d{4})')
                if self.fecha:
                    break
    
    def _extract_cif(self):
        for line in self.lines:
            extracted_cif = _extract_nif_cif(line)
            if extracted_cif and extracted_cif != "B85629020":
                self.cif = extracted_cif
                break

    def _extract_importe_and_base(self):
        for i, line in enumerate(self.lines):
            if re.search(r"TOTAL A", line, re.IGNORECASE) and i + 1 < len(self.lines):
                self.importe = _extract_amount(self.lines[i+1])
                if self.importe:
                    self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)
                    break

class AemaExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        # self.cliente is already "NEW SATELITE, S.L." by default

    def _extract_emisor(self):
        # For Aema, the issuer is "NEUMÁTICOS AEMA, S.A."
        for line in self.lines:
            if re.search(r"NEUMÁTICOS AEMA,\s*S\.A\.", line, re.IGNORECASE):
                self.emisor = "NEUMÁTICOS AEMA, S.A."
                break

    def _extract_numero_factura(self):
        invoice_regex = r"Número:([A-Z0-9-]+)\s*FACTURA DE VENTA"
        for line in self.lines:
            if re.search(r"Número:FACTURA DE VENTA", line, re.IGNORECASE):
                match = re.search(invoice_regex, line, re.IGNORECASE)
                if match:
                    self.numero_factura = match.group(1)
                    break

    def _extract_fecha(self):
        for line in self.lines:
            if re.search(r"Fecha:", line, re.IGNORECASE):
                self.fecha = _extract_from_line(line, r'(\d{2}[-/]\d{2}[-/]\d{4})')
                if self.fecha:
                    break
    
    def _extract_cif(self):
        for line in self.lines:
            extracted_cif = _extract_nif_cif(line)
            if extracted_cif and extracted_cif != "B85629020":
                self.cif = extracted_cif
                break

    def _extract_importe_and_base(self):
        for i, line in enumerate(self.lines):
            if re.search(r"Retención", line, re.IGNORECASE) and i + 1 < len(self.lines):
                self.importe = _extract_amount(self.lines[i+1]).replace('.', '')
                if self.importe:
                    self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)
                    break

class AutodescuentoExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        # self.cliente is already "NEW SATELITE, S.L." by default

    def _extract_emisor(self):
        # For Autodescuento, the issuer is "AUTODESCUENTO SL"
        for line in self.lines:
            if re.search(r"AUTODESCUENTO\s*SL", line, re.IGNORECASE):
                self.emisor = "AUTODESCUENTO SL"
                break

    def _extract_numero_factura(self):
        invoice_number_regex = r'(\d+)\s*$'
        for i, line in enumerate(self.lines):
            if re.search(r"Número", line, re.IGNORECASE) and i + 1 < len(self.lines):
                match = re.search(invoice_number_regex, self.lines[i+1])
                if match:
                    self.numero_factura = match.group(1)
                    break

    def _extract_fecha(self):
        for i, line in enumerate(self.lines):
            if re.search(r"Fecha\s*$", line, re.IGNORECASE) and i + 1 < len(self.lines):
                date_match = re.search(r'(\d{2}[-/]\d{2}[-/]\d{4})', self.lines[i+1])
                if date_match:
                    self.fecha = date_match.group(1)
                    break
    
    def _extract_cif(self):
        for line in self.lines:
            if re.search(r"CIF.: ", line, re.IGNORECASE):
                extracted_cif = _extract_nif_cif(line)
                if extracted_cif and extracted_cif != "B85629020":
                    self.cif = extracted_cif
                    break

    def _extract_importe_and_base(self):
        for line in self.lines:
            if re.search(r"Forma de pago Líquido\(EUR\):", line, re.IGNORECASE):
                amount_match = re.search(r'^([\d\.,]+)', line.strip())
                if amount_match:
                    importe_str = amount_match.group(1)
                    self.importe = _extract_amount(importe_str)
                    if self.importe:
                        self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)
                        break

class NorthgateExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)

    def _extract_emisor(self):
        # For Northgate, the issuer is "NORTHGATE ESPAÑA RENTING FLEXIBLE S.A."
        for line in self.lines:
            if re.search(r"NORTHGATE ESPAÑA RENTING FLEXIBLE S\.A\.", line, re.IGNORECASE):
                self.emisor = "NORTHGATE ESPAÑA RENTING FLEXIBLE S.A."
                break

    def _extract_numero_factura(self):
        # The debug output shows "FACTURA Nº" on Line 3, and the number "VO-2025005930" on Line 5.
        # Find "FACTURA Nº" and then look two lines ahead.
        for i, line in enumerate(self.lines):
            if re.search(r"FACTURA N°", line, re.IGNORECASE) and i + 2 < len(self.lines):
                # Extract the invoice number from Line i + 2 (Line 5 in debug output)
                invoice_number_line = self.lines[i+2]
                invoice_regex = r"([A-Z0-9-]+NORTHGATE\s*ESPAÑA\s*RENTING\s*FLEXIBLE\s*S\.A\.)"
                match = re.search(invoice_regex, invoice_number_line, re.IGNORECASE)
                if match:
                    # The number is embedded with the company name, we need to extract just the number
                    # The debug output was "VO-2025005930NORTHGATE ESPAÑA RENTING FLEXIBLE S.A."
                    # We need to grab only the part before "NORTHGATE"
                    num_match = re.match(r"([A-Z0-9-]+)", match.group(1))
                    if num_match:
                        self.numero_factura = num_match.group(1).strip()
                        break
        if self.numero_factura is None:
            # Fallback to generic if specific fails
            super()._extract_numero_factura()

    def _extract_fecha(self):
        # The debug output shows "29/05/25B85629020..." on Line 1.
        # Extract the date from Line 1.
        if len(self.lines) > 1:
            date_line = self.lines[1]
            date_regex = r"(\d{2}/\d{2}/\d{2})"
            match = re.search(date_regex, date_line)
            if match:
                # Convert YY to YYYY
                year_short = match.group(1).split('/')[-1]
                if len(year_short) == 2:
                    full_date = match.group(1)[:-2] + "20" + year_short
                    self.fecha = full_date
                else:
                    self.fecha = match.group(1)
        if self.fecha is None:
            # Fallback to generic if specific fails
            super()._extract_fecha()

    def _extract_modelo(self):
        # Extract model from "RENAULT KANGOO EXPRESS 1.5 DCI 55KW PROFESIONAL E6 (75CV)" on line 11
        for i, line in enumerate(self.lines):
            if "RENAULT KANGOO EXPRESS" in line and i == 11:
                # Regex to capture the model from this specific line
                model_regex = r'([\d\.,]+)?\s*(RENAULT KANGOO EXPRESS 1\.5 DCI 55KW PROFESIONAL E6 \(75CV\))'
                match = re.search(model_regex, line, re.IGNORECASE)
                if match:
                    self.modelo = match.group(2).strip()
                    break
        if self.modelo is None:
            super()._extract_modelo()


    def _extract_matricula(self):
        # Extract license plate from "2343-LGT" which is on line 10
        for i, line in enumerate(self.lines):
            if i == 10:
                matricula_regex = r'([A-Z0-9-]+)'
                match = re.search(matricula_regex, line, re.IGNORECASE)
                if match:
                    self.matricula = match.group(1).strip()
                    break
        if self.matricula is None:
            super()._extract_matricula()


    def _extract_cif(self):
        # Extract CIF from "CIF/NIF: A28659423" on line 9
        for i, line in enumerate(self.lines):
            if i == 9 and "CIF/NIF:" in line:
                extracted_cif = _extract_nif_cif(line)
                if extracted_cif and extracted_cif != "B85629020":
                    self.cif = extracted_cif
                    break
        if self.cif is None:
            super()._extract_cif()

    def _extract_importe_and_base(self):
        # Extract total amount from "TOTAL FACTURA 7.470,01 6.173,56" on line 19
        for i, line in enumerate(self.lines):
            if i == 19 and "TOTAL FACTURA" in line:
                values = re.findall(r'(\d+(?:[.,]\d{3})*[.,]\d{2})', line)
                if len(values) >= 2:
                    self.importe = values[0]
                    self.base_imponible = values[1]
                break
        if self.importe is None or self.base_imponible is None:
            super()._extract_importe_and_base()

# --- Mapping of Extraction Classes ---
EXTRACTION_CLASSES = {
    "autodoc": AutodocExtractor,
    "stellantis": StellantisExtractor,
    "brildor": BrildorExtractor,
    "hermanas": HermanasExtractor,
    "kiauto": KiautoExtractor,
    "sumauto": SumautoExtractor,
    "amor": HermanasExtractor,
    "pinchete": PincheteExtractor,
    "refialias": RefialiasExtractor,
    "leroy": LeroyExtractor,
    "poyo": PoyoExtractor,
    "caravana": LacaravanaExtractor,
    "malaga": MalagaExtractor,
    "beroil": BeroilExtractor,
    "autocasher": AutocasherExtractor,
    "cesvimap": CesvimapExtractor,
    "fiel": FielExtractor,
    "pradilla": PradillaExtractor,
    "boxes": BoxesExtractor,
    "hergar": HergarExtractor,
    "musas": MusasExtractor,
    "muas": MusasExtractor,
    "aema": AemaExtractor,
    "autodescuento": AutodescuentoExtractor,
    "northgate": NorthgateExtractor
}

# --- Main PDF Processing Logic ---

def extraer_datos(pdf_path, debug_mode=False):
    """ Detects the invoice type and applies the correct extraction class. """
    print(f"✅ Entering extraer_datos() with file: {pdf_path} and debug_mode: {debug_mode}")
    
    try:
        with open(pdf_path, 'rb') as archivo:
            pdf = PyPDF2.PdfReader(archivo)
            texto = ''
            for pagina in pdf.pages:
                texto += pagina.extract_text() or ''
            lines = texto.splitlines()
    except Exception as e:
        print(f"❌ Error reading PDF {pdf_path}: {e}")
        return "COMPRA", None, None, None, None, None, None, None, None

    if debug_mode:
        print("\n🔍 DEBUG MODE ACTIVATED: Showing all lines in file\n")
        for i, linea in enumerate(lines):
            print(f"Line {i}: {linea}")

    nombre_archivo = os.path.basename(pdf_path).lower()

    for keyword, ExtractorClass in EXTRACTION_CLASSES.items():
        if keyword in nombre_archivo:
            print(f"➡️ Detected '{keyword}' in filename. Using specific extraction function.")
            # Pass pdf_path to all classes, even if not all use it.
            extractor = ExtractorClass(lines, pdf_path) 
            return extractor.extract_all()
    
    print("➡️ No specific invoice type detected. Using generic extraction function.")
    generic_extractor = BaseInvoiceExtractor(lines)
    return generic_extractor.extract_all()

# --- Command Line Argument Parsing and CSV Output ---

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process a PDF file or all PDFs in a folder.')
    parser.add_argument('ruta', help='Path to a PDF file or a folder with PDF files')
    parser.add_argument('--debug', action='store_true', help='Activate debug mode (True/False)')
    args = parser.parse_args()

    ruta = args.ruta
    debug_mode = args.debug
    archivos_pdf = []

    if os.path.isfile(ruta) and ruta.lower().endswith('.pdf'):
        archivos_pdf.append(ruta)
    elif os.path.isdir(ruta):
        archivos_pdf = [os.path.join(ruta, archivo) for archivo in os.listdir(ruta) if archivo.lower().endswith('.pdf')]

    if not archivos_pdf:
        print("❌ No PDF files found to process.")
        exit()

    csv_path = os.path.join(os.path.dirname(ruta), 'facturas_resultado.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Archivo', 'Tipo', 'Fecha', 'Número de Factura', 'Emisor', 'Cliente', 'CIF', 'Modelo', 'Matricula', "Base", "IVA", 'Importe'])

        for archivo in archivos_pdf:
            print(f"\n--- Processing file: {os.path.basename(archivo)} ---")
            tipo, fecha, numero_factura, emisor, cliente, cif, modelo, matricula, importe, base_imponible = extraer_datos(archivo, debug_mode)
            
            formatted_importe = 'No encontrado'
            if importe is not None:
                try:
                    numeric_importe = float(str(importe).replace(',', '.')) 
                    formatted_importe = f"{numeric_importe:.2f} €".replace('.', ',')
                except ValueError:
                    formatted_importe = str(importe)

            writer.writerow([
                os.path.basename(archivo),
                tipo or 'No encontrado',
                fecha or 'No encontrada',
                numero_factura or 'No encontrado',
                emisor or 'No encontrado', # Use the issuer field
                cliente or 'No encontrado', # Use the fixed client field
                cif or 'No encontrado',
                modelo or 'No encontrado',
                matricula or 'No encontrado',
                base_imponible or 'No encontrado',
                VAT_RATE,
                formatted_importe
            ])

    print(f"\n✅ Done! Check the results file in: {csv_path}")
