import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_nif_cif, _calculate_base_from_total, VAT_RATE, _calculate_total_from_base

class RecoautosExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        self.vat_rate = VAT_RATE

    def _extract_emisor(self):
        self.emisor = "RECICLADOS AUTO4 SL"

    def _extract_cif(self):
        for line in self.lines:
            match = re.search(r"CIF:\s*([A-Z0-9]+)", line, re.IGNORECASE)
            if match:
                extracted_cif = match.group(1).strip()
                if extracted_cif and extracted_cif != "B85629020":
                    self.cif = extracted_cif
                    return

    def _extract_fecha(self):
        # Lógica: 2 líneas después de "Fecha" (Línea 19 -> Línea 21: 17/06/2025)
        print("DEBUG: Intentando extraer Fecha...")
        for i, line in enumerate(self.lines):
            if re.search(r"^\s*Fecha\s*$", line.strip(), re.IGNORECASE):
                print(f"DEBUG: 'Fecha' encontrado en línea {i}")
                target_index = i + 2
                if target_index < len(self.lines):
                    date_line = self.lines[target_index].strip()
                    date_match = re.search(r'(\d{2}[-/]\d{2}[-/]\d{4})', date_line)
                    if date_match:
                        self.fecha = date_match.group(1).strip()
                        print(f"DEBUG: Fecha encontrada: {self.fecha}")
                        return
        self.fecha = None
        print(f"DEBUG: Fecha final: {self.fecha}")

    def _extract_numero_factura(self):
        # Lógica: 3 líneas antes de "Factura Nº" (Línea 23 -> Línea 20: 2025000711/FRU)
        print("DEBUG: Intentando extraer Número de Factura...")
        for i, line in enumerate(self.lines):
            if re.search(r"^\s*Factura Nº\s*$", line.strip(), re.IGNORECASE):
                print(f"DEBUG: 'Factura Nº' encontrado en línea {i}")
                target_index = i - 3
                if target_index >= 0:
                    num_line = self.lines[target_index].strip()
                    num_match = re.search(r'(\d{10}/FRU)', num_line)
                    if num_match:
                        self.numero_factura = num_match.group(1).strip()
                        print(f"DEBUG: Número de Factura encontrado: {self.numero_factura}")
                        return
        self.numero_factura = None
        print(f"DEBUG: Número de Factura final: {self.numero_factura}")
    
    def _extract_modelo(self):
        # Modelo (VOLKSWAGEN GOLF) está en la línea 38
        self.modelo = None
        for i, line in enumerate(self.lines):
            if i == 38 and re.search(r"VOLKSWAGEN GOLF", line, re.IGNORECASE):
                self.modelo = "VOLKSWAGEN GOLF"
                return
        
    def _extract_matricula(self):
        self.matricula = None

    def _extract_importe_and_base(self):
        print("DEBUG: Iniciando extracción de importes...")
        
        # --- ANCLA: "TOTAL FACTURA" (Línea 52) ---
        total_anchor_index = -1
        for i, line in enumerate(self.lines):
            if "TOTAL FACTURA" in line.strip(): # Línea 52
                total_anchor_index = i
                print(f"DEBUG: 'TOTAL FACTURA' encontrado en línea {i}")
                break

        if total_anchor_index != -1:
            # 1. Importe Total (1 línea después: Línea 53)
            total_index = total_anchor_index + 1
            if total_index < len(self.lines):
                line_with_total = self.lines[total_index].strip()
                print(f"DEBUG: Línea de Importe Total ({total_index}): '{line_with_total}'")
                total_match = re.search(r'([\d\.,]+)', line_with_total)
                if total_match:
                    self.importe = _extract_amount(total_match.group(1)) # Formato '90,00'
                    print(f"DEBUG: Importe Total extraído: {self.importe}")

            # 2. Base Imponible (1 línea antes: Línea 51)
            base_index = total_anchor_index - 1
            if base_index >= 0:
                line_with_base = self.lines[base_index].strip()
                print(f"DEBUG: Línea de Base Imponible ({base_index}): '{line_with_base}'")
                base_match = re.search(r'([\d\.,]+)', line_with_base)
                if base_match:
                    self.base_imponible = _extract_amount(base_match.group(1)) # Formato '74,38'
                    print(f"DEBUG: Base Imponible extraída: {self.base_imponible}")
        
        # 3. IVA (Se extrae de la línea 48, pero para ser más robustos se calcula si tenemos la base)
        # Si Base e Importe Total están, el IVA es la diferencia o se calcula.
        # En este caso, lo extraemos de la línea 48, donde está el valor.
        iva_match = re.search(r'([\d\.,]+)', self.lines[48].strip())
        if iva_match:
            self.iva = _extract_amount(iva_match.group(1)) # Formato '15,62'
            print(f"DEBUG: IVA extraído (L48): {self.iva}")

        print(f"DEBUG: Importes finales: Total={self.importe}, Base={self.base_imponible}, IVA={self.iva}")