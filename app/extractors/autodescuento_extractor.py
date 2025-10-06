import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_nif_cif, _calculate_base_from_total, VAT_RATE

class AutodescuentoExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)

    def _extract_emisor(self):
        for line in self.lines:
            if re.search(r"AUTODESCUENTO\s*SL", line, re.IGNORECASE):
                self.emisor = "AUTODESCUENTO SL"
                break

    def _extract_numero_factura(self):
        invoice_number_regex = r'(\d+)\s*$'
        for i, line in enumerate(self.lines):
            if re.search(r"Número", line, re.IGNORECASE) and i + 1 < len(self.lines):
                match = re.search(invoice_number_regex, self.lines[i+1])
                if match:
                    self.numero_factura = match.group(1)
                    break

    def _extract_fecha(self):
        for i, line in enumerate(self.lines):
            if re.search(r"Fecha\s*$", line, re.IGNORECASE) and i + 1 < len(self.lines):
                date_match = re.search(r'(\d{2}[-/]\d{2}[-/]\d{4})', self.lines[i+1])
                if date_match:
                    self.fecha = date_match.group(1)
                    break
    
    def _extract_cif(self):
        for line in self.lines:
            if re.search(r"CIF.: ", line, re.IGNORECASE):
                extracted_cif = _extract_nif_cif(line)
                if extracted_cif and extracted_cif != "B85629020":
                    self.cif = extracted_cif
                    break

    def _extract_importe_and_base(self):
        for line in self.lines:
            if re.search(r"Forma de pago Líquido\(EUR\):", line, re.IGNORECASE):
                amount_match = re.search(r'^([\d\.,]+)', line.strip())
                if amount_match:
                    importe_str = amount_match.group(1)
                    self.importe = _extract_amount(importe_str)
                    if self.importe:
                        self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)
                        break
