import re
import os
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _calculate_base_from_total, VAT_RATE, _extract_from_line, extract_and_format_date

class BerolkemiExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        self.emisor = "BEROL KEMI, S.L"
        self.cif = "B79841052"
        self.vat_rate = VAT_RATE
        self.importe = None
        self.base_imponible = None
        self.iva = None
        # Campos no aplicables en esta factura
        self.matricula = None
        self.modelo = None

    def _extract_emisor(self):
        for line in self.lines:
            if re.search(r"BEROL KEMI, S\.L", line, re.IGNORECASE):
                self.emisor = "BEROL KEMI, S.L"
                break

    def _extract_cif(self):
        # El CIF está fijo, pero se puede verificar por el texto.
        for line in self.lines:
            match = re.search(r'C\.I\.F\.:\s*([A-Z]?\d{7}[A-Z]?)', line)
            if match:
                extracted_cif = match.group(1).strip()
                if extracted_cif == "B79841052": 
                    self.cif = extracted_cif
                    return

    def _extract_numero_factura(self):
        # ANCLA: 'Serie/NºFactura' (Línea 14)
        # PARTES: Línea 22 ('25') y Línea 23 ('1.628'). Se concatenan como 25/1628.
        print("DEBUG: Intentando extraer Número de Factura...")
        for i, line in enumerate(self.lines):
            if "Serie/NºFactura" in line: # Línea 14
                print(f"DEBUG: 'Serie/NºFactura' encontrado en línea {i}")
                
                # La Serie (Línea 22) está 8 líneas después (22 - 14 = 8)
                serie_index = i + 8
                # El Número (Línea 23) está 9 líneas después (23 - 14 = 9)
                num_index = i + 9
                
                if serie_index < len(self.lines) and num_index < len(self.lines):
                    serie_part = self.lines[serie_index].strip() 
                    num_part = self.lines[num_index].strip()     
                    
                    print(f"DEBUG: Parte Serie (Línea {serie_index}): '{serie_part}'")
                    print(f"DEBUG: Parte Número (Línea {num_index}): '{num_part}'")

                    if serie_part and num_part:
                        # Une las dos partes, quitando el punto de miles del número
                        self.numero_factura = f"{serie_part}/{num_part.replace('.', '')}"
                        print(f"DEBUG: Número de Factura encontrado: {self.numero_factura}")
                        return
        print(f"DEBUG: Número de Factura final: {self.numero_factura}")

    def _extract_fecha(self):
        # ANCLA: 'Fecha Factura' (Línea 13)
        # VALOR: Línea 17 ('10/06/2025') -> 4 líneas después.
        print("DEBUG: Intentando extraer Fecha...")
        for i, line in enumerate(self.lines):
            if "Fecha Factura" in line: # Línea 13
                print(f"DEBUG: 'Fecha Factura' encontrado en línea {i}")
                
                target_index = i + 4 # Línea 17
                if target_index < len(self.lines):
                    date_line = self.lines[target_index]
                    print(f"DEBUG: Buscando fecha en línea {target_index}: '{date_line.strip()}'")

                    fecha_match = re.search(r'(\d{2}/\d{2}/\d{4})', date_line)
                    if fecha_match:
                        self.fecha = fecha_match.group(1).strip()
                        print(f"DEBUG: Fecha encontrada: {self.fecha}")
                        return
        print(f"DEBUG: Fecha final: {self.fecha}")

    def _extract_matricula(self):
        self.matricula = None

    def _extract_modelo(self):
        self.modelo = None

    def _extract_importe_and_base(self):
        print("DEBUG: Iniciando extracción de importes...")
        
        # --- 1. Importe Total (Línea 69) ---
        # Ancla: "IMPORTE:" (Línea 68) -> Valor: Línea 69 ('52,03')
        importe_index = -1
        for i, line in enumerate(self.lines):
            if "IMPORTE:" in line: # Línea 68
                importe_index = i
                print(f"DEBUG: 'IMPORTE:' encontrado en línea {i}")
                break

        if importe_index != -1 and importe_index + 1 < len(self.lines):
            line_with_total = self.lines[importe_index + 1].strip().replace('\xa0', ' ')
            print(f"DEBUG: Línea de Importe Total ({importe_index+1}): '{line_with_total}'")
            
            total_match = re.search(r'([\d\.,]+)', line_with_total)
            if total_match:
                self.importe = _extract_amount(total_match.group(1)) # Formato '52,03'
                print(f"DEBUG: Importe Total extraído: {self.importe}")

        # --- 2. Base Imponible (Línea 62) ---
        # Ancla: "B. IMPONIBLE" (Línea 56) -> Valor: Línea 62 ('43,00')
        base_anchor_index = -1
        for i, line in enumerate(self.lines):
            if "B. IMPONIBLE" in line: # Línea 56
                base_anchor_index = i
                break
        
        if base_anchor_index != -1:
            target_base_index = base_anchor_index + 7 # Línea 62 (56 + 6)
            if target_base_index < len(self.lines):
                line_with_base = self.lines[target_base_index].strip().replace('\xa0', ' ')
                print(f"DEBUG: Línea de Base Imponible ({target_base_index}): '{line_with_base}'")
                
                base_match = re.search(r'([\d\.,]+)', line_with_base)
                if base_match:
                    self.base_imponible = _extract_amount(base_match.group(1)) # Formato '43,00'
                    print(f"DEBUG: Base Imponible extraída: {self.base_imponible}")
        
        # --- 3. IVA (Línea 64) ---
        # Ancla: "TOTAL IVA" (Línea 57) -> Valor: Línea 64 ('9,03')
        iva_anchor_index = -1
        for i, line in enumerate(self.lines):
            if "TOTAL IVA" in line: # Línea 57
                iva_anchor_index = i
                break
        
        if iva_anchor_index != -1:
            target_iva_index = iva_anchor_index + 7 # Línea 64 (57 + 7)
            if target_iva_index < len(self.lines):
                line_with_iva = self.lines[target_iva_index].strip().replace('\xa0', ' ')
                print(f"DEBUG: Línea de IVA ({target_iva_index}): '{line_with_iva}'")
                
                iva_match = re.search(r'([\d\.,]+)', line_with_iva)
                if iva_match:
                    self.iva = _extract_amount(iva_match.group(1)) # Formato '9,03'
                    print(f"DEBUG: IVA extraído: {self.iva}")
                    
        # Para el cálculo del IVA, ya no es necesario si se extrae correctamente.
        # Si la extracción falla, puedes volver a la lógica de cálculo (opcional).

        print(f"DEBUG: Importes finales: Total={self.importe}, Base={self.base_imponible}, IVA={self.iva}")