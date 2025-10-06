import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_nif_cif, _extract_from_lines_with_keyword, _calculate_base_from_total, VAT_RATE

class HermanasExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)

    def _extract_emisor(self):
        self.emisor = "Hermanas del Amor de Dios Casa General"

    def _extract_numero_factura(self):
        self.numero_factura = _extract_from_lines_with_keyword(self.lines, r'FACTURA', r'([A-Z]{2}-\d{2}/\d{4})', look_ahead=6)

    def _extract_fecha(self):
        self.fecha = _extract_from_lines_with_keyword(self.lines, r'Fecha', r'(\d{2}/\d{2}/\d{4})')

    def _extract_importe_and_base(self):
        for line in self.lines:
            if 'CONCEPTO IMPORTE' in line:
                self.importe = _extract_amount(line)
            elif "CIF: B85629020" in line:
                self.importe = _extract_amount(line)
            if self.importe:
                self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)
                break
    
    def _extract_cif(self):
        for line in self.lines:
            if re.search(r'C.I.F.:', line, re.IGNORECASE):
                extracted_cif = _extract_nif_cif(line)
                if extracted_cif and extracted_cif != "B85629020":
                    self.cif = extracted_cif
                    break
