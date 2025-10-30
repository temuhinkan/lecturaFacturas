import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_from_lines_with_keyword, _calculate_base_from_total, VAT_RATE

class LeroyExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        # Inicialización de atributos para seguridad (aunque la clase base debería hacerlo)
        self.emisor = "Leroy Merlin Espana S.L.U"
        self.numero_factura = None
        self.fecha = None
        self.importe = None
        self.base_imponible = None
        self.iva = None
        self.cif = None
        self.vat_rate = VAT_RATE

    def _extract_emisor(self):
        self.emisor = "Leroy Merlin Espana S.L.U"
        
    def _extract_cif(self):
        # Extraer NIF del emisor (Línea 01 o 09)
        self.cif = "B84818442"

    def _extract_numero_factura(self):
        # 🟢 CORRECCIÓN: Buscar 'FACTURA' seguido del número (Línea 04)
        pattern = r'FACTURA\s*([A-Z0-9_/-]+)'
        for line in self.lines:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                self.numero_factura = match.group(1).strip()
                return

    def _extract_fecha(self):
        # 🟢 CORRECCIÓN: La fecha está en L23, después de la etiqueta en L22.
        # Buscar "Fecha de venta:" y tomar la fecha de la línea siguiente si existe.
        for i, line in enumerate(self.lines):
            if re.search(r'Fecha de venta:', line, re.IGNORECASE) and i + 1 < len(self.lines):
                # Extrae el formato DD/MM/YYYY de la línea siguiente (L23)
                match = re.search(r'(\d{2}/\d{2}/\d{4})', self.lines[i+1])
                if match:
                    self.fecha = match.group(1).strip()
                    return

    def _extract_importe_and_base(self):
        
        def format_result(val):
            """Formatea el valor a string con dos decimales y coma como separador."""
            if val is not None:
                # _extract_amount retorna float o string con '.', convertir a string con ','
                return f"{float(str(val).replace(',', '.')):.2f}".replace('.', ',')
            return None
        
        # 🟢 CORRECCIÓN: Usar líneas fijas para los totales al final del documento.
        # L97: Base Imponible (45,60)
        # L98: IVA (9,58)
        # L99: Importe Total (55,18)

        if 97 < len(self.lines):
            base_raw = self.lines[97].strip()
            self.base_imponible = format_result(_extract_amount(base_raw))
        
        if 98 < len(self.lines):
            iva_raw = self.lines[98].strip()
            self.iva = format_result(_extract_amount(iva_raw))
            
        if 99 < len(self.lines):
            total_raw = self.lines[99].strip()
            self.importe = format_result(_extract_amount(total_raw))