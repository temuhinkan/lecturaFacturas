import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_nif_cif, _calculate_base_from_total, VAT_RATE

class LacaravanaExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        self.emisor = "LA CARAVANA SL"
        self.numero_factura = None
        self.fecha = None
        self.importe = None
        self.base_imponible = None
        self.iva = None
        self.cif = None
        self.vat_rate = VAT_RATE

    def _format_amount(self, val):
        """Helper para formatear el valor a string con dos decimales y coma como separador."""
        if val is not None:
            try:
                # _extract_amount puede retornar float o string con '.', convertir a string con ','
                return f"{float(str(val).replace(',', '.')):.2f}".replace('.', ',')
            except ValueError:
                return None
        return None

    def _extract_emisor(self):
        self.emisor = "LA CARAVANA SL"

    def _extract_numero_factura(self):
        # 🟢 CORRECCIÓN: Busca el patrón de factura F-XX-XXXXX (Línea 11).
        invoice_regex = r'([A-Z]-\d{2}-\d{5})'
        for line in self.lines:
            match = re.search(invoice_regex, line, re.IGNORECASE)
            if match:
                self.numero_factura = match.group(1).strip()
                return

    def _extract_fecha(self):
        # Extrae la fecha (Línea 10)
        date_regex = r'(\d{2}/\d{2}/\d{4})'
        for line in self.lines:
            match = re.search(date_regex, line)
            if match:
                self.fecha = match.group(1)
                return

    def _extract_importe_and_base(self):
        # 🟢 CORRECCIÓN: Extracción indexada basada en las líneas de debug (L37-L43).

        # 1. Extraer Importe Total (TOTAL:): Busca L38, valor en L40 (i+2)
        for i, line in enumerate(self.lines):
            if re.search(r'TOTAL\s*:\s*$', line.strip(), re.IGNORECASE):
                if i + 2 < len(self.lines):
                    total_raw = self.lines[i+2] # L40: 71,00 €
                    self.importe = self._format_amount(_extract_amount(total_raw))
        
        # 2. Extraer Base Imponible (Base Imp.:): Busca L37, valor en L43 (i+6)
        for i, line in enumerate(self.lines):
            if re.search(r'Base Imp.', line, re.IGNORECASE):
                if i + 6 < len(self.lines):
                    base_raw = self.lines[i+6] # L43: 58,68 €
                    self.base_imponible = self._format_amount(_extract_amount(base_raw))
                    
        # 3. Extraer IVA (IVA(21,00%) :): Busca L41, valor en L39 (i-2)
        for i, line in enumerate(self.lines):
            if re.search(r'IVA\(21,00%\)', line, re.IGNORECASE):
                if i - 2 >= 0:
                    iva_raw = self.lines[i-2] # L39: 12,32 €
                    self.iva = self._format_amount(_extract_amount(iva_raw))
        
    def _extract_cif(self):
        # Extrae el CIF del emisor (L50: CIF: B30378129)
        cif_regex = r'CIF:\s*([A-Z0-9]+)'
        for line in self.lines:
            match = re.search(cif_regex, line, re.IGNORECASE)
            if match:
                self.cif = match.group(1)
                return  