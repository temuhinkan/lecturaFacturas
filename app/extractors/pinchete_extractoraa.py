import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_from_line, _calculate_base_from_total, VAT_RATE

class PincheteExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)

    def _extract_emisor(self):
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
