import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_nif_cif, _calculate_base_from_total, VAT_RATE, _calculate_total_from_base

class NorthgateExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        self.vat_rate = 0.21 # Tasa fija del 21%
        # Inicialización de atributos
        self.importe = None
        self.base_imponible = None
        self.iva = None
        self.matricula = None
        self.modelo = None

    def _extract_emisor(self):
        for line in self.lines:
            if re.search(r"NORTHGATE ESPAÑA RENTING FLEXIBLE S\.A\.", line, re.IGNORECASE):
                self.emisor = "NORTHGATE ESPAÑA RENTING FLEXIBLE S.A."
                break
    
    # --- Otros campos (omitidos por brevedad, asumo que ya están bien) ---
    def _extract_cif(self):
        # ... (Mantener la lógica anterior)
        for line in self.lines:
            match = re.search(r"CIF/NIF:\s*([A-Z0-9]+)", line, re.IGNORECASE)
            if match:
                extracted_cif = match.group(1).strip()
                if extracted_cif and extracted_cif != "B85629020":
                    self.cif = extracted_cif
                    return
    
    def _extract_numero_factura(self):
        # ... (Mantener la lógica anterior)
        for i, line in enumerate(self.lines):
            if re.search(r"FACTURA N", line.strip(), re.IGNORECASE):
                if i + 6 < len(self.lines):
                    target_line = self.lines[i + 6]
                    match = re.search(r"(VO-[A-Z0-9-]+)", target_line)
                    if match:
                        self.numero_factura = match.group(1).strip()
                        return

    def _extract_fecha(self):
        # ... (Mantener la lógica anterior)
        date_pattern = r"(\d{2}[-/]\d{2}[-/]\d{2,4})"
        for i in range(5):
             if i < len(self.lines):
                date_line = self.lines[i]
                match = re.search(date_pattern, date_line)
                if match:
                    date_str = match.group(1)
                    parts = date_str.split('/')
                    if len(parts[-1]) == 2:
                        self.fecha = f"{parts[0]}/{parts[1]}/20{parts[-1]}"
                    else:
                        self.fecha = date_str
                    return

    def _extract_matricula(self):
        # ... (Mantener la lógica anterior)
        for i, line in enumerate(self.lines):
            if re.search(r"Matrícula:", line.strip(), re.IGNORECASE):
                if i - 4 >= 0:
                    target_line = self.lines[i - 4]
                    match = re.search(r"([A-Z0-9-]+)", target_line, re.IGNORECASE)
                    if match:
                        self.matricula = match.group(1).strip()
                        return

    def _extract_modelo(self):
        # ... (Mantener la lógica anterior)
        for i, line in enumerate(self.lines):
            if re.search(r"Modelo:", line.strip(), re.IGNORECASE):
                if i - 3 >= 0:
                    target_line = self.lines[i - 3]
                    match = re.search(r"(RENAULT\s[A-Z0-9\s\.\(\)]+)", target_line, re.IGNORECASE)
                    if match:
                        self.modelo = match.group(1).strip()
                        return
    # -----------------------------------------------------------------

    # --- CAMPO COMPLEJO: IMPORTES (Base y Total) ---
    def _extract_importe_and_base(self):
        print("DEBUG: Iniciando extracción de importes...")
        total_index = -1
        
        # 1. Búsqueda de la línea de TOTAL FACTURA
        for i, line in enumerate(self.lines):
            cleaned_line = line.strip().replace('\xa0', ' ')
            if re.search(r"TOTAL\s*FACTURA", cleaned_line, re.IGNORECASE):
                total_index = i
                print(f"DEBUG: 'TOTAL FACTURA' encontrado en línea {i}")
                break

        if total_index != -1:
            # 2. Extracción de Importe Total (Línea i + 1)
            if total_index + 1 < len(self.lines):
                line_with_total = self.lines[total_index + 1].strip().replace('\xa0', ' ')
                print(f"DEBUG: Línea de Importe Total ({total_index+1}): '{line_with_total}'")
                
                total_match = re.search(r'([\d\.,]+)', line_with_total)
                if total_match:
                    # **CORRECCIÓN:** Asignar el valor formateado al atributo de la clase.
                    self.importe = _extract_amount(total_match.group(1))
                    imp1=self.importe.replace('.', '')
                    self.importe=imp1.replace(',', '.')
                    print(f"DEBUG: Importe Total extraído: {self.importe}")
                    

            # 3. Extracción de Base Imponible (Línea i + 2)
            if total_index + 2 < len(self.lines):
                line_with_base = self.lines[total_index + 2].strip().replace('\xa0', ' ')
                print(f"DEBUG: Línea de Base Imponible ({total_index+2}): '{line_with_base}'")

                base_match = re.search(r'([\d\.,]+)', line_with_base)
                if base_match:
                    # **CORRECCIÓN:** Asignar el valor formateado al atributo de la clase.
                    self.base_imponible = _extract_amount(base_match.group(1))
                    print(f"DEBUG: Base Imponible extraída: {self.base_imponible}")

            
            # 4. Cálculo y Formateo del IVA
            if self.base_imponible:
                print("DEBUG: Calculando IVA a partir de la base...")
                
                # PREPARACIÓN: Base original (ej: '6.173,56'). Necesitamos '6173.56' para float().
                clean_str = self.base_imponible.replace('.', '')
                base_for_calc = clean_str.replace(',', '.')
                self.base_imponible=base_for_calc
            