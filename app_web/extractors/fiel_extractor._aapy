import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import extract_and_format_date, _extract_amount, _extract_nif_cif, _extract_from_lines_with_keyword, _calculate_base_from_total, VAT_RATE

class FielExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)

    def _extract_emisor(self):
        for line in self.lines:
            if re.search(r"COMBUSTIBLES FIEL,\s*S\.L\.", line, re.IGNORECASE):
                self.emisor = "COMBUSTIBLES FIEL, S.L."
                break

    def _extract_numero_factura(self):
        invoice_regex = r"M(\d+)\s+(\d+)"
        for line in self.lines:
            match = re.search(invoice_regex, line, re.IGNORECASE)
            if match:
                self.numero_factura = f"M{match.group(1)} {match.group(2)}"
                break

    def _extract_fecha(self):
        self.fecha = _extract_from_lines_with_keyword(self.lines, r'(\d{2}[-/]\d{2}[-/]\d{4})', r'(\d{2}[-/]\d{2}[-/]\d{4})')
        if self.fecha is None:
            self.fecha = extract_and_format_date(self.lines)

    def _extract_cif(self):
        for line in self.lines:
            if re.search(r"Cif:\s*([A-Z]\d+)", line, re.IGNORECASE):
                extracted_cif = _extract_nif_cif(line)
                if extracted_cif and extracted_cif != "B85629020":
                    self.cif = extracted_cif
                    break
            if self.cif is None:
                super()._extract_cif()


    def _extract_importe_and_base(self):
        """
        Busca la línea con 'Total factura' (Línea 36) y extrae el importe (Línea 37).
        Luego calcula la Base Imponible a partir del Importe Total.
        """
        for i, line in enumerate(self.lines):
            # 1. Buscar la línea que contiene la frase clave 'Total factura'
            # Usamos re.search con IGNORECASE y \s+ para ser flexibles con espacios
            if re.search(r'Total\s*factura', line, re.IGNORECASE) and i + 1 < len(self.lines):
                
                # 2. El importe total está en la línea siguiente (i+1)
                amount_line = self.lines[i+1]
                
                # 3. Extraer el importe (300.00)
                # _extract_amount() debe normalizar el valor a un número.
                self.importe = _extract_amount(amount_line)
                
                if self.importe is not None:
                    # 4. Calcular la Base Imponible desde el Importe Total.
                    # Convertimos el importe a un string con coma (',') para la utilidad
                    # si asumes que maneja el formato español, aunque para 300.00 no importa.
                    importe_str_for_calc = str(self.importe).replace('.', ',')
                    
                    # Asumiendo VAT_RATE = 0.21 desde utils.py
                    calculated_base = _calculate_base_from_total(importe_str_for_calc, self.vat_rate)
                    
                    if calculated_base is not None:
                        # 5. Asignar el resultado formateado (con coma)
                        self.base_imponible = str(calculated_base).replace('.', ',')
                    
                    break # Salir del bucle una vez que encontramos los valores
