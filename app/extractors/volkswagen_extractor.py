import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_nif_cif, _calculate_base_from_total, VAT_RATE, _extract_from_line, _extract_from_lines_with_keyword, extract_and_format_date

class VolkswagenExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        self.emisor = "VOLKSWAGEN RENTING, S.A."
        self.cif = "A80185051" # CIF del emisor
        self.iva = None
        self.vat_rate = VAT_RATE
        print(f"DEBUG VOLKSWAGEN: CIF Emisor inicializado: {self.cif}")

    def _extract_emisor(self):
        pass

    def _extract_numero_factura(self):
        print("DEBUG VOLKSWAGEN: Intentando extraer Número de Factura...")
        self.numero_factura = _extract_from_lines_with_keyword(
            self.lines, 
            r'Nº Factura', 
            r'(\d+)',
            look_ahead=1
        )
        if self.numero_factura:
            self.numero_factura = self.numero_factura.strip()
            print(f"DEBUG VOLKSWAGEN: Número de Factura encontrado: {self.numero_factura}")
            return
        print("DEBUG VOLKSWAGEN: Número de Factura no encontrado.")
        super()._extract_numero_factura()

    def _extract_fecha(self):
        print("DEBUG VOLKSWAGEN: Intentando extraer Fecha...")
        fecha_raw = _extract_from_lines_with_keyword(
            self.lines,
            r'Fecha',
            r'(\d{2}-\d{2}-\d{4})', 
            look_ahead=1
        )
        if fecha_raw:
            day, month, year = fecha_raw.split('-')
            self.fecha = f"{day}/{month}/{year}"
            print(f"DEBUG VOLKSWAGEN: Fecha encontrada: {self.fecha}")
            return
        print("DEBUG VOLKSWAGEN: Fecha no encontrada.")
        super()._extract_fecha()

    def _extract_cif(self):
        # Se mantiene el CIF del emisor (A80185051)
        print(f"DEBUG VOLKSWAGEN: Verificando CIF. Se mantiene el CIF del Emisor: {self.cif}")
        pass

    def _extract_cliente(self):
        # Cliente: NEW SATELITE, SL.
        print("DEBUG VOLKSWAGEN: Intentando extraer Cliente...")
        for i, line in enumerate(self.lines):
            if "Cliente:" in line and i + 1 < len(self.lines):
                client_name_line = self.lines[i+1].strip()
                match = re.match(r'([A-Z\s,.]+?)(?:CL|AV|C/|\d)', client_name_line, re.IGNORECASE)
                if match:
                    self.cliente = match.group(1).strip().replace('.', '')
                    print(f"DEBUG VOLKSWAGEN: Cliente encontrado: {self.cliente}")
                    return
                else: 
                     self.cliente = client_name_line
                     print(f"DEBUG VOLKSWAGEN: Cliente encontrado (sin regex): {self.cliente}")
                     return
        super()._extract_cliente()


    def _extract_modelo(self):
        # L26: Modelo, L27: : SKODA FABIA
        print("DEBUG VOLKSWAGEN: Intentando extraer Modelo...")
        self.modelo = _extract_from_lines_with_keyword(
            self.lines, 
            r'Modelo', 
            r'(.+)', 
            look_ahead=1 
        )
        if self.modelo:
            self.modelo = self.modelo.strip().lstrip(':').strip()
            print(f"DEBUG VOLKSWAGEN: Modelo encontrado y asignado: {self.modelo}")
            return
        print("DEBUG VOLKSWAGEN: Modelo no encontrado.")
        super()._extract_modelo()


    def _extract_matricula(self):
        # L22: Matrícula, L23: : 6150KYY
        print("DEBUG VOLKSWAGEN: Intentando extraer Matrícula...")
        self.matricula = _extract_from_lines_with_keyword(
            self.lines, 
            r'Matrícula', 
            r'([A-Z0-9]+)',
            look_ahead=1
        )
        if self.matricula:
            self.matricula = self.matricula.strip()
            print(f"DEBUG VOLKSWAGEN: Matrícula encontrada y asignada: {self.matricula}")
            return
        print("DEBUG VOLKSWAGEN: Matrícula no encontrada.")
        super()._extract_matricula()


    def _extract_importe_and_base(self):
        
        print("\nDEBUG VOLKSWAGEN: INICIO EXTRACCIÓN DE IMPORTES")
        
        # 1. Extraer Importe Total (TOTAL FACTURA)
        importe_str_raw = _extract_from_lines_with_keyword(
            self.lines, 
            r'TOTAL FACTURA', 
            r'([\d.,]+\s*€)', 
            look_ahead=2 # L36 -> L38
        )
        print(f"DEBUG VOLKSWAGEN: Importe Total (RAW) encontrado por keyword: '{importe_str_raw}'")

        if importe_str_raw:
            self.importe = _extract_amount(importe_str_raw)
            print(f"DEBUG VOLKSWAGEN: _extract_amount devolvió: '{self.importe}'")
            if self.importe is not None:
                # 🟢 FIX CRÍTICO: Eliminar el separador de miles (punto) para el formato '8300,00'
                self.importe = str(self.importe).replace('.', '') 
                print(f"DEBUG VOLKSWAGEN: Importe Total ASIGNADO (Limpio): {self.importe}")

        # 2. Extraer Base Imponible
        base_str_raw = _extract_from_lines_with_keyword(
            self.lines, 
            r'TOTAL BASE IMPONIBLE', 
            r'([\d.,]+\s*€)', 
            look_ahead=2 # L30 -> L32
        )
        print(f"DEBUG VOLKSWAGEN: Base Imponible (RAW) encontrado por keyword: '{base_str_raw}'")

        if base_str_raw:
            self.base_imponible = _extract_amount(base_str_raw)
            print(f"DEBUG VOLKSWAGEN: _extract_amount devolvió: '{self.base_imponible}'")
            if self.base_imponible is not None:
                # 🟢 FIX CRÍTICO: Eliminar el separador de miles (punto) para el formato '6859,50'
                self.base_imponible = str(self.base_imponible).replace('.', '')
                print(f"DEBUG VOLKSWAGEN: Base Imponible ASIGNADA (Limpia): {self.base_imponible}")


        # 3. Calcular IVA (La lógica de cálculo ahora funciona con las cadenas limpias)
        if self.importe and self.base_imponible:
            print("DEBUG VOLKSWAGEN: Calculando IVA a partir de Importe y Base...")
            try:
                # '8300,00'.replace(',', '.') -> '8300.00' (Correcto para float())
                importe_float = float(self.importe.replace(',', '.')) 
                base_float = float(self.base_imponible.replace(',', '.'))
                
                iva_float = importe_float - base_float
                
                # Asignar el IVA
                self.iva = f"{iva_float:.2f}".replace('.', ',')
                print(f"DEBUG VOLKSWAGEN: IVA calculado y ASIGNADO: {self.iva}")
            except ValueError as e:
                print(f"DEBUG VOLKSWAGEN: ERROR al calcular IVA (ValueError): {e}")
                self.iva = None
        
        print("DEBUG VOLKSWAGEN: FIN EXTRACCIÓN DE IMPORTES\n")