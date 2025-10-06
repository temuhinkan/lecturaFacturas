import re
import os
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _calculate_base_from_total, VAT_RATE, _extract_from_line

class BoxesExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path):
        super().__init__(lines, pdf_path)
        self.cif = "B-84962851" # CIF fijo para este emisor
        self.vat_rate = VAT_RATE # Asegúrate de que vat_rate esté inicializado si se usa en _calculate_base_from_total

    def _extract_emisor(self):
        self.emisor = "BOXES INTEGRALCAR, S.L"

    # ¡IMPORTANTE! Sobreescribe este método para que no haga nada si el CIF es fijo.
    def _extract_cif(self):
        # El CIF ya está fijado en el constructor (__init__) para este extractor.
        # No necesitamos buscarlo en el documento.
        pass

    def _extract_numero_factura(self):
        if self.pdf_path:
            nombre_archivo = os.path.basename(self.pdf_path)
            # El nombre del archivo es FRA838-2025-25_boxes.pdf, que contiene el número 838
            # Ajustado para FRA763-2025-25_boxes.pdf para 763
            match_invoice_num = re.search(r'FRA(\d+)-(\d+)-(\d+)_', nombre_archivo, re.IGNORECASE)
            if match_invoice_num:
                self.numero_factura = f"{match_invoice_num.group(1)}/{match_invoice_num.group(3)}"
    def _extract_fecha(self):
        # La fecha se encuentra después de "Vtos: " 
        for line in self.lines:
            fecha_match = re.search(r'Vtos:\s*(\d{2}/\d{2}/\d{4})', line, re.IGNORECASE)
            if fecha_match:
                self.fecha = fecha_match.group(1).strip()
                break # Sale del bucle una vez que encuentra la fecha

    def _extract_modelo(self):
        # El modelo es KANGOO
        for line in self.lines:
            modelo_match = re.search(r'Modelo:\s*(.*)', line, re.IGNORECASE)
            if modelo_match:
                self.modelo = modelo_match.group(1).strip()
                break

    def _extract_matricula(self):
        # La matrícula es 7752LJX
        matricula_pattern = r'\b\d{4}[BCDFGHJKLMNPRSTVWXYZ]{3}\b'
        
        for line in self.lines:
            matricula_match = re.search(matricula_pattern, line, re.IGNORECASE)
            if matricula_match:
                self.matricula = matricula_match.group(0).strip()
                break
        
        # Fallback si el patrón estricto no encuentra (esto es opcional, depende de la fiabilidad)
        if not self.matricula:
             for line in self.lines:
                matricula_match_orig = re.search(r'Matrícula:\s*([A-Z0-9]+)', line, re.IGNORECASE)
                if matricula_match_orig:
                    self.matricula = matricula_match_orig.group(1).strip()
                    break

    def _extract_importe_and_base(self):
        # El TOTAL FACTURA es 219,91 € y la Base Imponible es 181,74 €
        for line in self.lines:
            if re.search(r"TOTAL FACTURA", line, re.IGNORECASE):
                self.importe = _extract_amount(line)
                if self.importe:
                    self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)
                    break