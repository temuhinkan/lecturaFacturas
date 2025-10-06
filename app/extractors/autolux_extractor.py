import re
import os
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_nif_cif, _calculate_base_from_total, VAT_RATE

class AutoluxExtractor(BaseInvoiceExtractor):
    # CIF del emisor: B02819530 (Obtenido de la fuente 30 y Línea 24)
    EMISOR_CIF = "B02819530"
    EMISOR_NAME = "AUTOLUX RECAMBIOS, S.L."

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
        # El cliente está en la Línea 5 del output: NEWSATELITE SL
        if len(self.lines) > 5 and self.lines[5].strip():
            self.cliente = self.lines[5].strip()

    def _extract_numero_factura(self):
        # El número de factura está en la Línea 13: 25.068.427 30-07-2025...
        for line in self.lines:
            # Buscamos el patrón "d.d.ddd.ddd" al inicio de una línea
            match_num = re.search(r'^(\d{2}\.\d{3}\.\d{3})', line)
            if match_num:
                self.numero_factura = match_num.group(1).strip()
                break
    
    def _extract_nif_cif_cliente(self):
        # El CIF del cliente está en la Línea 6 (B85629020) o en la Línea 13
        # Usaremos la Línea 13 que contiene el CIF-DNI B85629020
        for line in self.lines:
            match_cif_line = re.search(r'B\d{8}', line)
            if match_cif_line:
                self.nif_cif = match_cif_line.group(0).strip()
                break


    def _extract_fecha(self):
        # La fecha de factura está en la Línea 13: ... 30-07-2025 ...
        for line in self.lines:
            # Busca un patrón de fecha después de un número largo (la factura)
            match_fecha = re.search(r'\d{2}\.\d{3}\.\d{3}\s+(\d{2}-\d{2}-\d{4})', line)
            if match_fecha:
                # La convertimos a formato DD/MM/YYYY
                self.fecha = match_fecha.group(1).replace('-', '/')
                break

    def _extract_modelo(self):
        # El modelo (KANGOO) se encuentra en la Línea 3: 467009 / PARACHOQUES KANGOO 13-> DEL. 1 78,51 78,51
        for line in self.lines:
            # Busca la palabra clave "KANGOO" o "RENAULT KANGOO"
            match_modelo = re.search(r'(KANGOO\s*(\d{2}->)?\s*DEL\.)', line, re.IGNORECASE)
            if match_modelo:
                # Almacena el modelo que encuentre, ej: KANGOO 13-> DEL.
                self.modelo = match_modelo.group(1).strip()
                break

    def _extract_matricula(self):
        # La matrícula no está disponible en las líneas de la factura, se deja en blanco.
        pass

    def _extract_importe_and_base(self):
        # Los valores están en la Línea 16: 86,51 86,51 21 18,17 104,68 (Base, Base, Tipo, Cuota, Total)
        
        # El valor TOTAL FACTURA es 104,68
        # El valor BASE es 86,51
        
        for line in self.lines:
            # Buscar una línea que contenga los 5 valores numéricos seguidos (base, base, tipo, cuota, total)
            # El patrón busca la estructura "X,XX X,XX Y Z,ZZ W,WW" donde el IVA es 21
            match_amounts = re.search(r'([\d,]+)\s+([\d,]+)\s+21\s+([\d,]+)\s+([\d,]+)', line)
            
            if match_amounts:
                # Los grupos son: (Base), (Base), (Cuota), (Total)
                base_str = match_amounts.group(1)
                total_str = match_amounts.group(4)
                
                self.base_imponible = _extract_amount(base_str)
                self.importe = _extract_amount(total_str)
                break