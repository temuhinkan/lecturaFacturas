import re
import os
from extractors.base_invoice_extractor import BaseInvoiceExtractor
# Asegúrate de importar _calculate_total_from_base por si necesitas el fallback
from utils import _extract_amount, _calculate_base_from_total, VAT_RATE, _extract_from_line, _calculate_total_from_base

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
            # Buscar Vtos: 28/03/2025
            fecha_match = re.search(r'Vtos:\s*(\d{2}/\d{2}/\d{4})', line, re.IGNORECASE)
            if fecha_match:
                self.fecha = fecha_match.group(1).strip()
                break # Sale del bucle una vez que encuentra la fecha

    def _extract_modelo(self):
        # El modelo (ej. CAPTUR) se encuentra en la línea 23 del debug
        for line in self.lines:
            modelo_match = re.search(r'RENAULT\s*(\w+)', line, re.IGNORECASE)
            if modelo_match:
                self.modelo = modelo_match.group(1).strip()
                break

    def _extract_matricula(self):
        # La matrícula (ej. 2416KZM) se encuentra en la línea 40 del debug
        matricula_pattern = r'\b\d{4}[A-Z]{3}\b|\b\d{1,4}[BCDFGHJKLMNPRSTVWXYZ]{3}\b'
        
        for line in self.lines:
            matricula_match = re.search(matricula_pattern, line, re.IGNORECASE)
            if matricula_match:
                self.matricula = matricula_match.group(0).strip()
                break
        
        # Fallback si el patrón estricto no encuentra (esto es opcional, depende de la fiabilidad)
        if not self.matricula:
             for line in self.lines:
                # Intenta capturar lo que está cerca de 'Matricula:' si no se encuentra
                matricula_match_orig = re.search(r'Matrícula:\s*([A-Z0-9]+)', line, re.IGNORECASE)
                if matricula_match_orig:
                    self.matricula = matricula_match_orig.group(1).strip()
                    break

    def _extract_importe_and_base(self):
        # Corregido: El TOTAL FACTURA (ej. 484,85 €) aparece varias líneas después del texto.
        for i, line in enumerate(self.lines):
            if re.search(r"TOTAL FACTURA", line, re.IGNORECASE):
                # Buscar la cantidad en las siguientes 5 líneas (el importe está en la línea 89, 3 líneas después de la 86)
                for offset in range(1, 6): 
                    if i + offset < len(self.lines):
                        target_line = self.lines[i + offset]
                        # Intentar extraer la cantidad de la línea objetivo
                        self.importe = _extract_amount(target_line)
                        if self.importe:
                            # Si el importe total es encontrado, calcular la base
                            self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)
                            return
                
                # Si se encontró "TOTAL FACTURA" pero no el importe cerca, buscar la Base Imponible como alternativa.
                break 

        # FALLBACK: Búsqueda robusta de Base Imponible si el total no se encontró
        # La Base Imponible (ej. 400,70) a menudo está cerca de su etiqueta (Línea 83)
        if not self.base_imponible:
            for i, line in enumerate(self.lines):
                 if re.search(r"Base Imponible", line, re.IGNORECASE):
                      # Buscar la Base Imponible en la misma línea o en las 5 líneas anteriores/posteriores
                      for offset in range(-5, 6): 
                          base_idx = i + offset
                          if 0 <= base_idx < len(self.lines):
                              base_amount_str = _extract_amount(self.lines[base_idx])
                              if base_amount_str:
                                   self.base_imponible = base_amount_str
                                   # Recalcular importe y IVA a partir de la base
                                   self.importe, self.iva = _calculate_total_from_base(base_amount_str, self.vat_rate)
                                   return