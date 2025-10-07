import re
import os
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_nif_cif, _calculate_base_from_total, VAT_RATE

class DesguaceseduardoExtractor(BaseInvoiceExtractor):
    # CIF del emisor: B-09420274
    EMISOR_CIF = "B-09420274"
    EMISOR_NAME = "DesguacesEduardo S.L."

    def __init__(self, lines, pdf_path):
        super().__init__(lines, pdf_path)
        self.cif = self.EMISOR_CIF
        self.emisor = self.EMISOR_NAME
        self.vat_rate = VAT_RATE

    # --- Métodos de Extracción --
    
    def _extract_emisor(self):
        # El emisor está fijo
        self.emisor = self.EMISOR_NAME

    def _extract_cif(self):
        # El CIF ya está fijado
        pass

    def _extract_cliente(self):
        # Sugerencia automática: Cliente en la Línea 2
        # Línea: NEWSATELITE S.L.
        if len(self.lines) > 2:
            self.cliente = self.lines[2].strip()

    def _extract_nif_cif_cliente(self):
        # Sugerencia automática: CIF/NIF del Cliente en la Línea 3
        # Línea: B85629020
        if len(self.lines) > 3:
            line = self.lines[3]
            # CORRECCIÓN 1: Se doblan las llaves {} y se usa doble barra invertida \b
            match = re.search(r'\b[A-Z0-9]{8,10}\b', line) 
            if match:
                self.nif_cif = match.group(0).strip()

    def _extract_numero_factura(self):
        # Sugerencia automática: Número de Factura en la Línea 0
        # Línea: 3519.0825
        if len(self.lines) > 0:
            line = self.lines[0]
            # Patrón genérico de número de factura (Ajustar si es necesario)
            match = re.search(r'([A-Z0-9./-]+)', line) 
            if match:
                self.numero_factura = match.group(1).strip()
        
    def _extract_fecha(self):
        # Sugerencia automática: Fecha en la Línea 1
        # Línea: 25/08/2025
        if len(self.lines) > 1:
            line = self.lines[1]
            # CORRECCIÓN 2: Se doblan llaves {} y barras invertidas \d y \-
            match = re.search(r'(\d{2}[/\-]\d{2}[/\-]\d{4})', line)
            if match:
                self.fecha = match.group(1).replace('-', '/').strip()

    def _extract_modelo(self):
        # Extracción genérica de modelo.
        pass

    def _extract_matricula(self):
        # Extracción de matrícula.
        pass

    def _extract_importe_and_base(self):
        # Sugerencia automática: Base en Línea 9 y Total en Línea 11
        # Línea Base: 24,79€
        # Línea Total: 30,00€
        
        # Extracción del TOTAL
        if len(self.lines) > 11:
            total_line = self.lines[11]
            self.importe = _extract_amount(total_line)
            
        # Extracción de la Base Imponible
        if len(self.lines) > 9:
             base_line = self.lines[9]
             self.base_imponible = _extract_amount(base_line)
             
        # Fallback de cálculo
        if self.importe and not self.base_imponible:
            self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)

