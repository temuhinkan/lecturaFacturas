import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_nif_cif, _extract_from_lines_with_keyword, _calculate_base_from_total, VAT_RATE

class KiautoExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)

    def _extract_emisor(self):
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