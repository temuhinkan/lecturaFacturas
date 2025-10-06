import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_from_line, _calculate_base_from_total, VAT_RATE

class HergarExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        self.cif = "A-78009172" # Fixed CIF for this issuer

    def _extract_emisor(self):
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
