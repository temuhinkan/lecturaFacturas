import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_nif_cif, _calculate_base_from_total, VAT_RATE, _extract_from_line, _extract_from_lines_with_keyword, extract_and_format_date

class AdevintaExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None, debug_mode=False):
        super().__init__(lines, pdf_path)
        self.emisor = "Adevinta Motor, S.L.U." # Emisor fijo según lo proporcionado
        self.debug_mode = debug_mode
        self.iva_amount = None # Inicializar self.iva_amount para evitar AttributeError
        self.cif="B85629020"

    def _extract_emisor(self):
        # El emisor es fijo para esta clase, no necesita extracción de las líneas
        pass

    def _extract_numero_factura(self):
        # Patrón para buscar el número de factura de "Factura" y la línea siguiente
        # o de "8ES0077715 Factura original:"
        
        # Intento 1: Buscar "Factura" y el número en la línea siguiente
        for i, line in enumerate(self.lines):
            if re.search(r"Factura", line, re.IGNORECASE) and i + 1 < len(self.lines):
                next_line = self.lines[i+1]
                match = re.search(r"([A-Z0-9]+)", next_line)
                if match:
                    self.numero_factura = match.group(1).strip()
                    if self.debug_mode:
                        print(f"DEBUG: Número de factura extraído (Intento 1): {self.numero_factura}")
                    return

        # Intento 2: Buscar "Factura original:" en la misma línea
        for line in self.lines:
            match = re.search(r"([A-Z0-9]+)\s*Factura original:", line, re.IGNORECASE)
            if match:
                self.numero_factura = match.group(1).strip()
                if self.debug_mode:
                    print(f"DEBUG: Número de factura extraído (Intento 2): {self.numero_factura}")
                return
        
        # Si no se encuentra, se recurre al método de la clase base
        super()._extract_numero_factura()
        if self.debug_mode and not self.numero_factura:
            print("DEBUG: Número de factura no encontrado con la lógica específica de Adevinta.")


    def _extract_fecha(self):
        # Patrón para buscar la fecha en el formato "DD/MM/YYYY Fecha:"
        date_pattern = r"(\d{2}/\d{2}/\d{4})\s*Fecha:"
        for line in self.lines:
            match = re.search(date_pattern, line)
            if match:
                self.fecha = match.group(1).strip()
                if self.debug_mode:
                    print(f"DEBUG: Fecha extraída: {self.fecha}")
                return
        # Si no se encuentra con el patrón específico, se recurre al método de la clase base
        super()._extract_fecha()
        if self.debug_mode and not self.fecha:
            print("DEBUG: Fecha no encontrada con la lógica específica de Adevinta.")


    def _extract_cif(self):
        # Patrón para buscar el CIF del emisor "CIF B-70677158"
        cif_emisor_pattern = r"CIF\s*([A-Z0-9]{1,2}-?\d{8})"
        for line in self.lines:
            match = re.search(cif_emisor_pattern, line, re.IGNORECASE)
            if match:
                self.cif_emisor = match.group(1).strip()
                if self.debug_mode:
                    print(f"DEBUG: CIF del emisor extraído: {self.cif}")
                return
        # Si no se encuentra, se recurre al método de la clase base
        super()._extract_cif()
        if self.debug_mode and not self.cif:
            print("DEBUG: CIF del emisor no encontrado con la lógica específica de Adevinta.")

    def _extract_cliente(self):
        # El cliente es "NEW SATELITE, S.L." y su CIF/NIF está en "B85629020"
        # Podemos buscar "NEW SATELITE, S.L." o el NIF del cliente para confirmarlo.
        cliente_name_pattern = r"NEW\s*SATELITE,\s*S\.L\."
        cliente_nif_pattern = r"CIF/NIF:\s*(B\d{8})"

        for i, line in enumerate(self.lines):
            if re.search(cliente_name_pattern, line, re.IGNORECASE):
                self.cliente = "NEW SATELITE, S.L."
                if self.debug_mode:
                    print(f"DEBUG: Cliente extraído: {self.cliente}")
                return
            
            match_nif = re.search(cliente_nif_pattern, line, re.IGNORECASE)
            if match_nif:
                # Si encontramos el NIF del cliente, asumimos el nombre del cliente.
                # Esto es un respaldo si el nombre directo no se encuentra.
                self.cliente = "NEW SATELITE, S.L."
                if self.debug_mode:
                    print(f"DEBUG: Cliente extraído por NIF: {self.cliente}")
                return

        # Si no se encuentra con la lógica específica, self.cliente permanecerá como None
        # o será establecido por la clase base si tiene un método para ello.
        if self.debug_mode and not self.cliente:
            print("DEBUG: Cliente no encontrado con la lógica específica de Adevinta.")
        # No llamamos a super()._extract_cliente() si BaseInvoiceExtractor no lo tiene.


    def _extract_modelo(self):
        # No se especifica un modelo en este tipo de factura,
        # así que podemos dejar que la clase base lo maneje (probablemente resultará en 'No encontrado').
        super()._extract_modelo()

    def _extract_matricula(self):
        # No se especifica una matrícula en este tipo de factura,
        # así que podemos dejar que la clase base lo maneje (probablemente resultará en 'No encontrado').
        super()._extract_matricula()

    def _extract_importe_and_base(self):
        if self.debug_mode:
            print("DEBUG: Entering _extract_importe_and_base for AdevintaExtractor")

        # Prioridad 1: Intentar extraer el "Total" (importe final)
        total_pattern = r"Total\s*([\d.,]+\s*EUR)"
        for line in self.lines:
            match = re.search(total_pattern, line, re.IGNORECASE)
            if match:
                importe_str = match.group(1).replace('EUR', '').strip()
                extracted_importe = _extract_amount(importe_str)
                if extracted_importe is not None:
                    self.importe = str(extracted_importe).replace('.', ',')
                    if self.debug_mode:
                        print(f"DEBUG: Importe (Total) extraído: {self.importe}")
                    
                    # Calcular la Base Imponible a partir del Importe Total (IVA incluido)
                    try:
                        numeric_importe = float(self.importe.replace(',', '.'))
                        # Usamos VAT_RATE para calcular la base a partir del importe total (IVA incluido)
                        calculated_base = _calculate_base_from_total(str(numeric_importe).replace('.', ','), VAT_RATE)
                        self.base_imponible = calculated_base
                        if self.debug_mode:
                            print(f"DEBUG: Base Imponible calculada a partir del Total: {self.base_imponible}")
                    except ValueError as e:
                        self.base_imponible = 'No encontrado'
                        if self.debug_mode:
                            print(f"DEBUG: Error al calcular la base imponible a partir del Total: {e}")
                    return # Salimos una vez que encontramos el total y calculamos la base
        
        # Prioridad 2 (Fallback): Si no se encontró el "Total" o no se pudo calcular la base,
        # intentar extraer la Base Imponible directamente del "Neto"
        if self.base_imponible is None:
            if self.debug_mode:
                print("DEBUG: Total no encontrado o cálculo de base fallido. Intentando extraer Base Imponible desde 'Neto'.")
            base_iva_pattern = r"Neto\s*([\d.,]+\s*EUR)" # La base imponible es el "Neto"
            for line in self.lines:
                match_base = re.search(base_iva_pattern, line, re.IGNORECASE)
                if match_base:
                    base_str = match_base.group(1).replace('EUR', '').strip()
                    extracted_base = _extract_amount(base_str)
                    if extracted_base is not None:
                        self.base_imponible = str(extracted_base).replace('.', ',')
                        if self.debug_mode:
                            print(f"DEBUG: Base Imponible (Neto) extraída: {self.base_imponible}")
                        # Si encontramos la base por esta vía, y el importe no se ha establecido,
                        # podemos intentar calcular el importe inverso.
                        if self.importe is None:
                            try:
                                numeric_base = float(self.base_imponible.replace(',', '.'))
                                self.importe = str(numeric_base * (1 + VAT_RATE)).replace('.', ',')
                                if self.debug_mode:
                                    print(f"DEBUG: Importe calculado a partir de la Base (fallback): {self.importe}")
                            except ValueError:
                                self.importe = 'No encontrado'
                        return # Salimos una vez que encontramos la base

        # Extraer el importe de IVA si está disponible (esto es independiente del cálculo de base/importe)
        iva_pattern = r"IVA/IGIC\s*[\d.,]+%\s*([\d.,]+\s*EUR)"
        for line in self.lines:
            if self.iva_amount is None: # Usar self.iva_amount
                match_iva_amount = re.search(iva_pattern, line, re.IGNORECASE)
                if match_iva_amount:
                    iva_amount_str = match_iva_amount.group(1).replace('EUR', '').strip()
                    extracted_iva_amount = _extract_amount(iva_amount_str)
                    if extracted_iva_amount is not None:
                        self.iva_amount = str(extracted_iva_amount).replace('.', ',') # Guardar el monto de IVA
                        if self.debug_mode:
                            print(f"DEBUG: Importe de IVA extraído: {self.iva_amount}")
                        break # Salimos después de encontrar el IVA

        # Si aún no tenemos importe o base, usamos el fallback de la clase base.
        if self.importe is None or self.base_imponible is None:
            if self.debug_mode:
                print("DEBUG: Importe o base no encontrados con lógica específica de Adevinta. Recurriendo a la clase base.")
            super()._extract_importe_and_base()

    def extract_all(self):
        # Llamar a los métodos de extracción específicos
        self._extract_numero_factura()
        self._extract_fecha()
        self._extract_cif()
        self._extract_emisor()
        self._extract_cliente()
        self._extract_modelo()
        self._extract_matricula()
        self._extract_importe_and_base()

        # Devolver todos los atributos en el orden esperado por main_extractor.py
        # AdevintaExtractor no extrae 'tasas', por lo que devolvemos None para mantener la consistencia.
        return (self.tipo, self.fecha, self.numero_factura, self.emisor,self.cif_emisor, self.cliente, self.cif,
                self.modelo, self.matricula, self.importe, self.base_imponible, None) # Tasas como None
