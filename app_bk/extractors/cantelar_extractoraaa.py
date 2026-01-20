import re
import os
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_nif_cif, _calculate_base_from_total, VAT_RATE 

class CantelarExtractor(BaseInvoiceExtractor): 
    EMISOR_CIF = "B75526939" 
    
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        self.emisor = "ACCESORIOS PARA VEHICULOS CANTELAR, S.L." 
        self.cif = self.EMISOR_CIF
        self.vat_rate = VAT_RATE
        # CRÍTICO: Almacena el índice de la línea de la ÚLTIMA FECHA
        self.last_date_line_index = -1 

    def _extract_emisor(self):
        # El emisor está fijo en __init__
        pass

    def _extract_cif(self):
        # El CIF está fijo en __init__
        pass

    # --- Lógica de Extracción de Número de Factura (Priorizando Nombre de Archivo) ---
    def _extract_numero_factura(self):
        # 1. Intentar extraer del nombre del archivo (self.pdf_path)
        # Patrón en el nombre de archivo: X-XXXXXX o X_XXXXXX
        if self.pdf_path:
            file_name = os.path.basename(self.pdf_path)
            # Regex para el patrón digito-seis-digitos (o más)
            match_filename = re.search(r'(\d+[-_]\d{6,})', file_name, re.IGNORECASE)
            
            if match_filename:
                # Reemplazar posibles guiones bajos por guiones
                self.numero_factura = match_filename.group(1).replace('_', '-').strip()
                return

        # 2. Fallback: Usar la lógica de posición si no se encuentra en el nombre
        # La factura tiene el número dividido en dos líneas: L49: '6', L50: '003001'
        # Usamos los índices 48 y 49 (0-based)
        if len(self.lines) >= 50:
            part1 = self.lines[48].strip() 
            part2 = self.lines[49].strip() 
            
            # Validar que los fragmentos coincidan con el patrón esperado
            if re.match(r'^\d+$', part1) and re.match(r'^\d{6,}$', part2):
                self.numero_factura = f"{part1}-{part2}"
                return
        
    # --- Lógica de Extracción de Fecha (CRÍTICO: Busca la Última) ---
    def _extract_fecha(self):
        date_regex = r'(\d{2}/\d{2}/\d{4})'
        last_index = -1
        last_date = None
        
        # Iterar para encontrar la última ocurrencia (índice más alto)
        for i, line in enumerate(self.lines):
            match = re.search(date_regex, line.strip())
            if match:
                last_index = i
                last_date = match.group(1) # Guarda la última fecha encontrada
        
        self.last_date_line_index = last_index
        self.fecha = last_date
        
    # --- Lógica de Extracción de Importes (RELATIVA A LA ÚLTIMA FECHA) ---
    def _extract_importe_and_base(self):
        
        # 1. Asegurar que la fecha (y el índice) se hayan extraído
        if self.last_date_line_index == -1:
            self._extract_fecha()

        if self.last_date_line_index != -1:
            # Referencias para la factura Cantelar (L74: Última Fecha)
            # Base Imponible (L68) = last_date_line_index - 6
            # IVA (L70) = last_date_line_index - 4
            # Importe Total (L73) = last_date_line_index - 1
            
            # 🟢 Base Imponible (6 líneas antes de la última fecha)
            base_line_index = self.last_date_line_index - 6
            if base_line_index >= 0 and base_line_index < len(self.lines):
                extracted_base = _extract_amount(self.lines[base_line_index].strip())
                if extracted_base is not None:
                    self.base_imponible = str(extracted_base).replace('.', ',')

            # 🟢 IVA (4 líneas antes de la última fecha)
            iva_line_index = self.last_date_line_index - 4
            if iva_line_index >= 0 and iva_line_index < len(self.lines):
                extracted_iva = _extract_amount(self.lines[iva_line_index].strip())
                if extracted_iva is not None:
                    self.iva = str(extracted_iva).replace('.', ',')

            # 🟢 Importe Total (1 línea antes de la última fecha)
            importe_line_index = self.last_date_line_index - 1
            if importe_line_index >= 0 and importe_line_index < len(self.lines):
                extracted_importe = _extract_amount(self.lines[importe_line_index].strip())
                if extracted_importe is not None:
                    self.importe = str(extracted_importe).replace('.', ',')
                    
            # Fallback de cálculo si la extracción directa falla
            if self.importe and (self.base_imponible is None or self.iva is None):
                try:
                    calculated_base = _calculate_base_from_total(self.importe, self.vat_rate)
                    if calculated_base is not None:
                        self.base_imponible = calculated_base.replace('.', ',')
                        base_f = float(self.base_imponible.replace(',', '.'))
                        iva_f = base_f * self.vat_rate
                        self.iva = f"{iva_f:.2f}".replace('.', ',')
                except ValueError:
                    pass