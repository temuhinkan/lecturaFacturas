import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_nif_cif, _extract_from_lines_with_keyword, _calculate_base_from_total, VAT_RATE

class BrildorExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)

    def _extract_emisor(self):
        self.emisor = "Brildor SL"

    def _extract_numero_factura(self):
        # 🟢 CORRECCIÓN: look_ahead se cambia de 2 a 0 (implícito) para buscar en la misma línea (L14: Factura 000211156)
        # Usamos Factura\s*(\d{6,}) para asegurarnos de que el patrón está en la misma línea.
        self.numero_factura = _extract_from_lines_with_keyword(
            self.lines, 
            r'Factura\s*(\d{6,})', # La palabra clave y el número están juntos
            r'(\d{6,})',          # Capturar solo el número
            look_ahead=0          # Buscar en la misma línea
        )

    def _extract_fecha(self):
        self.fecha = _extract_from_lines_with_keyword(self.lines, r'Fecha', r'(\d{2}/\d{2}/\d{4})', look_ahead=1)

    def _extract_importe_and_base(self):
        # La lógica de los importes es correcta para esta factura (L30: Total, L31: 36,66 €)
        for i, line in enumerate(self.lines):
            if 'Total' in line and i + 1 < len(self.lines):
                self.importe = _extract_amount(self.lines[i+1])
                if self.importe:
                    # Se asume que self.importe viene sin separador de miles si es necesario
                    # Y que _calculate_base_from_total maneja el formato de coma
                    self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)
                    # Opcional: Extraer IVA y asignar
                    if self.importe and self.base_imponible:
                        try:
                            # Preparamos para el cálculo quitando separadores de miles y cambiando , a .
                            importe_float = float(self.importe.replace('.', '').replace(',', '.'))
                            base_float = float(self.base_imponible.replace('.', '').replace(',', '.'))
                            iva_float = importe_float - base_float
                            self.iva = f"{iva_float:.2f}".replace('.', ',')
                        except ValueError:
                            # Fallback si falla el cálculo
                            self.iva = _extract_from_lines_with_keyword(self.lines, r'IVA 21%', r'([\d,]+)', look_ahead=1)
                    break
    
    def _extract_cif(self):
        # Lógica para extraer el CIF del emisor (ESB03308681, en L46 y L50)
        for line in self.lines:
            if re.search(r'Brildor SL', line, re.IGNORECASE):
                extracted_cif = _extract_nif_cif(line)
                if extracted_cif and extracted_cif != "B85629020":
                    self.cif = extracted_cif
                    break
        if self.cif is None: 
            super()._extract_cif()