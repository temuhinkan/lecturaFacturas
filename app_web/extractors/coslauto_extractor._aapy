import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _calculate_base_from_total, VAT_RATE, extract_and_format_date, _extract_from_line

class CoslautoExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None, debug_mode=False):
        super().__init__(lines, pdf_path)
        self.emisor = "COSLAUTO, SLU."
        self.cif = "B87532248"
        self.debug_mode = debug_mode
        self.cliente = None # Ensure cliente is initialized
        self.tasas=None
    def _extract_emisor(self):
        # Emisor is fixed as per user's request
        pass

    def _extract_cif(self):
        # CIF is fixed as per user's request
        pass

    def _extract_numero_factura(self):
        # The invoice number is the 'registro' before the line with "REFERENCIA"
        # From COSLAUTO 2.pdf, it's 'CA2500227' associated with "Factora Cargo"
        for i, line in enumerate(self.lines):
            if "REFERENCIA" in line.upper():
                # Look at the previous lines for "Factora Cargo" and the number
                for j in range(i - 1, max(-1, i - 5), -1): # Check up to 5 lines back
                    prev_line = self.lines[j]
                    match = re.search(r"Factora Cargo\s*([A-Z0-9]+)", prev_line, re.IGNORECASE)
                    if match:
                        self.numero_factura = match.group(1).strip()
                        if self.debug_mode:
                            print(f"DEBUG: Número de factura extraído: {self.numero_factura}")
                        return
        if self.debug_mode and not self.numero_factura:
            print("DEBUG: Número de factura no encontrado con la lógica específica de Coslauto.")

    def _extract_fecha(self):
        # Date is next to "FECHA" in DD/MM/YY format
        date_pattern = r"FECHA\s*:\s*(\d{2}/\d{2}/\d{2})"
        for line in self.lines:
            match = re.search(date_pattern, line, re.IGNORECASE)
            if match:
                self.fecha = extract_and_format_date(match.group(1))
                if self.debug_mode:
                    print(f"DEBUG: Fecha extraída: {self.fecha}")
                return
        super()._extract_fecha() # Fallback to base class if not found

    def _extract_cliente(self):
        # Client is "NEW SATELITE S.L"
        client_pattern = r"NEW SATELITE S\.L"
        found_client = False
        for line in self.lines:
            match = re.search(client_pattern, line, re.IGNORECASE)
            if match:
                self.cliente = match.group(0).strip()
                found_client = True
                if self.debug_mode:
                    print(f"DEBUG: Cliente extraído: {self.cliente}")
                break # Exit loop once found

        if not found_client:
            self.cliente = "No encontrado" # Explicitly set if not found by specific logic
            if self.debug_mode:
                print("DEBUG: Cliente 'NEW SATELITE S.L' no encontrado.")

        # Removed super()._extract_cliente() to prevent the reported error.
        # This assumes BaseInvoiceExtractor's _extract_cliente is problematic or not needed here.


    def _extract_importe_and_base(self):
        # The amount is the line after "APAGAR"
        found_apagar = False
        for i, line in enumerate(self.lines):
            if found_apagar:
                # Assuming the line immediately after "APAGAR" contains the total amount
                importe_match = re.search(r"([\d.,]+\s*€)", line)
                if importe_match:
                    self.importe = _extract_amount(importe_match.group(1))
                    if self.importe is not None:
                        try:
                            numeric_importe = float(str(self.importe).replace(',', '.'))
                            # Calculate base by removing 21% from the total amount
                            self.base_imponible = _calculate_base_from_total(str(numeric_importe).replace('.', ','), VAT_RATE)
                            if self.debug_mode:
                                print(f"DEBUG: Importe extraído: {self.importe}, Base Imponible calculada: {self.base_imponible}")
                            return
                        except ValueError as e:
                            self.base_imponible = 'No encontrado'
                            if self.debug_mode:
                                print(f"DEBUG: Error al calcular la base imponible a partir del Total: {e}")
                    break # Exit loop once importe is found
            if "APAGAR" in line.upper():
                found_apagar = True

        # Fallback to the base class logic if "APAGAR" or the amount after it is not found
        if self.importe is None or self.base_imponible is None:
            if self.debug_mode:
                print("DEBUG: Importe o base no encontrados con la lógica específica de Coslauto. Recurriendo a la clase base.")
            super()._extract_importe_and_base()

    def _extract_modelo(self):
        # No specific logic provided for 'modelo', rely on base class or leave as None
        pass

    def _extract_matricula(self):
        # No specific logic provided for 'matricula', rely on base class or leave as None
        pass

    def extract_all(self):
        self._extract_emisor()
        self._extract_cif()
        self._extract_numero_factura()
        self._extract_fecha()
        self._extract_cliente()
        self._extract_importe_and_base()
        self._extract_modelo()
        self._extract_matricula()

        return (
            self.tipo,
            self.fecha,
            self.numero_factura,
            self.emisor,
            self.cliente,
            self.cif,
            self.modelo,
            self.matricula,
            self.base_imponible,
            VAT_RATE, # Assuming VAT_RATE is globally defined or passed
            self.importe
        )