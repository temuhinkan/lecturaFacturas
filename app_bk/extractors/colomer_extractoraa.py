import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_nif_cif, _calculate_base_from_total, VAT_RATE, _extract_from_line

class ColomerExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        self.vat_rate = VAT_RATE

    def _extract_emisor(self):
        # El emisor es NEW SATELITE SL, en la Línea 02 de la factura
        self.emisor = "NEW SATELITE SL"

    def _extract_cif(self):
        # El CIF del emisor (NEW SATELITE SL) está en la Línea 04
        self.cif = "B13101423"

    def _extract_numero_factura(self):
        # Lógica: Buscar 'FACTURA Nº' (L10) y el número está a 7 líneas después (L17: N-2025005504)
        print("--- TRAZA: _extract_numero_factura ---")
        for i, line in enumerate(self.lines):
            # Busca la etiqueta "FACTURA Nº"
            if re.search(r"^\s*FACTURA Nº\s*$", line.strip(), re.IGNORECASE):
                print(f"TRAZA: 'FACTURA Nº' encontrado en línea {i}")
                # El valor está 7 líneas después, como se ha indicado
                target_index = i + 7
                if target_index < len(self.lines):
                    num_line = self.lines[target_index].strip()
                    print(f"TRAZA: Línea {target_index} (Valor): '{num_line}'")
                    # El patrón es "N-2025005504"
                    num_match = re.search(r'(N-[\d]+)', num_line)
                    if num_match:
                        self.numero_factura = num_match.group(1).strip()
                        print(f"TRAZA: Número de Factura extraído: {self.numero_factura}")
                        return
        self.numero_factura = None
        print(f"TRAZA: Número de Factura final: {self.numero_factura}")

    def _extract_fecha(self):
        # Lógica: Buscar 'FECHA' (L13) y la fecha está a 5 líneas después (L18: 30/05/2025)
        print("--- TRAZA: _extract_fecha ---")
        for i, line in enumerate(self.lines):
            # Busca la etiqueta "FECHA"
            if re.search(r"^\s*FECHA\s*$", line.strip(), re.IGNORECASE):
                print(f"TRAZA: 'FECHA' encontrado en línea {i}")
                # El valor está 5 líneas después, como se ha indicado
                target_index = i + 5
                if target_index < len(self.lines):
                    date_line = self.lines[target_index].strip()
                    print(f"TRAZA: Línea {target_index} (Valor): '{date_line}'")
                    # Patrón de fecha DD/MM/YYYY
                    date_match = re.search(r'(\d{2}[-/]\d{2}[-/]\d{4})', date_line)
                    if date_match:
                        self.fecha = date_match.group(1).strip()
                        print(f"TRAZA: Fecha extraída: {self.fecha}")
                        return
        self.fecha = None
        print(f"TRAZA: Fecha final: {self.fecha}")
    
    def _extract_modelo(self):
        # El modelo (RENAULT KANGOO) está en la línea 35
        # No se requiere traza detallada a menos que falle la extracción
        for i, line in enumerate(self.lines):
            if i == 35:
                match = re.search(r"ANILLO AIRBAG\s*(.+?)\s*\(", line, re.IGNORECASE)
                if match:
                    self.modelo = match.group(1).strip()
                    return
        self.modelo = None

    def _extract_matricula(self):
        self.matricula = None

    def _extract_importe_and_base(self):
        print("--- TRAZA: _extract_importe_and_base ---")
        total_anchor_index = -1
        
        # --- 1. Buscar Ancla: "TOTAL FACTURA" (Línea 52) ---
        for i, line in enumerate(self.lines):
            if "TOTAL FACTURA" in line.strip(): 
                total_anchor_index = i
                print(f"TRAZA: 'TOTAL FACTURA' encontrado en línea {i}")
                break

        if total_anchor_index != -1:
            # 2. Importe Total: 1 línea después (L53: 107,00 €)
            total_index = total_anchor_index + 1
            if total_index < len(self.lines):
                line_with_total = self.lines[total_index].strip()
                print(f"TRAZA: Línea {total_index} (Importe Total): '{line_with_total}'")
                self.importe = _extract_amount(line_with_total) 
                print(f"TRAZA: Importe Total extraído: {self.importe}")

            # 3. Base Imponible: 1 línea antes (L51: 88,43)
            base_index = total_anchor_index - 1
            if base_index >= 0:
                line_with_base = self.lines[base_index].strip()
                print(f"TRAZA: Línea {base_index} (Base Imponible): '{line_with_base}'")
                
                # Extraer el último valor numérico para ser robustos
                base_match = re.findall(r'([\d\.,]+)', line_with_base)
                if base_match:
                    self.base_imponible = _extract_amount(base_match[-1])
                    print(f"TRAZA: Base Imponible extraída: {self.base_imponible}")
        
        # 4. Cálculo de IVA (por la diferencia si ambos existen)
        if self.importe is not None and self.base_imponible is not None:
            try:
                # Convertir a float para restar
                importe_float = float(str(self.importe).replace(',', '.'))
                base_float = float(str(self.base_imponible).replace(',', '.'))
                iva_float = round(importe_float - base_float, 2)
                # Formatear el IVA al formato de salida
                self.iva = str(iva_float).replace('.', ',')
                print(f"TRAZA: IVA calculado (Total - Base): {self.iva}")
            except ValueError:
                self.iva = None
                print("TRAZA: Error al convertir importes para calcular el IVA.")
        else:
            self.iva = None
            print("TRAZA: No se pudo calcular el IVA por falta de Importe o Base.")

        print(f"TRAZA: Importes finales: Total={self.importe}, Base={self.base_imponible}, IVA={self.iva}")