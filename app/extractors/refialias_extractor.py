import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_from_lines_with_keyword, _calculate_base_from_total, VAT_RATE

class RefialiasExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)

    def _extract_emisor(self):
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
