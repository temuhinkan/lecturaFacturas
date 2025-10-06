import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_nif_cif, _extract_from_lines_with_keyword, _calculate_base_from_total,_calculate_total_from_base, VAT_RATE

class StellantisExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)

    def _extract_emisor(self):
        self.emisor = "Placas de Piezas y Componentes de Recambio, S. A. U"

    def _extract_numero_factura(self):
        self.numero_factura = _extract_from_lines_with_keyword(self.lines, r'N° Factura', r'(\d{6,})')

    def _extract_fecha(self):
        self.fecha = _extract_from_lines_with_keyword(self.lines, r'(\d{2}/\d{2}/\d{4})', r'(\d{2}/\d{2}/\d{4})')

    def _extract_importe_and_base(self):
        for line in self.lines:
            if 'Total Factura' in line:
                print(f"line: {line}")
                self.base_imponible = _extract_amount(line, is_stellantis=True)
                if self.base_imponible:
                    self.importe = _calculate_total_from_base(self.base_imponible, self.vat_rate)
                    break
    # El método _extract_cif se ha eliminado para que StellantisExtractor herede
    # la implementación de BaseInvoiceExtractor, que ya maneja la exclusión del CIF del cliente.
    def _extract_cif(self):
        for line in self.lines:
            if re.search(r'NIF: A', line, re.IGNORECASE):
                match =  re.search(r'NIF:\s*(A[0-9]{8}?)', line, re.IGNORECASE)
                extracted_cif = match.group(1).strip()
                if extracted_cif and extracted_cif != "B85629020":
                    self.cif = extracted_cif
                    break
