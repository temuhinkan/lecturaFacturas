import re
from utils import extract_and_format_date, _extract_amount, _extract_nif_cif, _calculate_base_from_total, VAT_RATE, _extract_from_line, _extract_from_lines_with_keyword

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
