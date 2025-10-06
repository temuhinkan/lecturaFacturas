import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import extract_and_format_date, _extract_amount, _extract_nif_cif, _calculate_base_from_total, VAT_RATE

class BeroilExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)

    def _extract_emisor(self):
        for line in self.lines:
            if re.search(r"BEROIL,\s*S\.L\.U", line, re.IGNORECASE):
                self.emisor = "BEROIL, S.L.U"
                break

    def _extract_numero_factura(self):
        invoice_regex = r"FACTURA NÚM:\s*([A-Z0-9_ -]+)"
        for line in self.lines:
            if re.search("FACTURA NÚM:", line, re.IGNORECASE):
                match = re.search(invoice_regex, line, re.IGNORECASE)
                if match:
                    self.numero_factura = match.group(1)
                    break

    def _extract_fecha(self):
        super()._extract_fecha()
        if self.fecha is None:
            self.fecha = extract_and_format_date(self.lines)

    def _extract_cif(self):
        for line in self.lines:
            if re.search(r"CIF: B\d+", line, re.IGNORECASE):
                match =  re.search(r'(B[0-9]{8}?)', line, re.IGNORECASE)
                if match:
                    extracted_cif = match.group(1).strip()
                    if extracted_cif and extracted_cif != "B85629020":
                        self.cif = extracted_cif
                        break
                if self.cif is None:
                    super()._extract_cif()


    def _extract_importe_and_base(self):
        for i, line in enumerate(self.lines):
            if re.search(r"FORMA DE PAGO:", line, re.IGNORECASE) and i > 0:
                self.importe = _extract_amount(self.lines[i-1])
                if self.importe:
                    self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)
                    break
    def _extract_matricula(self):
        self.matricula =""