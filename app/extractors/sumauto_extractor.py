import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_nif_cif, _calculate_base_from_total, VAT_RATE, _extract_from_line, _extract_from_lines_with_keyword

class SumautoExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        self.emisor = "Sumauto Motor, S.L." 
        # 🟢 CORRECCIÓN CRÍTICA: Inicializar 'iva' para evitar el AttributeError
        self.iva = None
        self.base_imponible = None
        self.importe = None
        self.numero_factura = None
        self.fecha = None
        self.cif = None
        self.vat_rate = VAT_RATE

    def _extract_emisor(self):
        # El emisor está definido en el constructor
        self.emisor = "Sumauto Motor, S.L."

    def _extract_cif(self):
        # El CIF del emisor está en la Línea 45
        self.cif = "B88049341"
        
    def _extract_numero_factura(self):
        # La etiqueta "Nº factura" está en L25, el valor 'C280FP25_0353097' está en L32
        for i, line in enumerate(self.lines):
            # Usar una expresión regular flexible
            if re.search(r"Nº factura", line, re.IGNORECASE):
                # El valor está en L32, pero el ancla 'Nº factura' está en L25.
                # La posición relativa es muy grande (32 - 25 = 7 líneas de diferencia).
                # Buscamos directamente el patrón 'C280FP25_0353097' que es más fiable.
                pass 
        
        # Búsqueda directa del patrón de factura único (L32)
        pattern = r'(C\d{3}FP\d{2}_\d+)'
        for line in self.lines:
            match = re.search(pattern, line)
            if match:
                self.numero_factura = match.group(1).strip()
                return

    def _extract_fecha(self):
        # La fecha de expedición es la fecha de factura. (L33)
        match = re.search(r"Fecha de expedición:\s*(\d{2}/\d{2}/\d{4})", self.lines[33])
        if match:
            self.fecha = match.group(1).strip()
            return
        
    def _extract_importe_and_base(self):
        
        def safe_format_amount(raw_value):
            """Limpia el valor, maneja coma/punto y lo formatea."""
            amount = _extract_amount(raw_value)
            if amount is None: return None
            
            try:
                # 1. Reemplazamos coma por punto para que float() pueda interpretar
                float_amount = float(str(amount).replace(',', '.'))
                # 2. Formateamos a string con dos decimales y volvemos a usar la coma
                return f"{float_amount:.2f}".replace('.', ',')
            except ValueError:
                return None
        
        # Base Imponible está en L71: '92,00'
        base_raw = self.lines[71].strip()
        self.base_imponible = safe_format_amount(base_raw)
        
        # Importe Total está en L57: '111,32'
        total_raw = self.lines[57].strip()
        self.importe = safe_format_amount