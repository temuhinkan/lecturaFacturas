import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_nif_cif, _calculate_base_from_total, VAT_RATE, _extract_from_line, _extract_from_lines_with_keyword

class SumautoExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        self.emisor = "Sumauto Motor, S.L." # Set the issuer explicitly

    def _extract_emisor(self):
        # The issuer is explicitly set in __init__, so we can skip the generic search
        pass

    def _extract_numero_factura(self):
        # Invoice number is usually near "Nº factura" or "C280FP25" pattern.
        # From debug, "Nº factura" is on Line 12, and the value "C280FP25_0353097" is on Line 14.
        # We need to find "Nº factura" and then look ahead for the value.
        for i, line in enumerate(self.lines):
            if re.search(r"Nº factura", line, re.IGNORECASE):
                # The value is on line i+2 (Line 14 in debug if keyword is on Line 12)
                if i + 2 < len(self.lines):
                    target_line = self.lines[i+2]
                    match = re.search(r"(C\d{3}FP\d{2}_\d+)", target_line) # Specific pattern for Sumauto invoice number
                    if match:
                        self.numero_factura = match.group(1).strip()
                        break
        if self.numero_factura is None:
            super()._extract_numero_factura()

    def _extract_fecha(self):
        # Date of issue is usually near "Fecha de expedición:".
        # From debug, "Fecha de expedición: 09/04/2025" is on Line 15.
        for i, line in enumerate(self.lines):
            if re.search(r"Fecha de expedición:", line, re.IGNORECASE):
                match = re.search(r"Fecha de expedición:\s*(\d{2}/\d{2}/\d{4})", line)
                if match:
                    self.fecha = match.group(1).strip()
                    break
        if self.fecha is None:
            super()._extract_fecha()

    def _extract_cif(self):
        # Issuer CIF is on Line 19: "CIF B88049341"
        for i, line in enumerate(self.lines):
            if re.search(r"CIF\s*B\d+", line, re.IGNORECASE): # Search for "CIF B" pattern
                extracted_cif = _extract_nif_cif(line)
                if extracted_cif and extracted_cif != "B85629020": # Exclude client CIF
                    self.cif = extracted_cif
                    break
        if self.cif is None:
            super()._extract_cif()

    def _extract_modelo(self):
        # This type of invoice does not usually contain vehicle models.
        # Keeping it as None unless a specific pattern is identified.
        pass

    def _extract_matricula(self):
        # This type of invoice does not usually contain license plates.
        # Keeping it as None unless a specific pattern is identified.
        pass

    def _extract_importe_and_base(self):
        # Total amount and taxable base are on Line 19.
        # "111,32TOTAL TARIFA IRPF 0 %" and "92,00" (Base imponible, near B.IMPONIBLE)
        total_found = False
        base_found = False

        for i, line in enumerate(self.lines):
            # Look for lines containing "TOTAL TARIFA" or "B.IMPONIBLE"
            if re.search(r"TOTAL TARIFA", line, re.IGNORECASE) or re.search(r"B\.IMPONIBLE", line, re.IGNORECASE):
                # Extract total amount
                total_match = re.search(r"(\d+(?:[.,]\d{3})*[.,]\d{2})TOTAL TARIFA", line)
                if total_match:
                    self.importe = total_match.group(1).strip()
                    total_found = True

                # Extract base imponible
                base_match = re.search(r"B\.IMPONIBLE\s*(\d+(?:[.,]\d{3})*[.,]\d{2})", line)
                if base_match:
                    self.base_imponible = base_match.group(1).strip()
                    base_found = True
                
                if total_found and base_found:
                    break
        
        # Fallback to calculation if base not explicitly found but total is.
        if self.importe and self.base_imponible is None:
            self.base_imponible = _calculate_base_from_total(self.importe, VAT_RATE)
        
        if self.importe is None or self.base_imponible is None:
            super()._extract_importe_and_base()
