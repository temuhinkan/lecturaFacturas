import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import extract_and_format_date, _extract_amount, _extract_nif_cif, _extract_from_lines_with_keyword, _calculate_base_from_total, VAT_RATE

class FielExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)

    def _extract_emisor(self):
        for line in self.lines:
            if re.search(r"COMBUSTIBLES FIEL,\s*S\.L\.", line, re.IGNORECASE):
                self.emisor = "COMBUSTIBLES FIEL, S.L."
                break

    def _extract_numero_factura(self):
        invoice_regex = r"M(\d+)\s+(\d+)"
        for line in self.lines:
            match = re.search(invoice_regex, line, re.IGNORECASE)
            if match:
                self.numero_factura = f"M{match.group(1)} {match.group(2)}"
                break

    def _extract_fecha(self):
        self.fecha = _extract_from_lines_with_keyword(self.lines, r'(\d{2}[-/]\d{2}[-/]\d{4})', r'(\d{2}[-/]\d{2}[-/]\d{4})')
        if self.fecha is None:
            self.fecha = extract_and_format_date(self.lines)

    def _extract_cif(self):
        for line in self.lines:
            if re.search(r"Cif:\s*([A-Z]\d+)", line, re.IGNORECASE):
                extracted_cif = _extract_nif_cif(line)
                if extracted_cif and extracted_cif != "B85629020":
                    self.cif = extracted_cif
                    break
            if self.cif is None:
                super()._extract_cif()


    def _extract_importe_and_base(self):
        for line in self.lines:
            if re.search(r"Total factura\s*", line, re.IGNORECASE):
                self.importe = _extract_amount(line)
                if self.importe:
                    self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)
                    break
