import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_nif_cif, _calculate_base_from_total, VAT_RATE, _extract_from_line

class RecoautosExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        # self.emisor will be set in _extract_emisor method to ensure it's not overwritten
        # self.emisor = "RECOAUTOS DESGUACE PREMIUM, S.L." # Removed from __init__

    def _extract_emisor(self):
        # Explicitly set the issuer for Recoautos
        self.emisor = "RECOAUTOS DESGUACE PREMIUM, S.L."

    def _extract_numero_factura(self):
        # El número de factura está en la línea 16, ejemplo: "2025010176/FRU"
        # La línea completa es "2025010176/FRU 26/05/2025 4300054540Factura Nº Cliente Vendedor Rectifica a Nº Pedido Nº"
        for i, line in enumerate(self.lines):
            if i == 16: # Línea donde se espera el número de factura
                # Captura el primer patrón "YYYYMMDD/ABC" al inicio de la línea
                match = re.search(r"^(\d{10}/[A-Z]+)", line)
                if match:
                    self.numero_factura = match.group(1).strip()
                    break
        if self.numero_factura is None:
            super()._extract_numero_factura()

    def _extract_fecha(self):
        # La fecha está en la línea 16, ejemplo: "26/05/2025"
        # La línea completa es "2025010176/FRU 26/05/2025 4300054540Factura Nº Cliente Vendedor Rectifica a Nº Pedido Nº"
        for i, line in enumerate(self.lines):
            if i == 16: # Línea donde se espera la fecha
                # Captura el patrón de fecha DD/MM/YYYY
                match = re.search(r"(\d{2}/\d{2}/\d{4})", line)
                if match:
                    self.fecha = match.group(1).strip()
                    break
        if self.fecha is None:
            super()._extract_fecha()

    def _extract_cif(self):
        # El CIF del emisor está en la línea 2, ejemplo: "CIF: B19897925"
        for i, line in enumerate(self.lines):
            if i == 2: # Línea donde se espera el CIF del emisor
                extracted_cif = _extract_nif_cif(line)
                if extracted_cif and extracted_cif != "B85629020":
                    self.cif = extracted_cif
                    break
        if self.cif is None:
            super()._extract_cif()

        def _extract_modelo(self):
            # El modelo y la matrícula están en la línea 20
            # Línea 20: " 66,12 € 66,12 € 1,00 CREMALLERA DIRECCION RENAULT KANGOO 5478584"
            for i, line in enumerate(self.lines):
                if i == 20: # Línea donde se espera el modelo
                    match = re.search(r"RENAULT KANGOO", line, re.IGNORECASE)
                    if match:
                        self.modelo = match.group(0).strip()
                        break
            if self.modelo is None:
                super()._extract_modelo()

        def _extract_matricula(self):
            # Parece que no hay matrícula explícita en el snippet, así que mantendremos el fallback.
            super()._extract_matricula()

    def _extract_importe_and_base(self):
        # Based on debug output:
        # Line 21: SUBTOTAL % DTO BASE IMPONIBLE % RETENCIÓN RETENCIÓN IVA % IVA
        # Line 22:  21,00  13,89  0,00  66,12  66,12
        # Line 23: TOTAL FACTURA
        # Line 24:  80,01 €

        total_found = False
        base_found = False

        for i, line in enumerate(self.lines):
            if i == 23 and "TOTAL FACTURA" in line: # "TOTAL FACTURA" is on line 23
                # The total importe is on the next line (line 24)
                if i + 1 < len(self.lines):
                    self.importe = _extract_amount(self.lines[i+1])
                    if self.importe:
                        total_found = True
            
            if i == 22: # Base imponible values are on line 22
                # Extract all numeric values that look like amounts from line 22
                # Values: "21,00", "13,89", "0,00", "66,12", "66,12"
                # The base is the 4th value in the sequence (index 3)
                values_in_line = re.findall(r'\d+(?:[.,]\d{3})*[.,]\d{2}', line)
                if len(values_in_line) >= 4: # Ensure there are at least 4 values
                    self.base_imponible = values_in_line[3].strip() # 4th element (index 3) is 66,12
                    if self.base_imponible:
                        base_found = True
        
        # Fallback to calculation if base not explicitly found but total is.
        # This part of the logic ensures if the base is not found directly, it's computed.
        if total_found and not base_found:
            self.base_imponible = _calculate_base_from_total(self.importe, VAT_RATE)
        
        # If both are still None, then use generic fallback from base class
        if self.importe is None or self.base_imponible is None:
            super()._extract_importe_and_base()

