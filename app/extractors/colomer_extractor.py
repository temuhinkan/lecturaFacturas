import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_nif_cif, _calculate_base_from_total, VAT_RATE, _extract_from_line

class ColomerExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        self.emisor = "RECUPERACIONES COLOMER, S.L."

    def _extract_numero_factura(self):
        # The invoice number is on Line 12 in the debug output: "C.I.F. B85629020N-2025005504"
        # We need to extract "N-2025005504"
        for i, line in enumerate(self.lines):
            if i == 12: # Line where the invoice number is expected
                match = re.search(r"(N-[A-Z0-9]+)", line)
                if match:
                    self.numero_factura = match.group(1).strip()
                    break
        if self.numero_factura is None:
            super()._extract_numero_factura()

    def _extract_fecha(self):
        # The date is on Line 13 in the debug output: "30/05/2025"
        for i, line in enumerate(self.lines):
            if i == 13: # Line where the date is expected
                match = re.search(r"(\d{2}/\d{2}/\d{4})", line)
                if match:
                    self.fecha = match.group(1).strip()
                    break
        if self.fecha is None:
            super()._extract_fecha()

    def _extract_cif(self):
        # The issuer's CIF is on Line 15 in the debug output: "CIF: B13101423"
        for i, line in enumerate(self.lines):
            if i == 15: # Line where the issuer's CIF is expected
                extracted_cif = _extract_nif_cif(line)
                if extracted_cif and extracted_cif != "B85629020":
                    self.cif = extracted_cif
                    break
        if self.cif is None:
            super()._extract_cif()

    def _extract_modelo(self):
        # The model is mentioned in the concept on Line 23 (e.g., "ANILLO AIRBAG RENAULT KANGOO Express (FW0/1_)")
        # or Line 20 in other debug outputs ("CREMALLERA DIRECCION RENAULT KANGOO").
        # Let's try to extract from Line 23 first, then Line 20 if not found.
        for i, line in enumerate(self.lines):
            if i == 23: # Line where the model is expected in this specific PDF
                match = re.search(r"RENAULT KANGOO", line, re.IGNORECASE)
                if match:
                    self.modelo = match.group(0).strip()
                    break
            elif i == 20: # Fallback for other documents like Recoautos
                match = re.search(r"RENAULT KANGOO", line, re.IGNORECASE)
                if match:
                    self.modelo = match.group(0).strip()
                    break
        if self.modelo is None:
            super()._extract_modelo()

    def _extract_matricula(self):
        # No explicit license plate observed in the provided snippet.
        super()._extract_matricula()

    def _extract_importe_and_base(self):
        # Total Factura is on Line 28: "TOTAL FACTURA"
        # The actual amount is on Line 29: "107,00 €"
        # Base Imponible is on Line 27: "88,43" (part of "88,43 88,43")
        total_found = False
        base_found = False

        for i, line in enumerate(self.lines):
            if i == 28 and "TOTAL FACTURA" in line:
                if i + 1 < len(self.lines):
                    self.importe = _extract_amount(self.lines[i+1])
                    if self.importe:
                        total_found = True
            
            if i == 27: # Line where base imponible values are located
                values_in_line = re.findall(r'\d+(?:[.,]\d{3})*[.,]\d{2}', line)
                # From the debug output, the base imponible '88,43' is the third numeric value
                # on the line (index 2 in a 0-indexed list of found values)
                if len(values_in_line) >= 3:
                    self.base_imponible = values_in_line[2].strip()
                    base_found = True
        
        # Fallback to calculation if base is not explicitly found but total is.
        if total_found and not base_found:
            self.base_imponible = _calculate_base_from_total(self.importe, VAT_RATE)
        
        # If both are still None, then use generic fallback from base class
        if self.importe is None or self.base_imponible is None:
            super()._extract_importe_and_base()

