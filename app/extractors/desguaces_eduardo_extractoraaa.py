import re
import os
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_nif_cif, _calculate_base_from_total, VAT_RATE

class DesguacesEduardoExtractor(BaseInvoiceExtractor):
    # CIF del emisor: B-09420274 (Obtenido de la línea de factura)
    EMISOR_CIF = "B-09420274"
    EMISOR_NAME = "Desguaces Eduardo S.L."

    def __init__(self, lines, pdf_path):
        super().__init__(lines, pdf_path)
        self.cif = self.EMISOR_CIF
        self.emisor = self.EMISOR_NAME
        self.vat_rate = VAT_RATE

    # --- Métodos de Extracción ---

    def _extract_emisor(self):
        # El emisor está fijo, pero lo re-afirmamos para claridad.
        self.emisor = self.EMISOR_NAME

    def _extract_cif(self):
        # El CIF ya está fijado en el constructor, no se busca.
        pass

    def _extract_cliente(self):
        # El cliente es la primera línea después del CIF del emisor y antes de la dirección.
        # En el output: "Line 2: NEWSATELITE S.L."
        if len(self.lines) > 2 and self.lines[2].strip():
            self.cliente = self.lines[2].strip()

    def _extract_numero_factura(self):
        # La factura se encuentra en la Línea 0 del output: 3519.0825
        if len(self.lines) > 0 and self.lines[0].strip():
            # A veces estos números son largos. Lo guardamos como viene.
            self.numero_factura = self.lines[0].strip()

    def _extract_fecha(self):
        # La fecha se encuentra en la Línea 1 del output: 25/08/2025
        if len(self.lines) > 1 and re.match(r'\d{2}/\d{2}/\d{4}', self.lines[1].strip()):
            self.fecha = self.lines[1].strip()

    def _extract_modelo(self):
        # El modelo es 'RENAULT KANGOO II' y se encuentra en la línea de concepto (Línea 8).
        # Línea 8: 25/08/2025 24,79€ 1 KIT CAMBIO RUEDA, GATO RENAULT KANGOO II
        for line in self.lines:
            # Busca las palabras clave "RENAULT KANGOO"
            match_modelo = re.search(r'(RENAULT\s+KANGOO\s+II?)', line, re.IGNORECASE)
            if match_modelo:
                # Almacena el modelo que encuentre, ej: RENAULT KANGOO II
                self.modelo = match_modelo.group(1).strip()
                break

    def _extract_matricula(self):
        # La matrícula no está visible en el output de las líneas.
        # Se asume que Desguaces Eduardo no incluye la matrícula.
        # Por lo tanto, se deja como 'None' (o lo que defina BaseInvoiceExtractor).
        pass

    def _extract_importe_and_base(self):
        # Buscamos la línea que contiene el TOTAL: Línea 11: 30,00€
        # Buscamos la línea que contiene la BASE IMPONIBLE: Línea 9: 24,79€
        
        # 1. Extracción del Importe (TOTAL)
        if len(self.lines) > 11:
            total_line = self.lines[11]
            self.importe = _extract_amount(total_line)
            
            # 2. Extracción de la Base Imponible (Línea 9)
            if len(self.lines) > 9:
                 base_line = self.lines[9]
                 extracted_base = _extract_amount(base_line)
                 
                 # Usamos la base extraída directamente
                 if extracted_base:
                     self.base_imponible = extracted_base
                 # Fallback: Si no se extrajo la base, la calculamos a partir del total
                 elif self.importe:
                     self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)