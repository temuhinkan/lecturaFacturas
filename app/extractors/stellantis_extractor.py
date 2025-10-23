import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_nif_cif, _extract_from_lines_with_keyword, _calculate_base_from_total,_calculate_total_from_base, VAT_RATE

class StellantisExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        # 🚨 Inicialización: Aseguramos que la tasa de IVA (0.21) esté en la instancia
        self.vat_rate = VAT_RATE
        # 🚨 Inicialización: Aseguramos que el atributo self.iva exista
        self.iva = None 

    def _extract_emisor(self):
        self.emisor = "Placas de Piezas y Componentes de Recambio, S. A. U"

    def _extract_numero_factura(self):
        # Corrección: Busca el número de factura en la línea ANTERIOR a 'N° Factura'.
        
        keyword = r'N° Factura'
        for i, line in enumerate(self.lines):
            if re.search(keyword, line, re.IGNORECASE):
                if i - 1 >= 0:
                    line_to_check = self.lines[i-1] 
                    match = re.search(r'(\d{6,})', line_to_check)
                    if match:
                        self.numero_factura = match.group(1).strip()
                        break
        
        # Fallback: Busca en la misma línea que la palabra clave
        if not self.numero_factura:
            self.numero_factura = _extract_from_lines_with_keyword(self.lines, r'N° Factura', r'(\d{6,})')


    def _extract_fecha(self):
        self.fecha = _extract_from_lines_with_keyword(self.lines, r'(\d{2}/\d{2}/\d{4})', r'(\d{2}/\d{2}/\d{4})')

    def _extract_importe_and_base(self):
        
        # Reiniciamos los campos
        self.base_imponible = None
        self.iva = None       # <--- Este es el campo que queremos forzar
        self.importe = None

        total_factura_index = -1
        # 1. Buscar la etiqueta 'Total Factura'
        for i, line in enumerate(self.lines):
            if 'Total Factura' in line:
                total_factura_index = i
                break
        
        # 2. Si encontramos 'Total Factura' y hay una línea anterior válida (Base Imponible)
        if total_factura_index != -1 and total_factura_index - 1 >= 0:
            
            # Extraemos el monto de la línea anterior
            base_line = self.lines[total_factura_index - 1]
            extracted_base = _extract_amount(base_line, is_stellantis=True)
            
            if extracted_base:
                
                self.base_imponible = extracted_base
                
                # 🚨 PASO CLAVE: Forzamos el valor de salida del IVA al texto deseado
                # Esto garantiza que el campo 'IVA' no se quede como 'No encontrado'
                self.iva = "21%"  # Puedes cambiarlo a "21" si prefieres solo el número
                
                try:
                    # 3. Calcular el Importe Total (Base + IVA monetario)
                    # El importe total SÍ debe ser el cálculo (Base * 1.21)
                    base_float = float(self.base_imponible.replace(',', '.'))
                    
                    # Usamos VAT_RATE (0.21) para el cálculo del total, no para la etiqueta
                    total_amount = base_float * (1 + self.vat_rate) 
                    
                    # 4. Asignación del Importe Total (monetario)
                    self.importe = f"{total_amount:.2f}".replace('.', ',')
                    
                except ValueError:
                    # Si falla el cálculo, limpiamos los campos
                    self.base_imponible = None
                    # self.iva se mantiene como "21%" si se encontró la base, o se pone a None aquí si Base=None
                    self.importe = None

    def _extract_cif(self):
        for line in self.lines:
            if re.search(r'NIF: A', line, re.IGNORECASE):
                match =  re.search(r'NIF:\s*(A[0-9]{8}?)', line, re.IGNORECASE)
                extracted_cif = match.group(1).strip()
                if extracted_cif and extracted_cif != "B85629020":
                    self.cif = extracted_cif
                    break