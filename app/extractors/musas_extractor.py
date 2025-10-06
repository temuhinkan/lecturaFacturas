import re
import os
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_nif_cif, _calculate_base_from_total, VAT_RATE, _extract_from_line

class MusasExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        self.emisor = "Motor Las Musas, S.L."
        self.vat_rate = VAT_RATE

    def _extract_emisor(self):
        pass

    def _extract_matricula(self):
        matricula_pattern = r'\b\d{4}[BCDFGHJKLMNPRSTVWXYZ]{3}\b'
        for line in self.lines:
            matricula_match = re.search(matricula_pattern, line, re.IGNORECASE)
            if matricula_match:
                self.matricula = matricula_match.group(0).strip()
                break
        if not self.matricula:
            for line in self.lines:
                matricula_match_orig = re.search(r'\bMatrícula:\s*([A-Z0-9]+)\b', line, re.IGNORECASE)
                if matricula_match_orig:
                    self.matricula = matricula_match_orig.group(1).strip()
                    break

    def _extract_numero_factura(self):
        factura_pattern = r"(FT\d+\s+\d+)"
        for line in self.lines:
            match = re.search(factura_pattern, line)
            if match:
                self.numero_factura = match.group(1).strip()
                break
        if self.numero_factura is None:
            super()._extract_numero_factura()

    def _extract_fecha(self):
        fecha_pattern = r"(\d{2}/\d{2}/\d{4})"
        for line in self.lines:
            match = re.search(fecha_pattern, line)
            if match:
                self.fecha = match.group(1).strip()
                break
        if self.fecha is None:
            super()._extract_fecha()
    
    def _extract_modelo(self):
        for i, line in enumerate(self.lines):
            if re.search(r'MODELO', line, re.IGNORECASE):
                if i + 1 < len(self.lines):
                    data_line = self.lines[i+1].strip()
                    if data_line:
                        partes = data_line.split()
                        if partes:
                            self.modelo = partes[0]
                            return
        if self.modelo is None:
            super()._extract_modelo()

    def _extract_cif(self):
        emisor_cif_pattern = r"CIF:\s*(B\d{8})"
        for line in self.lines:
            match = re.search(emisor_cif_pattern, line, re.IGNORECASE)
            if match:
                extracted_cif = match.group(1).strip()
                if extracted_cif == "B81583445":
                    self.cif = extracted_cif
                    return
        super()._extract_cif()

    def _extract_importe_and_base(self):
        self.importe = None
        self.base_imponible = None

        for i, line in enumerate(self.lines):
            if re.search(r"\bTOTAL\s*A\s*PAGAR\b", line, re.IGNORECASE):
                if i + 1 < len(self.lines):
                    data_line = self.lines[i+1]
                    
                    numeric_strings = re.findall(r'(\d+[,.]\d{2})', data_line)
                    
                    if numeric_strings:
                        extracted_total_str = numeric_strings[-1]
                        
                        cleaned_str_from_util = _extract_amount(extracted_total_str)
                        
                        if isinstance(cleaned_str_from_util, str):
                            # Convertir la cadena limpia a float, reemplazando la coma por el punto
                            self.importe = float(cleaned_str_from_util.replace(',', '.'))
                        else:
                            # Si _extract_amount ya devolvió un float, usarlo directamente
                            self.importe = cleaned_str_from_util
                        
                        break 
                
        # Calcular la base a partir de este importe
        if self.importe is not None and self.base_imponible is None:
            # **CAMBIO CLAVE AQUÍ:** Convertimos self.importe a str antes de pasarlo a _calculate_base_from_total
            # para satisfacer la expectativa de que el argumento sea una cadena de texto.
            self.base_imponible = _calculate_base_from_total(str(self.importe), self.vat_rate) 
        
        # Fallback a la superclase si no se pudo extraer el importe o la base imponible
        if self.importe is None or self.base_imponible is None:
            super()._extract_importe_and_base()