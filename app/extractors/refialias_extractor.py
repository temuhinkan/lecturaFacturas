import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
# Asumiendo que utils.py contiene las funciones necesarias
from utils import _extract_amount, _extract_nif_cif, _extract_from_lines_with_keyword, _calculate_base_from_total, VAT_RATE 

class RefialiasExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        self.vat_rate = VAT_RATE

    def _extract_emisor(self):
        # Emisor definido por el CIF B80843055 (REFIALIAS S.L)
        self.emisor = "REFIALIAS S.L"

    def _extract_cif(self):
        # Extracción del CIF del emisor (B80843055)
        self.cif = 'B80843055' 

    def _extract_numero_factura(self):
        # Busca 'FACTURA :' (L6) y toma el valor de la línea siguiente (L7: 'A /19440')
        for i, line in enumerate(self.lines):
            if line.strip() == 'FACTURA :':
                if i + 1 < len(self.lines):
                    raw_num = self.lines[i+1].strip()
                    match = re.search(r'([A-Z0-9\s_/]+)', raw_num)
                    if match:
                        self.numero_factura = match.group(1).strip()
                        return 

    def _extract_fecha(self):
        # Busca 'FECHA:' (L11) y toma el valor de la línea siguiente (L12: '01-04-25')
        fecha_regex_pattern = r'(\d{2}-\d{2}-\d{2})'
        for i, line in enumerate(self.lines):
            if line.strip() == 'FECHA:':
                if i + 1 < len(self.lines):
                    raw_date = self.lines[i+1].strip()
                    match = re.search(fecha_regex_pattern, raw_date)
                    if match:
                        self.fecha = match.group(1)
                        return

    # Función auxiliar para manejar el formato de coma decimal y prevenir el error 'could not convert string to float'
    def _safe_format_amount(self, raw_value):
        amount = _extract_amount(raw_value)
        if amount is None:
            return None
        
        # 1. Convertir a string y reemplazar coma por punto para el parseo de float
        amount_str = str(amount).replace(',', '.')
        
        try:
            # 2. Convertir a float
            float_amount = float(amount_str)
            # 3. Formatear a string con dos decimales y coma (formato final)
            return f"{float_amount:.2f}".replace('.', ',')
        except ValueError:
            return None

    def _extract_importe_and_base(self):
        
        # Mapeamos los índices de las etiquetas relevantes en la sección de totales
        header_indices = {}
        for i, line in enumerate(self.lines):
            if line.strip() == 'Base Imponible':
                header_indices['BASE'] = i # Línea 28
            elif line.strip() == 'I.V.A.':
                header_indices['IVA'] = i   # Línea 30
            elif line.strip() == 'TOTAL' and 'IVA' in header_indices and i > header_indices['IVA']:
                # Nos aseguramos que sea el TOTAL final (L31) y no el TOTAL de la tabla de productos
                header_indices['TOTAL'] = i
            
        # El valor de Base Imponible (L32), I.V.A. (L34) y TOTAL (L35) están 4 líneas debajo de sus etiquetas (L28, L30, L31)
        OFFSET = 4
        
        # 1. Extracción de Base Imponible (Línea 32: '40,00')
        if 'BASE' in header_indices and header_indices['BASE'] + OFFSET < len(self.lines):
            base_raw = self.lines[header_indices['BASE'] + OFFSET].strip()
            self.base_imponible = self._safe_format_amount(base_raw)

        # 2. Extracción de IVA (Línea 34: '8,40')
        if 'IVA' in header_indices and header_indices['IVA'] + OFFSET < len(self.lines):
             iva_raw = self.lines[header_indices['IVA'] + OFFSET].strip()
             self.iva = self._safe_format_amount(iva_raw)

        # 3. Extracción de Importe Total (Línea 35: '48,40 €')
        if 'TOTAL' in header_indices and header_indices['TOTAL'] + OFFSET < len(self.lines):
            importe_raw = self.lines[header_indices['TOTAL'] + OFFSET].strip()
            self.importe = self._safe_format_amount(importe_raw)