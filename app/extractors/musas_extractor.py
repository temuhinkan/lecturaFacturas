import re
import os
from extractors.base_invoice_extractor import BaseInvoiceExtractor
# Asegúrate de importar _calculate_total_from_base para el cálculo inverso
from utils import _extract_amount, _extract_nif_cif, _calculate_base_from_total, VAT_RATE, _extract_from_line, _calculate_total_from_base

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
        # Busca el modelo 7 líneas después de la etiqueta 'MODELO'
        for i, line in enumerate(self.lines):
            if re.search(r'MODELO', line, re.IGNORECASE):
                if i + 7 < len(self.lines):
                    data_line = self.lines[i+7].strip()
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
        self.iva = None
        
        # 1. Búsqueda principal: Encontrar 'TOTAL A PAGAR' y extraer el valor 7 líneas después
        for i, line in enumerate(self.lines):
            if re.search(r"\bTOTAL\s*A\s*PAGAR\b", line, re.IGNORECASE):
                # El valor está consistentemente 7 líneas después de la etiqueta (e.g., 69 - 62 = 7)
                target_index = i + 7 
                
                if 0 <= target_index < len(self.lines):
                    target_line = self.lines[target_index]
                    
                    # _extract_amount extrae la cadena numérica (ej. '70,60') ignorando 'EUROS'
                    extracted_total_str = _extract_amount(target_line)
                    
                    if extracted_total_str:
                        self.importe = extracted_total_str
                        
                        # Calcular Base y IVA usando la función de utils.py
                        self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)
                        
                        if self.base_imponible:
                            # Re-ejecutar cálculo para obtener el IVA
                            _, self.iva = _calculate_total_from_base(self.base_imponible, self.vat_rate)

                        return
                
                break # Salir después de encontrar la etiqueta TOTAL A PAGAR

        # 2. Fallback: Buscar Base Imponible y calcular totales
        if self.base_imponible is None:
            # La Base Imponible (valor) también está 7 líneas después de su etiqueta (e.g., 66 - 59 = 7)
            base_pattern = r"Base\s*imponible"
            for i, line in enumerate(self.lines):
                if re.search(base_pattern, line, re.IGNORECASE):
                    target_index = i + 7 
                    if 0 <= target_index < len(self.lines):
                        base_amount_str = _extract_amount(self.lines[target_index])
                        if base_amount_str:
                            self.base_imponible = base_amount_str
                            # Calcular Importe y IVA desde la Base Imponible
                            self.importe, self.iva = _calculate_total_from_base(self.base_imponible, self.vat_rate)
                            return  