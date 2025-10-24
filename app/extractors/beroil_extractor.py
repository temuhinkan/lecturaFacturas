import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_nif_cif

class BeroilExtractor(BaseInvoiceExtractor):
    
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        
        # Inicialización CRÍTICA de todos los campos, incluyendo 'iva', para evitar el AttributeError
        self.emisor = "BEROIL, S.L.U"
        self.numero_factura = None
        self.fecha = None
        self.cif =  "B09417957"
        self.base_imponible = None
        self.iva = None  # <--- Esta línea previene el error
        self.importe = None
        self.vat_rate = 0.21

    def _extract_emisor(self):
        # El emisor se define en __init__
        pass

    def _extract_numero_factura(self):
        # Extrae de la Línea 6: FACTURA NÚM:25D022748
        if len(self.lines) > 6:
            match = re.search(r'FACTURA NÚM:([A-Z0-9]+)', self.lines[6])
            if match:
                self.numero_factura = match.group(1).strip()
                return

    def _extract_fecha(self):
        # Extrae de la Línea 1: 31/05/2025
        if len(self.lines) > 1:
            match = re.search(r'(\d{2}/\d{2}/\d{4})', self.lines[1])
            if match:
                self.fecha = match.group(1)
                return

    def _extract_cif(self):
        # El CIF del emisor no es claro en el extracto, pero podemos asumir el CIF del cliente
        # si fuera necesario, o dejarlo en 'None'. Dejaremos la extracción simple para enfocarnos
        # en la corrección de los montos.
        pass
        
    def _extract_importe_and_base(self):
        # Los montos se encuentran en líneas de índice fijo (0-based) en el pie:
        # Base Imponible: 64.12 € (Línea 40 -> índice 40)
        # IVA: 13.47 € (Línea 42 -> índice 42)
        # Importe Total: 77.59 € (Línea 43 -> índice 43)

        if len(self.lines) > 43:
            # 1. Base Imponible (L40)
            base_str = self.lines[40].strip()
            self.base_imponible = _extract_amount(base_str)
            if self.base_imponible is not None:
                self.base_imponible = str(self.base_imponible).replace('.', ',')

            # 2. IVA (L42)
            iva_str = self.lines[42].strip()
            self.iva = _extract_amount(iva_str)
            if self.iva is not None:
                self.iva = str(self.iva).replace('.', ',')

            # 3. Importe Total (L43)
            importe_str = self.lines[43].strip()
            self.importe = _extract_amount(importe_str)
            if self.importe is not None:
                self.importe = str(self.importe).replace('.', ',')

        # Si la extracción falla o el IVA es 0, nos aseguramos de que self.iva no sea None.
        if self.iva is None:
            self.iva = '0,00'