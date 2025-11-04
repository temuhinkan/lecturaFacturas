import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import extract_and_format_date, _extract_amount, _extract_nif_cif, _extract_from_lines_with_keyword, _calculate_base_from_total, VAT_RATE

class AutocasherExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)

    def _extract_emisor(self):
        self.emisor = "AUTOCASHER PILAS, SL"

    def _extract_numero_factura(self):
        # 1. Buscar la línea que contiene el NIF del cliente (Línea 01: B-85629020)
        for i, line in enumerate(self.lines):
            if 'B-85629020' in line:
                # 2. El número de factura está en la línea siguiente (Línea 02)
                if i + 1 < len(self.lines):
                    potential_invoice = self.lines[i + 1].strip()
                    # 3. Intentar extraer un número de 6 o más dígitos
                    match = re.search(r'(\d{6,})', potential_invoice)
                    if match:
                        self.numero_factura = match.group(1).strip()
                        return

        # 4. Fallback: Intentar encontrarlo cerca de la etiqueta FACTURA Nº:
        self.numero_factura = _extract_from_lines_with_keyword(
            self.lines, r'FACTURA Nº:', r'([A-Z0-9_ -]+)', look_ahead=1, look_back=1
        )

    def _extract_fecha(self):
        self.fecha = _extract_from_lines_with_keyword(self.lines, r'(\d{2}[-/]\d{2}[-/]\d{4})', r'(\d{2}[-/]\d{2}[-/]\d{4})')
        if self.fecha is None:
            self.fecha = extract_and_format_date(self.lines)

    def _extract_cif(self):
        for line in self.lines:
            if re.search("CIF:", line, re.IGNORECASE):
                extracted_cif = _extract_nif_cif(line)
                if extracted_cif and extracted_cif != "B85629020":
                    self.cif = extracted_cif
                    break

    def _extract_importe_and_base(self):
        for i, line in enumerate(self.lines):
            if re.search(r"TOTAL  FACTURA", line, re.IGNORECASE) and i + 1 < len(self.lines):
                self.importe = _extract_amount(self.lines[i+1])
                if self.importe:
                    self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)
                    break
