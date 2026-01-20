import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_nif_cif, _calculate_base_from_total, VAT_RATE, _extract_from_line, _extract_from_lines_with_keyword, extract_and_format_date

class OscaroExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None, debug_mode=False):
        super().__init__(lines, pdf_path)
        self.emisor = "Oscaro Recambios S.L" # Nombre del emisor fijo para Oscaro
        self.debug_mode = debug_mode
        self.cliente = None # Inicializar cliente para asegurar que siempre esté definido

    def _extract_emisor(self):
        # El emisor es fijo para esta clase, no necesita extracción de las líneas
        pass

    def _extract_numero_factura(self):
        # Patrón para buscar "Factura: VFT1602802193"
        invoice_number_pattern = r"Factura\s*:\s*([A-Z0-9]+)"
        for line in self.lines:
            match = re.search(invoice_number_pattern, line, re.IGNORECASE)
            if match:
                print(f"mach:")
                self.numero_factura = match.group(1).strip()
                if self.debug_mode:
                    print(f"DEBUG: Número de factura extraído: {self.numero_factura}")
                return
        # Si no se encuentra, se recurre al método de la clase base
        super()._extract_numero_factura()
        if self.debug_mode and not self.numero_factura:
            print("DEBUG: Número de factura no encontrado con la lógica específica de Oscaro.")


    def _extract_fecha(self):
        # La fecha ya se extrae bien con la clase genérica según tu comentario,
        # así que podemos dejar que la clase base se encargue de ello.
        # Si fuera necesario un patrón específico, se sobrescribiría aquí.
        super()._extract_fecha()


    def _extract_cif(self):
        # Patrón para buscar "CIF B64314222"
        cif_pattern = r"CIF\s*([A-Z0-9]{9})"
        for line in self.lines:
            match = re.search(cif_pattern, line, re.IGNORECASE)
            if match:
                self.cif = match.group(1).strip()
                if self.debug_mode:
                    print(f"DEBUG: CIF extraído: {self.cif}")
                return
        # Si no se encuentra, se recurre al método de la clase base
        super()._extract_cif()
        if self.debug_mode and not self.cif:
            print("DEBUG: CIF no encontrado con la lógica específica de Oscaro.")

    def _extract_cliente(self):
        # Patrones para buscar el nombre del cliente (ej. "NEW SATELITE SL", "Newsatelite s I")
        # Se busca en las líneas que contienen "NIF:" o "Dirección de la factura"
        cliente_patterns = [
            r"(?:NEW\s*SATELITE\s*SL)",
            r"(?:Newsatelite\s*s\s*I)"
        ]
        
        for i, line in enumerate(self.lines):
            # Buscar el nombre del cliente cerca de "NIF:" o "Dirección de la factura"
            if re.search(r"NIF:|Dirección de la factura", line, re.IGNORECASE):
                # Buscar en la línea actual y algunas siguientes
                for j in range(i, min(i + 5, len(self.lines))):
                    for pattern in cliente_patterns:
                        match = re.search(pattern, self.lines[j], re.IGNORECASE)
                        if match:
                            self.cliente = match.group(0).strip()
                            if self.debug_mode:
                                print(f"DEBUG: Cliente extraído: {self.cliente}")
                            return
        
        # Si no se encuentra con la lógica específica, self.cliente permanecerá como None.
        # No se llama a super()._extract_cliente() porque BaseInvoiceExtractor no tiene este método.
        if self.debug_mode and not self.cliente:
            print("DEBUG: Cliente no encontrado con la lógica específica de Oscaro.")


    def _extract_modelo(self):
        # No se especifica un modelo en este tipo de factura,
        # así que podemos dejar que la clase base lo maneje (probablemente resultará en 'No encontrado').
        super()._extract_modelo()

    def _extract_matricula(self):
        # No se especifica una matrícula en este tipo de factura,
        # así que podemos dejar que la clase base lo maneje (probablemente resultará en 'No encontrado').
        super()._extract_matricula()

    def _extract_importe_and_base(self):
        # Según tu comentario, los importes se extraen bien con la clase genérica.
        # Sin embargo, vamos a implementar una lógica específica para "Total IVA incl."
        # y luego calcular la base a partir de ahí.
        if self.debug_mode:
            print("DEBUG: Entering _extract_importe_and_base for OscaroExtractor")

        total_iva_incl_found = False
        for i, line in enumerate(self.lines):
            # Buscar "Total IVA incl." y extraer el valor de la misma línea
            match = re.search(r"Total IVA incl\.\s*:\s*([\d.,]+\s*€)", line, re.IGNORECASE)
            if match:
                importe_str = match.group(1).replace('€', '').strip()
                extracted_importe = _extract_amount(importe_str)
                if extracted_importe is not None:
                    self.importe = str(extracted_importe).replace('.', ',')
                    total_iva_incl_found = True
                    if self.debug_mode:
                        print(f"DEBUG: Importe (Total IVA incl.) extraído: {self.importe}")
                    break
        
        # Calcular la base imponible si el importe fue encontrado
        if self.importe:
            try:
                numeric_importe = float(self.importe.replace(',', '.'))
                # Usamos VAT_RATE para calcular la base a partir del importe total (IVA incluido)
                calculated_base = _calculate_base_from_total(str(numeric_importe).replace('.', ','), VAT_RATE)
                self.base_imponible = calculated_base
                if self.debug_mode:
                    print(f"DEBUG: Base imponible calculada: {self.base_imponible}")
            except ValueError as e:
                self.base_imponible = 'No encontrado'
                if self.debug_mode:
                    print(f"DEBUG: Error al calcular la base imponible: {e}")
        
        # Si no se encontró el importe o la base, o si la lógica específica falla,
        # se recurre al método de la clase base como último recurso.
        if self.importe is None or self.base_imponible is None:
            if self.debug_mode:
                print("DEBUG: Importe o base no encontrados con lógica específica de Oscaro. Recurriendo a la clase base.")
            super()._extract_importe_and_base()

    def extract_all(self):
        # Llamar a los métodos de extracción específicos
        self._extract_numero_factura()
        self._extract_fecha()
        self._extract_cif()
        self._extract_emisor() # Llama a la implementación de OscaroExtractor (fija)
        self._extract_cliente() # Ahora llama al método _extract_cliente de OscaroExtractor
        self._extract_modelo()
        self._extract_matricula()
        self._extract_importe_and_base()

        # Devolver todos los atributos en el orden esperado por main_extractor.py
        # Nota: OscaroExtractor no extrae 'tasas' directamente de la misma manera que Pradilla,
        # por lo que devolvemos None para 'tasas' para mantener la consistencia de la tupla de 11 elementos.
        return (self.tipo, self.fecha, self.numero_factura, self.emisor, self.cliente, self.cif,
                self.modelo, self.matricula, self.importe, self.base_imponible, None) # Tasas como None
