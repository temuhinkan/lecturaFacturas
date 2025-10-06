import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_nif_cif, _extract_from_lines_with_keyword, _calculate_base_from_total, VAT_RATE

class BrildorExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)

    def _extract_emisor(self):
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
