import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import extract_and_format_date, _extract_amount, _extract_nif_cif, _extract_from_lines_with_keyword, _calculate_base_from_total, VAT_RATE

class CesvimapExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)

    def _extract_emisor(self):
        self.emisor = "CENTRO DE EXPERIMENTACIÓN Y SEGURIDAD VIAL MAPFRE"

    def _extract_numero_factura(self):
        invoice_regex = r"R-(\d+)"
        for line in self.lines:
            match = re.search(invoice_regex, line, re.IGNORECASE)
            if match:
                self.numero_factura = match.group(1)
                break

    def _extract_fecha(self):
        self.fecha = _extract_from_lines_with_keyword(self.lines, r'(\d{2}[-/]\d{2}[-/]\d{4})', r'(\d{2}[-/]\d{2}[-/]\d{4})')
        if self.fecha is None:
            self.fecha = extract_and_format_date(self.lines)

    def _extract_cif(self):
        for line in self.lines:
            if re.search("NIF:", line, re.IGNORECASE):
                extracted_cif = _extract_nif_cif(line)
                if extracted_cif and extracted_cif != "B85629020":
                    self.cif = extracted_cif
                    break

    # --- FUNCIÓN CORREGIDA Y AÑADIDA ---
    def _extract_importe_and_base(self):
        """
        Extrae el importe total buscando la palabra 'TOTAL' y toma el valor
        en la siguiente línea. Luego calcula la base imponible.
        """
        for i, line in enumerate(self.lines):
            # Buscar la línea que contiene la palabra clave 'TOTAL'
            if 'TOTAL' in line and i + 1 < len(self.lines):
                # El importe total está en la línea siguiente (índice i+1)
                amount_line = self.lines[i+1]
                
                # Extraer y normalizar el importe (ej: 75,63)
                self.importe = _extract_amount(amount_line)
                
                if self.importe:
                    # El importe total está formateado con coma,
                    # necesitamos pasar un string con coma a la utilidad de cálculo.
                    importe_str_with_comma = str(self.importe).replace('.', ',')
                    
                    # Calcular la Base Imponible desde el Importe Total
                    calculated_base = _calculate_base_from_total(importe_str_with_comma, self.vat_rate)
                    
                    if calculated_base is not None:
                        # Asignar el resultado formateado
                        self.base_imponible = str(calculated_base).replace('.', ',')
                    
                    # Salir del bucle una vez encontrados los valores
                    break

# La extracción de 'cliente', 'modelo' y 'matricula' se heredará de BaseInvoiceExtractor
# y se ejecutarán automáticamente si no se anulan aquí.