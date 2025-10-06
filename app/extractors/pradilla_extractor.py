import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_nif_cif, _calculate_base_from_total, VAT_RATE, _extract_from_line, _extract_from_lines_with_keyword, extract_and_format_date

class PradillaExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None, debug_mode=False):
        super().__init__(lines, pdf_path)
        self.emisor = "GESTORIA PRADILLA, S.L."
        self.cif = "B-80481369"
        self.debug_mode = debug_mode
        self.tasas = None # Nueva variable para almacenar las tasas

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
        
        total_a_pagar_float = None
        self.tasas = None # Resetear tasas para cada extracción

        # Intento 1: Buscar "TOTAL A PAGAR" y su valor en la línea siguiente (comportamiento principal)
        for i, line in enumerate(self.lines):
            if re.search(r"TOTAL A PAGAR", line, re.IGNORECASE):
                if i + 1 < len(self.lines):
                    values_in_next_line = re.findall(r'([\d.,]+)', self.lines[i+1])
                    if values_in_next_line:
                        total_a_pagar_str = values_in_next_line[-1]
                        extracted_total = _extract_amount(total_a_pagar_str)
                        if extracted_total is not None:
                            try:
                                total_a_pagar_float = float(str(extracted_total).replace(',', '.'))
                            except ValueError:
                                total_a_pagar_float = None

                    # Buscar las tasas en la línea anterior (si existe)
                    if i > 0:
                        prev_line = self.lines[i-1]
                        values_in_prev_line = re.findall(r'([\d.,]+)', prev_line)
                        if values_in_prev_line:
                            tasas_str = values_in_prev_line[-1]
                            extracted_tasas_val = _extract_amount(tasas_str)
                            if extracted_tasas_val is not None:
                                try:
                                    self.tasas = float(str(extracted_tasas_val).replace(',', '.'))
                                except ValueError:
                                    self.tasas = None
        
                # Una vez que encontramos "TOTAL A PAGAR", procesamos e intentamos salir.
                if total_a_pagar_float is not None:
                    importe_calculado = total_a_pagar_float
                    if self.tasas is not None and isinstance(self.tasas, (int, float)):
                        importe_calculado = total_a_pagar_float - self.tasas
                        if self.debug_mode:
                            print(f"DEBUG: Importe total a pagar: {total_a_pagar_float}, Tasas: {self.tasas}, Importe calculado (sin tasas): {importe_calculado}")
                    else:
                        if self.debug_mode:
                            print(f"DEBUG: Tasas no numéricas o no encontradas para la resta. Usando Total a Pagar como importe calculado.")
                    
                    self.importe = str(importe_calculado).replace('.', ',')
                    try:
                        numeric_importe = float(self.importe.replace(',', '.'))
                        calculated_base = _calculate_base_from_total(str(numeric_importe).replace('.', ','), VAT_RATE)
                        self.base_imponible = calculated_base
                    except ValueError as e:
                        self.base_imponible = 'No encontrado'
                    return # Salimos después de procesar el primer TOTAL A PAGAR encontrado


        # Intento 2 (Fallback): Si no se encontró el "TOTAL A PAGAR" en el formato esperado (línea siguiente)
        # Buscamos "TOTAL A PAGAR" y luego el primer número que parezca un total en las siguientes 5 líneas
        if total_a_pagar_float is None:
            if self.debug_mode:
                print("DEBUG: Intentando fallback para TOTAL A PAGAR.")
            for i, line in enumerate(self.lines):
                if re.search(r"TOTAL A PAGAR", line, re.IGNORECASE):
                    # Empezar a buscar el valor del total desde la línea actual hasta unas pocas líneas más adelante
                    for j in range(i, min(i + 6, len(self.lines))): # Buscar en la línea actual y las 5 siguientes
                        # Buscar números que estén al final de la línea o seguidos de (EUR)
                        match = re.search(r'([\d.,]+)\s*\(EUR\)', self.lines[j]) # Priorizar (EUR)
                        if not match:
                            match = re.search(r'([\d.,]+)\s*$', self.lines[j]) # O al final de la línea
                        
                        if match:
                            total_a_pagar_str = match.group(1)
                            extracted_total = _extract_amount(total_a_pagar_str)
                            if extracted_total is not None:
                                try:
                                    total_a_pagar_float = float(str(extracted_total).replace(',', '.'))
                                    if self.debug_mode:
                                        print(f"DEBUG: TOTAL A PAGAR encontrado por fallback: {total_a_pagar_float}")
                                    
                                    # Intentamos buscar tasas en la línea anterior a donde se encontró el total a pagar
                                    # Esto es importante para el caso de la segunda factura.
                                    if j > 0:
                                        prev_line_for_tasas = self.lines[j-1]
                                        values_in_prev_line_for_tasas = re.findall(r'([\d.,]+)', prev_line_for_tasas)
                                        if values_in_prev_line_for_tasas:
                                            tasas_str = values_in_prev_line_for_tasas[-1]
                                            extracted_tasas_val = _extract_amount(tasas_str)
                                            if extracted_tasas_val is not None:
                                                try:
                                                    self.tasas = float(str(extracted_tasas_val).replace(',', '.'))
                                                except ValueError:
                                                    self.tasas = None
                                            if self.debug_mode:
                                                print(f"DEBUG: Tasas encontradas por fallback: {self.tasas}")


                                    importe_calculado = total_a_pagar_float
                                    if self.tasas is not None and isinstance(self.tasas, (int, float)):
                                        importe_calculado = total_a_pagar_float - self.tasas
                                        if self.debug_mode:
                                            print(f"DEBUG: Importe total a pagar (fallback): {total_a_pagar_float}, Tasas: {self.tasas}, Importe calculado (sin tasas): {importe_calculado}")
                                    else:
                                        if self.debug_mode:
                                            print(f"DEBUG: Tasas no numéricas o no encontradas en fallback para la resta. Usando Total a Pagar como importe calculado.")

                                    self.importe = str(importe_calculado).replace('.', ',')
                                    try:
                                        numeric_importe = float(self.importe.replace(',', '.'))
                                        calculated_base = _calculate_base_from_total(str(numeric_importe).replace('.', ','), VAT_RATE)
                                        self.base_imponible = calculated_base
                                    except ValueError as e:
                                        self.base_imponible = 'No encontrado'
                                    return # Salimos después de procesar por fallback
                                except ValueError:
                                    pass # Continuar buscando si la conversión falla
                        
        # Si aún no tenemos importe o base, usamos el fallback de la clase base.
        if self.importe is None or self.base_imponible is None:
            if self.debug_mode:
                print("DEBUG: Importe o base no encontrados, recurriendo al fallback de la clase base.")
            # Esta parte se ejecutará si "TOTAL A PAGAR" no se encontró o el proceso falló.
            # En este caso, intentamos extraer la base directamente como respaldo, o usamos el super().
            for i, line in enumerate(self.lines):
                if re.search(r"BASE I\.V\.A\.", line, re.IGNORECASE):
                    if i + 1 < len(self.lines):
                        next_line_values = self.lines[i+1]
                        values_in_next_line = re.findall(r'([\d.,]+)', next_line_values)
                        if values_in_next_line:
                            extracted_base = _extract_amount(values_in_next_line[0])
                            if extracted_base is not None:
                                self.base_imponible = str(extracted_base).replace('.', ',')
                                # Si encontramos la base por esta vía, intentamos calcular el importe
                                # inverso, si no se ha establecido ya.
                                if self.importe is None:
                                    try:
                                        numeric_base = float(self.base_imponible.replace(',', '.'))
                                        # Esto es una estimación si no encontramos el total inicialmente
                                        self.importe = str(numeric_base * (1 + VAT_RATE)).replace('.', ',')
                                    except ValueError:
                                        self.importe = 'No encontrado'
                                break
            
            # Último fallback si nada se ha encontrado
            if self.importe is None or self.base_imponible is None:
                super()._extract_importe_and_base()

    # Sobreescribir el método extract_all para incluir las tasas
    def extract_all(self):
        # Primero, llamamos al método extract_all de la clase base
        # Esto asegura que todos los demás atributos (importe, base_imponible, etc.) se rellenen
        # y que _extract_importe_and_base (de esta clase) sea llamado para poblar self.tasas.
        base_extracted_data = super().extract_all()

        # Desempaquetamos los datos extraídos por la clase base
        # Asegúrate de que este orden coincida con lo que devuelve el extract_all de BaseInvoiceExtractor
        tipo, fecha, numero_factura, emisor, cliente, cif, modelo, matricula, importe, base_imponible = base_extracted_data

        # Ahora, devolvemos todos los campos incluyendo el nuevo campo 'tasas'
        return (tipo, fecha, numero_factura, emisor, cliente, cif,
                modelo, matricula, importe, base_imponible, self.tasas)
