import re
import os
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_nif_cif, _calculate_base_from_total, VAT_RATE, _extract_from_line, extract_and_format_date

class CantelarExtractor(BaseInvoiceExtractor): # Asegúrate de que el nombre de la clase sea el correcto
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        self.emisor = "ACCESORIOS PARA VEHICULOS CANTELAR, S.L." # Ajusta si el nombre es ligeramente diferente
        self.cif = "B75526939" # CIF de Cantelar

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
        # Extraer el número de factura directamente del nombre del archivo PDF.
        # Formato esperado: "Factura X-YYYYYY_cualquier_cosa.pdf"
        if self.pdf_path:
            file_name = os.path.basename(self.pdf_path)
            # Patrón para capturar "X-YYYYYY"
            # Ahora, la parte '_candelar' es opcional o flexible.
            # Usamos `_.*\.pdf` para que coincida con cualquier sufijo antes de .pdf
            # o simplemente `\.pdf` si no siempre hay un sufijo
            
            # Opción 1: Si siempre hay un sufijo (ej. _cantelar, _candelar, _algo)
            # match = re.search(r'Factura\s*(\d+-\d+)_\w+\.pdf', file_name, re.IGNORECASE)
            
            # Opción 2: Más flexible, solo busca el patrón antes de la extensión .pdf
            match = re.search(r'Factura\s*(\d+-\d+)[_ -]?[a-zA-Z0-9]*\.pdf', file_name, re.IGNORECASE)
            # Explicación del nuevo patrón:
            # [\d+-\d+] Ya lo tenemos
            # [_ -]? : Un guion bajo o un espacio, opcional (para cubrir casos como "Factura 6-003001.pdf" o "Factura 6-003001 - Copia.pdf")
            # [a-zA-Z0-9]* : Cero o más caracteres alfanuméricos (para "cantelar", "candelar", "copia", etc.)
            # \.pdf : La extensión del archivo.
            
            if match:
                self.numero_factura = match.group(1).strip()
                return
        # Si no se encuentra en el nombre del archivo, intentar el fallback de la clase base.
        super()._extract_numero_factura()


    def _extract_fecha(self):
        for line in self.lines:
            fecha_match = re.search(r'(\d{2}/\d{2}/\d{4})', line)
            if fecha_match:
                self.fecha = fecha_match.group(1).strip()
                return
        super()._extract_fecha()


    def _extract_cliente(self):
        for line in self.lines:
            if "NEW SATELITE SL" in line:
                self.cliente = "NEW SATELITE SL"
                return
        super()._extract_cliente()


    def _extract_modelo(self):
        self.modelo = None


    def _extract_matricula(self):
        self.matricula = None


    def _extract_importe_and_base(self):
        found_importe = False
        for line in self.lines:
            importe_match = re.search(r'TOTAL:\s*Factura\s*([\d.,]+)', line, re.IGNORECASE)
            if not importe_match:
                importe_match = re.search(r'(\d{2}/\d{2}/\d{4})\s*([\d.,]+)', line)
            
            if importe_match:
                if importe_match.groups() and len(importe_match.groups()) > 1:
                     self.importe = _extract_amount(importe_match.group(2))
                else:
                    self.importe = _extract_amount(importe_match.group(1))

                if self.importe is not None:
                    numeric_importe_for_calc = self.importe
                    self.importe = str(self.importe).replace('.', ',')
                    found_importe = True
                    break

        if found_importe and numeric_importe_for_calc is not None:
            try:
                calculated_base = _calculate_base_from_total(str(numeric_importe_for_calc).replace('.', ','), self.vat_rate)
                if calculated_base is not None:
                    self.base_imponible = str(calculated_base).replace('.', ',')
            except Exception as e:
                print(f"Error calculando base imponible desde importe en CantelarExtractor: {e}")
                self.base_imponible = 'Error de cálculo'

        if self.base_imponible is None or self.base_imponible == 'Error de cálculo':
            for line in self.lines:
                base_match = re.search(r'BASE I\.V\.A\.\s*R\.E\.\s*([\d.,]+)', line, re.IGNORECASE)
                if base_match:
                    extracted_base = _extract_amount(base_match.group(1))
                    if extracted_base is not None:
                        self.base_imponible = str(extracted_base).replace('.', ',')
                        break
                base_match_line20 = re.search(r'^([\d.,]+)\s*[\d.,]+\s*21,00\s*[\d.,]+$', line.strip())
                if base_match_line20:
                    self.base_imponible = str(_extract_amount(base_match_line20.group(1))).replace('.', ',')
                    break

        if self.importe is None or self.base_imponible is None:
            super()._extract_importe_and_base()