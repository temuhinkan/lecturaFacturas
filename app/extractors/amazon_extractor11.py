import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_nif_cif, _calculate_base_from_total, VAT_RATE, _extract_from_line, _extract_from_lines_with_keyword, extract_and_format_date

class AmazonExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None, debug_mode=False):
        super().__init__(lines, pdf_path)
        self.emisor = None # El emisor será dinámico
        self.debug_mode = debug_mode
        self.cliente = None # Inicializar cliente para asegurar que siempre esté definido


    def _extract_emisor(self):
        # El emisor está después de "Vendido por"
        emisor_pattern = r"Vendido por\s*(.+)"
        for line in self.lines:
            match = re.search(emisor_pattern, line, re.IGNORECASE)
            if match:
                # Capturamos el resto de la línea después de "Vendido por"
                self.emisor = match.group(1).strip()
                # Limpiar el emisor de cualquier "IVA" o "Nº de referencia de pago" que pueda estar en la misma línea
                self.emisor = re.sub(r"IVA\s*[A-Z0-9]+", "", self.emisor, flags=re.IGNORECASE).strip()
                self.emisor = re.sub(r"Nº de referencia de pago\s*[A-Z0-9]+", "", self.emisor, flags=re.IGNORECASE).strip()

                self.emisor += " (AMAZON)"
                if self.debug_mode:
                    print(f"DEBUG: Emisor extraído: {self.emisor}")
                return
        # Si no se encuentra, se recurre al método de la clase base
        super()._extract_emisor()
        if self.debug_mode and not self.emisor:
            print("DEBUG: Emisor no encontrado con la lógica específica de Amazon.")

    def _extract_numero_factura(self):
        # Patrón para buscar "Número del documento"
        # Incluye el guion '-' en el conjunto de caracteres para capturar el número completo
        invoice_number_pattern_doc = r"Número del documento\s*([A-Z0-9-]+)"
        # Patrón para buscar "Número de la factura"
        # Incluye el guion '-' en el conjunto de caracteres para capturar el número completo
        invoice_number_pattern_fact = r"Número de la factura\s*([A-Z0-9-]+)"

        for line in self.lines:
            # Intento 1: Buscar "Número del documento"
            match = re.search(invoice_number_pattern_doc, line, re.IGNORECASE)
            if match:
                self.numero_factura = match.group(1).strip()
                if self.debug_mode:
                    print(f"DEBUG: Número de factura extraído (Número del documento): {self.numero_factura}")
                return
            
            # Intento 2: Buscar "Número de la factura"
            match = re.search(invoice_number_pattern_fact, line, re.IGNORECASE)
            if match:
                self.numero_factura = match.group(1).strip()
                if self.debug_mode:
                    print(f"DEBUG: Número de factura extraído (Número de la factura): {self.numero_factura}")
                return

        # Si no se encuentra con ninguno de los patrones específicos, se recurre al método de la clase base
        super()._extract_numero_factura()
        if self.debug_mode and not self.numero_factura:
            print("DEBUG: Número de factura no encontrado con la lógica específica de Amazon.")

    def _extract_fecha(self):
        # Mapeo de meses en español a números (ya presente)
        month_map = {
            'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04',
            'mayo': '05', 'junio': '06', 'julio': '07', 'agosto': '08',
            'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'
        }

        # **NUEVA LÓGICA: Extraer "Fecha del pedido" o "Fecha de la factura/Fecha de la entrega"**
        # Patrón para "Fecha del pedido" (DD.MM.YYYY)
        date_pedido_pattern = r"Fecha del pedido\s*(\d{2}\.\d{2}\.\d{4})"
        # Patrón para "Fecha de la factura/Fecha de la entrega" (DD.MM.YYYY)
        date_factura_entrega_pattern = r"Fecha de la factura/Fecha\s*de la entrega\s*(\d{2}\.\d{2}\.\d{4})"

        for line in self.lines:
            # Intento 1: Buscar "Fecha del pedido"
            match = re.search(date_pedido_pattern, line, re.IGNORECASE)
            if match:
                date_str = match.group(1).replace('.', '/') # Cambiar a formato DD/MM/YYYY
                self.fecha = date_str
                if self.debug_mode:
                    print(f"DEBUG: Fecha extraída (Fecha del pedido): {self.fecha}")
                return

            # Intento 2: Buscar "Fecha de la factura/Fecha de la entrega"
            match = re.search(date_factura_entrega_pattern, line, re.IGNORECASE)
            if match:
                date_str = match.group(1).replace('.', '/') # Cambiar a formato DD/MM/YYYY
                self.fecha = date_str
                if self.debug_mode:
                    print(f"DEBUG: Fecha extraída (Fecha de la factura/Fecha de la entrega): {self.fecha}")
                return

        # Lógica original para meses con nombre (si las anteriores no encuentran)
        date_pattern_named_month = r"Fecha del pedido\s*(.+)" # Este patrón coge cualquier cosa después de "Fecha del pedido"
        for line in self.lines:
            match = re.search(date_pattern_named_month, line, re.IGNORECASE)
            if match:
                date_str = match.group(1).strip()
                parts = date_str.split()
                if len(parts) == 3:
                    day = parts[0]
                    month_name = parts[1].lower()
                    year = parts[2]
                    if month_name in month_map:
                        numeric_month = month_map[month_name]
                        formatted_date_str = f"{day}/{numeric_month}/{year}"
                        self.fecha = formatted_date_str
                        if self.debug_mode:
                            print(f"DEBUG: Fecha formateada (Fecha del pedido - nombre de mes): {self.fecha}")
                        return

        # Fallback a la lógica de la clase base si no se encuentra con ninguno de los patrones específicos
        super()._extract_fecha()
        if self.debug_mode and not self.fecha:
            print("DEBUG: Fecha no encontrada con la lógica específica de Amazon.")


    def _extract_cif(self):
        # El CIF está después de "IVA" y en la línea después de "Vendido por"
        # Primero, encontramos la línea "Vendido por"
        for i, line in enumerate(self.lines):
            if re.search(r"Vendido por", line, re.IGNORECASE):
                # Buscamos en las siguientes 3 líneas para encontrar el CIF después de "IVA"
                for j in range(i + 1, min(i + 4, len(self.lines))):
                    cif_pattern = r"IVA\s*([A-Z]{2}[A-Z0-9]{9})" # Ej. ESW0184081H, ESN0681779E
                    match = re.search(cif_pattern, self.lines[j], re.IGNORECASE)
                    if match:
                        self.cif = match.group(1).strip()
                        if self.debug_mode:
                            print(f"DEBUG: CIF extraído: {self.cif}")
                        return
        # Si no se encuentra, se recurre al método de la clase base
        super()._extract_cif()
        if self.debug_mode and not self.cif:
            print("DEBUG: CIF no encontrado con la lógica específica de Amazon.")

    def _extract_cliente(self):
        # El cliente para las facturas de Amazon siempre será "NEWSATELITE SL"
        self.cliente = "NEWSATELITE SL"
        if self.debug_mode:
            print(f"DEBUG: Cliente fijado a: {self.cliente}")


    def _extract_modelo(self):
        # No se especifica un modelo en este tipo de factura.
        super()._extract_modelo()

    def _extract_matricula(self):
        # No se especifica una matrícula en este tipo de factura.
        super()._extract_matricula()

    def _extract_importe_and_base(self):
        # Los importes se extraen correctamente con la clase genérica.
        # Sin embargo, podemos añadir una lógica específica para "Total pendiente" si es necesario.
        # Basado en la salida de debug, "Total pendiente" parece ser el importe total.
        if self.debug_mode:
            print("DEBUG: Entering _extract_importe_and_base for AmazonExtractor")

        # Intentar extraer el "Total pendiente" como importe
        total_pendiente_pattern = r"Total pendiente\s*([\d.,]+\s*€)"
        for line in self.lines:
            match = re.search(total_pendiente_pattern, line, re.IGNORECASE)
            if match:
                importe_str = match.group(1).replace('€', '').strip()
                extracted_importe = _extract_amount(importe_str)
                if extracted_importe is not None:
                    self.importe = str(extracted_importe).replace('.', ',')
                    if self.debug_mode:
                        print(f"DEBUG: Importe (Total pendiente) extraído: {self.importe}")
                    
                    # Calcular la Base Imponible a partir del Importe Total (IVA incluido)
                    try:
                        numeric_importe = float(self.importe.replace(',', '.'))
                        calculated_base = _calculate_base_from_total(str(numeric_importe).replace('.', ','), VAT_RATE)
                        self.base_imponible = calculated_base
                        if self.debug_mode:
                            print(f"DEBUG: Base Imponible calculada a partir del Total: {self.base_imponible}")
                    except ValueError as e:
                        self.base_imponible = 'No encontrado'
                        if self.debug_mode:
                            print(f"DEBUG: Error al calcular la base imponible a partir del Total: {e}")
                    return # Salimos una vez que encontramos el total y calculamos la base

        # Fallback a la lógica de la clase base si no se encuentra "Total pendiente"
        if self.importe is None or self.base_imponible is None:
            if self.debug_mode:
                print("DEBUG: Importe o base no encontrados con lógica específica de Amazon. Recurriendo a la clase base.")
            super()._extract_importe_and_base()

    def extract_all(self):
        # Llamar a los métodos de extracción específicos
        self._extract_emisor()
        self._extract_numero_factura()
        self._extract_fecha()
        self._extract_cif()
        self._extract_cliente()
        self._extract_modelo() # No aplica
        self._extract_matricula() # No aplica
        self._extract_importe_and_base() # Se extrae bien con la genérica o la específica de Total pendiente

        # Devolver todos los atributos en el orden esperado por main_extractor.py
        # AmazonExtractor no extrae 'tasas', por lo que devolvemos None para mantener la consistencia.
        return (self.tipo, self.fecha, self.numero_factura, self.emisor, self.cliente, self.cif,
                self.modelo, self.matricula, self.importe, self.base_imponible, None) # Tasas como None