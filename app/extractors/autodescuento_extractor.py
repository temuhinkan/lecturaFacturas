import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_nif_cif, _calculate_base_from_total, VAT_RATE, _calculate_total_from_base

class AutodescuentoExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        self.vat_rate = 0.21 # Tasa fija del 21%
        # Inicialización de atributos necesarios
        self.importe = None
        self.base_imponible = None
        self.iva = None

    def _extract_emisor(self):
        for line in self.lines:
            if re.search(r"AUTODESCUENTO\s*SL", line, re.IGNORECASE):
                self.emisor = "AUTODESCUENTO SL"
                break
    
    # --- CAMPO: CIF (Emisor) ---
    def _extract_cif(self):
        # El CIF (ESB83701003) está en la línea siguiente a 'CIF.:' (Línea 07).
        for i, line in enumerate(self.lines):
            if re.search(r"\bCIF\.:\s*$", line.strip(), re.IGNORECASE) and i + 1 < len(self.lines):
                # Intentamos extraer el CIF de la línea siguiente (Línea 07)
                extracted_cif = _extract_nif_cif(self.lines[i + 1])
                # Aseguramos que no se confunda con el CIF del cliente (B85629020)
                if extracted_cif and extracted_cif != "B85629020": 
                    self.cif = extracted_cif
                    return
        super()._extract_cif()

    # --- CAMPO: NÚMERO DE FACTURA ---
    def _extract_numero_factura(self):
        # El número (4300003562) está dos líneas después de 'Número' (Línea 27).
        for i, line in enumerate(self.lines):
            if re.search(r"\bNúmero\b", line.strip(), re.IGNORECASE) and i + 2 < len(self.lines):
                # La Línea 27 contiene el número de factura
                match = re.search(r'(\d+)', self.lines[i + 2])
                if match:
                    self.numero_factura = match.group(1).strip()
                    return
        super()._extract_numero_factura()

    # --- CAMPO: FECHA ---
    def _extract_fecha(self):
        # La fecha (06/05/2025) está dos líneas después de 'Fecha' (Línea 28).
        date_pattern = r'(\d{2}[-/]\d{2}[-/]\d{4})'
        for i, line in enumerate(self.lines):
            if re.search(r"\bFecha\b", line.strip(), re.IGNORECASE) and i + 2 < len(self.lines):
                # La Línea 28 contiene la fecha
                date_match = re.search(date_pattern, self.lines[i + 2])
                if date_match:
                    self.fecha = date_match.group(1).strip().replace('-', '/')
                    return
        super()._extract_fecha()

    # --- CAMPO COMPLEJO: IMPORTES (Base y Total) ---
    def _extract_importe_and_base(self):
        
        # Búsqueda basada en la etiqueta 'Líquido(EUR):' (Línea 52)
        total_index = -1
        for i, line in enumerate(self.lines):
            if re.search(r"Líquido\(EUR\):", line.strip(), re.IGNORECASE):
                total_index = i
                break

        if total_index != -1:
            
            # 1. Extraer Importe Total: Dos líneas antes de 'Líquido(EUR):' (Línea 50)
            if total_index - 2 >= 0:
                line_with_total = self.lines[total_index - 2]
                self.importe = _extract_amount(line_with_total)

            # 2. Extraer Base Imponible: Tres líneas antes de 'Líquido(EUR):' (Línea 49)
            if total_index - 3 >= 0:
                line_with_base = self.lines[total_index - 3]
                self.base_imponible = _extract_amount(line_with_base)
            
            # 3. Recalcular IVA (Verificación/Obtención)
            if self.base_imponible and self.importe:
                # Limpiamos puntos y comas para los cálculos internos de utils.py
                base_for_calc = self.base_imponible.strip().replace('€', '').replace('.', '')
                
                # Calculamos el IVA a partir de la Base Imponible
                _, calculated_iva = _calculate_total_from_base(base_for_calc, self.vat_rate)
                
                if calculated_iva:
                    self.iva = calculated_iva
            # Fallback de la clase base si todo falla
            else:
                 super()._extract_importe_and_base()

        else:
            # Fallback de la clase base si no se encuentra la etiqueta 'Líquido(EUR):'
            super()._extract_importe_and_base()