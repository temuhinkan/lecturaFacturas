import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_nif_cif, _extract_from_lines_with_keyword, _calculate_base_from_total, VAT_RATE

class KiautoExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        self.vat_rate = VAT_RATE

    def _extract_emisor(self):
        self.emisor = "AUTOLUX RECAMBIOS S.L"

    def _extract_numero_factura(self):
        # 🟢 CORRECCIÓN: 'Factura' (L26) -> valor '25.033.287' (L31). look_ahead=5.
        self.numero_factura = _extract_from_lines_with_keyword(
            self.lines, 
            r'Factura', 
            r'(\d{2}\.\d{3}\.\d{3})', 
            look_ahead=5 # Busca 5 líneas después de 'Factura'
        )
        if self.numero_factura:
            self.numero_factura = self.numero_factura.strip()

    def _extract_fecha(self):
        # 🟢 CORRECCIÓN: 'Fecha Factura' (L27) -> valor '10-04-2025' (L32). look_ahead=5.
        fecha_raw = _extract_from_lines_with_keyword(
            self.lines, 
            r'Fecha Factura', 
            r'(\d{2}[-/]\d{2}[-/]\d{4})', 
            look_ahead=5 # Busca 5 líneas después de 'Fecha Factura'
        )
        if fecha_raw:
            # Estandarizar el formato
            self.fecha = fecha_raw.replace('-', '/')

    def _extract_importe_and_base(self):
        # 1. Extraer BASE IMPONIBLE
        # 🟢 CORRECCIÓN: 'Base' (L42) -> valor '41,75' (L46). look_ahead=4.
        base_str_raw = _extract_from_lines_with_keyword(
            self.lines, 
            r'Base\b', # Coincide con la etiqueta 'Base'
            r'([\d.,]+)', 
            look_ahead=4
        )
        if base_str_raw:
            self.base_imponible = _extract_amount(base_str_raw)
            if self.base_imponible:
                # Asegurar formato de coma y quitar separadores de miles
                self.base_imponible = str(self.base_imponible).replace('.', '').replace(',', ',')
        
        # 2. Extraer IMPORTE TOTAL
        # 🟢 CORRECCIÓN: 'TOTAL FACTURA' (L39) -> valor '50,52' (L49). look_ahead=10.
        importe_str_raw = _extract_from_lines_with_keyword(
            self.lines, 
            r'TOTAL FACTURA', 
            r'([\d.,]+)', 
            look_ahead=10
        )
        if importe_str_raw:
            self.importe = _extract_amount(importe_str_raw)
            if self.importe:
                self.importe = str(self.importe).replace('.', '').replace(',', ',')

        # 3. Calcular IVA (ya que tenemos Base e Importe Total)
        if self.importe and self.base_imponible:
            try:
                importe_float = float(self.importe.replace(',', '.'))
                base_float = float(self.base_imponible.replace(',', '.'))
                iva_float = importe_float - base_float
                self.iva = f"{iva_float:.2f}".replace('.', ',')
            except ValueError:
                self.iva = None
    
    def _extract_cif(self):
        # Extrae el CIF del emisor (B02819530 en L60)
        for line in self.lines:
            if re.search(r'AUTOLUX RECAMBIOS S\.L', line, re.IGNORECASE):
                extracted_cif = _extract_nif_cif(line)
                # El CIF del emisor es B02819530. B85629020 es el del cliente.
                if extracted_cif and extracted_cif != "B85629020":
                    self.cif = extracted_cif
                    break