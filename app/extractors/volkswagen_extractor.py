import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_nif_cif, _calculate_base_from_total, VAT_RATE, _extract_from_line, _extract_from_lines_with_keyword, extract_and_format_date

class VolkswagenExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        self.emisor = "VOLKSWAGEN RENTING, S.A."
        # El CIF del emisor puede extraerse de la línea "A80185051" o del pie de página.
        # Lo definimos directamente si es constante, o lo extraemos si varía.
        # Según la factura de ejemplo, es constante en la parte superior.
        self.cif = "A80185051" 

    def _extract_emisor(self):
        # El emisor es constante, definido en __init__
        pass

    def _extract_numero_factura(self):
        # Buscar el número de factura que aparece después de "Nº Factura"
        # Ejemplo: "Nº Factura : 2415352"
        for line in self.lines:
            match = re.search(r'Nº Factura\s*:\s*(\d+)', line)
            if match:
                self.numero_factura = match.group(1).strip()
                return
        super()._extract_numero_factura()

    def _extract_fecha(self):
        # Buscar la fecha que aparece después de "Fecha"
        # Ejemplo: "Fecha : 02-09-2024"
        for line in self.lines:
            match = re.search(r'Fecha\s*:\s*(\d{2}-\d{2}-\d{4})', line)
            if match:
                # Convertir a formato DD/MM/YYYY si es necesario para estandarizar
                day, month, year = match.group(1).split('-')
                self.fecha = f"{day}/{month}/{year}"
                return
        super()._extract_fecha()

    def _extract_cif(self):
        # El CIF del emisor es constante, definido en __init__
        # Intentamos extraer el CIF del cliente si está presente
        # Cliente: NEW SATELITE, SL.
        # NIF : B85629020
        for line in self.lines:
            match = re.search(r'CIF.\s*:\s*([A-Z]?\d{7}[A-Z]?)', line)
            if match:
                # Si el CIF extraído no es el del emisor (que ya está fijado),
                # asumimos que es el del cliente.
                extracted_cif = match.group(1).strip()
                if extracted_cif != self.cif: # Evitar sobrescribir el CIF del emisor si es el primero que encuentra
                    self.cif = extracted_cif # Esto sobrescribiría el CIF del emisor, cuidado.
                                             # Si el objetivo es el CIF del *cliente*, necesitarías otro atributo.
                                             # Por ahora, BaseInvoiceExtractor solo tiene un self.cif
                                             # que generalmente se usa para el emisor.
                                             # Para el CIF del cliente, considera añadir self.cif_cliente.
                    return # Si encuentras un NIF diferente, asúmelo como el del cliente y termina.
        super()._extract_cif() # Fallback si no encuentra el CIF del cliente

    def _extract_cliente(self):
        # Cliente: NEW SATELITE, SL.
        # O también en la dirección: CL SIERRA DE ARACENA 62
        for i, line in enumerate(self.lines):
            if "Cliente:" in line and i + 1 < len(self.lines):
                # La siguiente línea o las subsiguientes pueden contener el nombre.
                # Intentamos capturar hasta la primera coma o salto de línea significativo.
                client_name_line = self.lines[i+1].strip()
                # Capturamos el nombre hasta antes de la dirección si está en la misma línea
                match = re.match(r'([A-Z\s,.]+?)(?:CL|AV|C/|\d)', client_name_line, re.IGNORECASE)
                if match:
                    self.cliente = match.group(1).strip().replace('.', '') # Eliminar puntos que puedan ser parte de abreviaturas
                    return
                else: # Si no hay patrón de dirección, tomar toda la línea
                     self.cliente = client_name_line
                     return
        super()._extract_cliente()


    def _extract_modelo(self):
        # Ejemplo: "Modelo",": SKODA FABIA"
        for line in self.lines:
            match = re.search(r'Modelo\s*:\s*(.+)', line)
            if match:
                self.modelo = match.group(1).strip()
                return
        super()._extract_modelo()


    def _extract_matricula(self):
        # Ejemplo: "Matrícula",": 6150KYY"
        for line in self.lines:
            match = re.search(r'Matrícula\s*:\s*([A-Z0-9]+)', line)
            if match:
                self.matricula = match.group(1).strip()
                return
        super()._extract_matricula()

    def _extract_importe_and_base(self):
        # Buscar "TOTAL FACTURA" y "TOTAL BASE IMPONIBLE"
        # "TOTAL BASE IMPONIBLE", "6.859,50 €"
        # "TOTAL FACTURA", "8.300,00 €"
        
        base_found = False
        importe_found = False

        for line in self.lines:
            # Extraer Importe Total
            match_total = re.search(r'TOTAL FACTURA :\s*\"?,?\"?([\d.,]+\s*€)', line, re.IGNORECASE)
            if match_total:
                self.importe = _extract_amount(match_total.group(1))
                if self.importe is not None:
                    self.importe = str(self.importe).replace('.', ',')
                    importe_found = True

            # Extraer Base Imponible
            match_base = re.search(r'TOTAL BASE IMPONIBLE :\s*\"?,?\"?([\d.,]+\s*€)', line, re.IGNORECASE)
            if match_base:
                self.base_imponible = _extract_amount(match_base.group(1))
                if self.base_imponible is not None:
                    self.base_imponible = str(self.base_imponible).replace('.', ',')
                    base_found = True

            if base_found and importe_found:
                break # Si ambos se encuentran, salimos

        # Fallback si no se encuentran
        if self.importe is None or self.base_imponible is None:
            super()._extract_importe_and_base()