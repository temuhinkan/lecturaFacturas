import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_nif_cif, _calculate_base_from_total, VAT_RATE

class LacaravanaExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)

    def _extract_emisor(self):
        self.emisor = "LA CARAVANA SL"

    def _extract_numero_factura(self):
        invoice_regex = r'(F-[A-Z0-9_]+-[A-Z0-9_]+)'
        for line in self.lines:
            if re.search("lacaravana", line, re.IGNORECASE): # Search for "lacaravana" keyword
                match = re.search(invoice_regex, line, re.IGNORECASE)
                if match:
                    self.numero_factura = match.group(1)
                    break

    def _extract_fecha(self):
        date_regex = r'(\d{2}/\d{2}/\d{4})'
        for line in self.lines:
            match = re.search(date_regex, line)
            if match:
                self.fecha = match.group(1)
                break

    def _extract_importe_and_base(self):
        for i, line in enumerate(self.lines):
            if re.search(r'TOTAL :', line, re.IGNORECASE):
                self.importe = _extract_amount(self.lines[i+1])
                if self.importe:
                    self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)
                    break
    def _extract_cif(self):
        for line in self.lines:
            if re.search(r'CIF: B', line, re.IGNORECASE):
                match =  re.search(r'CIF:\s*(B[0-9]{8}?)', line, re.IGNORECASE)
                extracted_cif = match.group(1).strip()
                if extracted_cif and extracted_cif != "B85629020":
                    self.cif = extracted_cif
                    break