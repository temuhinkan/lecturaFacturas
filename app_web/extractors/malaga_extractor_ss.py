import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_nif_cif, _calculate_base_from_total, VAT_RATE

class MalagaExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        self.emisor = "EURO DESGUACES MALAGA S.L"
        # Inicialización de campos
        self.numero_factura = None
        self.fecha = None
        self.importe = None
        self.base_imponible = None
        self.iva = None
        self.cif = None
        self.vat_rate = VAT_RATE
        # CRÍTICO: Almacena el índice de la línea donde se encuentra la fecha
        self.fecha_line_index = -1 

    def _find_date_and_index(self):
        """Busca el primer campo con formato de fecha simple (DD/MM/AAAA) y devuelve su índice y valor."""
        # Se busca el patrón de fecha
        date_regex = r'(\d{2}/\d{2}/\d{4})'
        for i, line in enumerate(self.lines):
            match = re.search(date_regex, line.strip())
            # Heurística: la fecha es un campo corto y solo contiene la fecha o similar
            if match and len(line.strip()) <= 15: 
                return i, match.group(1)
        return -1, None

    def _extract_emisor(self):
        self.emisor = "EURO DESGUACES MALAGA S.L"

    def _extract_fecha(self):
        # 1. Encontrar la fecha y su índice (el ancla)
        index, fecha = self._find_date_and_index()
        if index != -1:
            self.fecha_line_index = index
            self.fecha = fecha
        
    def _extract_numero_factura(self):
        # 1. Asegurar que la fecha se haya extraído para tener el índice
        if self.fecha_line_index == -1:
            self._extract_fecha()
        
        # 2. Extraer el número de factura 2 líneas antes de la fecha
        if self.fecha_line_index != -1 and self.fecha_line_index >= 2:
            num_line_index = self.fecha_line_index - 2
            
            # Contenido de la línea donde debería estar el número: '001134'
            num_factura_raw = self.lines[num_line_index].strip()
            
            # Patrón para el número de factura (mínimo 6 dígitos).
            match = re.search(r'^\d{6,}$', num_factura_raw)
            if match:
                self.numero_factura = num_factura_raw

    def _extract_cif(self):
        # Extrae el CIF del emisor (B-92.329.663)
        for line in self.lines:
            if re.search("C.I.F.", line, re.IGNORECASE) or re.search("B-92", line):
                extracted_cif = _extract_nif_cif(line)
                # Asegurar que no sea el CIF del cliente
                if extracted_cif and extracted_cif != "B85629020":
                    self.cif = extracted_cif
                    return

    def _extract_importe_and_base(self):
        # Aseguramos que la fecha se haya extraído para tener self.fecha_line_index
        if self.fecha_line_index == -1:
            self._extract_fecha()

        if self.fecha_line_index != -1:
            # 🟢 Paso 1: Extraer el Importe Total (6 líneas después de la fecha)
            importe_line_index = self.fecha_line_index + 6
            
            if importe_line_index < len(self.lines):
                importe_raw_line = self.lines[importe_line_index].strip()
                
                # Extraer el monto de esa línea (ej. '75,00 ')
                extracted_importe = _extract_amount(importe_raw_line)
                
                if extracted_importe is not None:
                    # Formatear el importe a cadena con coma decimal
                    self.importe = str(extracted_importe).replace('.', ',')

                    # 🟢 Paso 2: Calcular la Base Imponible y el IVA (quitando el 21%)
                    # Usamos la utilidad _calculate_base_from_total
                    self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)
                    
                    # Calcular el IVA: Importe Total - Base Imponible
                    if self.importe and self.base_imponible:
                        try:
                            importe_f = float(self.importe.replace(',', '.'))
                            base_f = float(self.base_imponible.replace(',', '.'))
                            iva_f = importe_f - base_f
                            self.iva = f"{iva_f:.2f}".replace('.', ',')
                        except ValueError:
                            self.iva = None