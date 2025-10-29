import re
import os
from extractors.base_invoice_extractor import BaseInvoiceExtractor
# Las funciones importadas ahora están disponibles en utils.py
from utils import _extract_amount, _extract_nif_cif, _calculate_base_from_total, VAT_RATE


class DesguaceseduardoExtractor(BaseInvoiceExtractor):
    # CIF del emisor: B-09420274
    EMISOR_CIF = "B-09420274"
    EMISOR_NAME = "DesguacesEduardo S.L."

    def __init__(self, lines, pdf_path):
        super().__init__(lines, pdf_path)
        # SOLUCIÓN al AttributeError: Asegurar que el atributo exista si la clase base no lo hace
        self.pdf_path = pdf_path 
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
            # Patrón: se mantiene el original para encontrar NIF/CIF
            match = re.search(r'\b[A-Z0-9]{8,10}\b', line) 
            if match:
                self.nif_cif = match.group(0).strip()

    def _extract_numero_factura(self):
        # Sugerencia automática: Número de Factura en la Línea 0
        # Línea: 3519.0825
        if len(self.lines) > 0:
            line = self.lines[0]
            # Patrón genérico de número de factura
            match = re.search(r'([A-Z0-9./-]+)', line) 
            if match:
                self.numero_factura = match.group(1).strip()
        
    def _extract_fecha(self):
        # Sugerencia automática: Fecha en la Línea 1
        # Línea: 25/08/2025
        if len(self.lines) > 1:
            line = self.lines[1]
            # Patrón para fechas (DD/MM/YYYY o DD-MM-YYYY)
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
        # El total correcto está en la LÍNEA 13 (30,00€), la L11 es incorrecta según el log.
        # Línea Base: 24,79€ (L9)
        # Línea Total: 30,00€ (L13)
        
        # Extracción del TOTAL (Línea 13)
        if len(self.lines) > 13: 
            total_line = self.lines[13]
            self.importe = _extract_amount(total_line)
            
        # Extracción de la Base Imponible (Línea 9)
        if len(self.lines) > 9:
             base_line = self.lines[9]
             self.base_imponible = _extract_amount(base_line)
             
        # Fallback de cálculo
        if self.importe and not self.base_imponible:
            self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)