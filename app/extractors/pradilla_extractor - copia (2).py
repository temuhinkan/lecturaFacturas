import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_nif_cif, _calculate_base_from_total, VAT_RATE, _extract_from_line, _extract_from_lines_with_keyword, extract_and_format_date

class PradillaExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None, debug_mode=False):
        super().__init__(lines, pdf_path)
        self.emisor = "GESTORIA PRADILLA, S.L."
        self.cif = "B-80481369"
        self.debug_mode = debug_mode

    def _extract_emisor(self):
        pass

    def _extract_numero_factura(self):
        # Patrón para buscar un número de 8 cifras precedido por un espacio y al final de la línea.
        # Este es el patrón general para el número de factura.
        invoice_number_pattern = r'\s(\d{8})\s*$' 

        for i, line in enumerate(self.lines):
            line_stripped = line.strip()
            # Intento 1: Buscar el patrón de 8 dígitos con espacio previo y fin de línea.
            match = re.search(invoice_number_pattern, line, re.IGNORECASE)
            if match:
                self.numero_factura = match.group(1).strip()
                return

            # Intento 2 (Fallback): Buscar el patrón CSV exacto (como en "NOFACTURA\n","25010126\n")
            # Esto es un respaldo si el patrón general falla para algunas líneas específicas.
            match_exact_csv = re.search(r'\"(?:N°|NO)FACTURA\\n\"\,\"(\\d{8})\\n\"', line, re.IGNORECASE)
            if match_exact_csv:
                self.numero_factura = match_exact_csv.group(1).strip()
                return
        
        super()._extract_numero_factura()


    def _extract_fecha(self):
        # Patrón para una fecha en formato DD/MM/YYYY.
        # Es lo suficientemente genérico para encontrar cualquier fecha válida.
        # No especificamos dónde debe estar en la línea, solo que debe contener el patrón.
        date_pattern = r'(\d{2}/\d{2}/\d{4})'

        for i, line in enumerate(self.lines):
            match = re.search(date_pattern, line) # No re.IGNORECASE para fechas, no aplica
            if match:
                self.fecha = match.group(1).strip()
                return # Devuelve la primera fecha encontrada y termina.
        
        # Si no se encuentra ninguna fecha con este patrón, se usa el fallback de la clase base.
        super()._extract_fecha()


    def _extract_cif(self):
        pass

    def _extract_modelo(self):
        car_models = ["RENAULT", "CITROEN", "OPEL", "SKODA", "SEAT", "AUDI", "BMW", "MERCEDES", "FORD", "VOLKSWAGEN", "KANGOO", "CORSA-E", "FABIA"]
        for line in self.lines:
            # Look for car models near "N.BASTIDOR:" or "ASUNTO:"
            if "N.BASTIDOR:" in line or "ASUNTO:" in line:
                for model in car_models:
                    if model in line.upper():
                        self.modelo = model
                        return
        super()._extract_modelo()


    def _extract_matricula(self):
        # Patrón para matrículas españolas (formato NNNNLLL).
        # Buscamos la matrícula cuando está incrustada en una línea, a menudo seguida de componentes de dirección.
        matricula_pattern_spanish_new_format = r'(\d{4}[A-Z]{3})' 
        
        for i, line in enumerate(self.lines):
            match = re.search(matricula_pattern_spanish_new_format, line, re.IGNORECASE)
            if match:
                extracted_matricula = match.group(1).strip()
                # Verificación adicional para asegurar que es la línea de la matrícula, buscando componentes de dirección.
                if re.search(r'(CL|SIERRA|MADRID|ARACENA)', line, re.IGNORECASE): 
                    self.matricula = extracted_matricula
                    return

        if self.debug_mode:
            print("DEBUG: Matricula not found with specific logic. Falling back to super()._extract_matricula().")
        super()._extract_matricula()


    def _extract_importe_and_base(self):
        if self.debug_mode:
            print("DEBUG: Entering _extract_importe_and_base for PradillaExtractor")
        
        # Priorizar la extracción del TOTAL A PAGAR
        total_found = False
        for i, line in enumerate(self.lines):
            if re.search(r"TOTAL A PAGAR", line, re.IGNORECASE):
                if i + 1 < len(self.lines):
                    next_line_values = self.lines[i+1]
                    values_in_next_line = re.findall(r'([\d.,]+)', next_line_values)
                    if values_in_next_line:
                        extracted_importe = _extract_amount(values_in_next_line[-1])
                        if extracted_importe is not None:
                            self.importe = str(extracted_importe).replace('.', ',')
                            total_found = True
                            break # Una vez que encontramos el total, podemos salir del bucle.
        
        # Si encontramos el importe total, calculamos la base a partir de él.
        if self.importe:
            try:
                numeric_importe = float(self.importe.replace(',', '.'))
                calculated_base = _calculate_base_from_total(str(numeric_importe).replace('.', ','), VAT_RATE)
                self.base_imponible = calculated_base
            except ValueError as e:
                self.base_imponible = 'No encontrado'
        else: # Si no se encontró el importe total, intentamos extraer la base directamente como respaldo.
            for i, line in enumerate(self.lines):
                if re.search(r"BASE I\.V\.A\.", line, re.IGNORECASE):
                    if i + 1 < len(self.lines):
                        next_line_values = self.lines[i+1]
                        values_in_next_line = re.findall(r'([\d.,]+)', next_line_values)
                        if values_in_next_line:
                            extracted_base = _extract_amount(values_in_next_line[0])
                            if extracted_base is not None:
                                self.base_imponible = str(extracted_base).replace('.', ',')
                                break
            
        # Si aún no tenemos importe o base, usamos el fallback de la clase base.
        if self.importe is None or self.base_imponible is None:
            super()._extract_importe_and_base()