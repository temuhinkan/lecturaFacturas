import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_nif_cif, _calculate_base_from_total, VAT_RATE

class MalagaExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)

    def _extract_emisor(self):
        self.emisor = "EURO DESGUACES MALAGA S.L"

    def _extract_numero_factura(self):
        invoice_regex = r'([0-9]+\s+\d{6,})'
        for line in self.lines:
            if re.search("Madrid1", line, re.IGNORECASE): # Specific keyword for this invoice
                match = re.search(invoice_regex, line, re.IGNORECASE)
                if match:
                    self.numero_factura = match.group(1)
                    break

    def _extract_fecha(self):
        date_regex = r'(\d{2}/\d{2}/\d{4})'
        for i, line in enumerate(self.lines):
            if re.search("Madrid1", line, re.IGNORECASE): # Specific keyword
                match = re.search(date_regex, self.lines[i+1])
                if match:
                    self.fecha = match.group(1)
                    break
    
    def _extract_cif(self):
        for line in self.lines:
            if re.search("C.I.F.", line, re.IGNORECASE):
                extracted_cif = _extract_nif_cif(line)
                if extracted_cif and extracted_cif != "B85629020":
                    self.cif = extracted_cif
                    break

    def _extract_importe_and_base(self):
        if self.lines: # The amount is on the last line
            last_line = self.lines[-1]
            self.importe = _extract_amount(last_line)
            if self.importe:
                self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)
