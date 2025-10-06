import re
import os
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _calculate_base_from_total, VAT_RATE, _extract_from_line, extract_and_format_date

class BerolkemiExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        self.emisor = "BEROL KEMI, S.L"
        self.cif = "B79841052"
        self.vat_rate = VAT_RATE

    def _extract_emisor(self):
        pass

    def _extract_cif(self):
        for line in self.lines:
            match = re.search(r'C\.I\.F\.\s*([A-Z]?\d{7}[A-Z]?)', line)
            if match:
                extracted_cif = match.group(1).strip()
                if extracted_cif != self.cif: 
                    pass
                return

    def _extract_numero_factura(self):
        # El número de factura está dos líneas después de "Fecha Factura Serie/NºFactura"
        # Línea de ejemplo: "/ 25 1.628"
        for i, line in enumerate(self.lines):
            # Busca la línea de encabezado que contiene "Serie/NºFactura"
            if "Serie/NºFactura" in line:
                # Asegúrate de que hay al menos dos líneas más
                if i + 2 < len(self.lines):
                    invoice_number_candidate_line = self.lines[i+2].strip()
                    # Expresión regular para capturar los dos grupos de dígitos.
                    # Se permite un "/" opcional al inicio, luego el primer número,
                    # espacios, y el segundo número que puede tener puntos (miles).
                    match = re.search(r'/?\s*(\d+)\s*([\d.]+)', invoice_number_candidate_line)
                    if match:
                        # Une las dos partes, quitando el punto del segundo número
                        # (ej. "25" y "1.628" -> "25/1628")
                        self.numero_factura = f"{match.group(1)}/{match.group(2).replace('.', '')}"
                        return # Éxito, salimos de la función
        super()._extract_numero_factura() # Fallback si no se encontró

    def _extract_fecha(self):
        for i, line in enumerate(self.lines):
            if "Fecha Factura" in line:
                if i + 1 < len(self.lines):
                    date_line = self.lines[i+1]
                    fecha_match = re.search(r'(\d{2}/\d{2}/\d{4})', date_line)
                    if fecha_match:
                        self.fecha = fecha_match.group(1).strip()
                        return
        super()._extract_fecha()

    def _extract_cliente(self):
        for i, line in enumerate(self.lines):
            if "NEW SATELITE, S.L." in line:
                self.cliente = "NEW SATELITE, S.L."
                return
        super()._extract_cliente()

    def _extract_modelo(self):
        self.modelo = None

    def _extract_matricula(self):
        self.matricula = None

    def _extract_importe_and_base(self):
        # 1. Extraer el importe total con alta prioridad.
        found_importe = False
        for line in self.lines:
            importe_match = re.search(r'IMPORTE:\s*([\d.,]+)', line, re.IGNORECASE)
            if importe_match:
                self.importe = _extract_amount(importe_match.group(1))
                if self.importe is not None:
                    # Guardamos el valor numérico para el cálculo
                    numeric_importe_for_calc = self.importe
                    # Formateamos para la salida si es necesario, pero guardamos el numérico para cálculos
                    self.importe = str(self.importe).replace('.', ',') 
                    found_importe = True
                    break

        # 2. Si el importe total se encontró, calcular la base imponible a partir de él.
        if found_importe and numeric_importe_for_calc is not None:
            try:
                # _calculate_base_from_total espera una cadena con coma o punto para el total.
                # Asegúrate de que _calculate_base_from_total maneje correctamente el tipo de dato.
                # Aquí lo convertimos a cadena y luego la función lo procesará.
                calculated_base = _calculate_base_from_total(str(numeric_importe_for_calc).replace('.', ','), self.vat_rate)
                if calculated_base is not None:
                    self.base_imponible = str(calculated_base).replace('.', ',')
                else:
                    self.base_imponible = 'No calculado' # En caso de que el cálculo falle por alguna razón
            except Exception as e:
                print(f"Error calculando base imponible desde importe: {e}")
                self.base_imponible = 'Error de cálculo'
        
        # 3. Fallback para la base imponible si no se pudo calcular desde el importe total
        # (Esto solo se ejecutaría si found_importe es False, o si el cálculo falló y base_imponible es None)
        if self.base_imponible is None or self.base_imponible == 'No calculado' or self.base_imponible == 'Error de cálculo':
            for line in self.lines:
                base_match = re.search(r'B\.\s*IMPONIBLE\s*(?:% I\.V\.A\.)?\s*([\d.,]+)', line, re.IGNORECASE)
                if base_match:
                    extracted_base = _extract_amount(base_match.group(1))
                    if extracted_base is not None:
                        self.base_imponible = str(extracted_base).replace('.', ',')
                        break
        
        # Último fallback si aún no tenemos importe o base
        if self.importe is None or self.base_imponible is None:
            super()._extract_importe_and_base()