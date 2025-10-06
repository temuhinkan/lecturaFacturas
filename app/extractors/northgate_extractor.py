import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_nif_cif, _calculate_base_from_total, VAT_RATE

class NorthgateExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)

    def _extract_emisor(self):
        for line in self.lines:
            if re.search(r"NORTHGATE ESPAÑA RENTING FLEXIBLE S\.A\.", line, re.IGNORECASE):
                self.emisor = "NORTHGATE ESPAÑA RENTING FLEXIBLE S.A."
                break

    def _extract_numero_factura(self):
        # Based on debug output, "FACTURA Nº" is on Line 3, and the number "VO-2025005930" is on Line 5.
        # So we need to find "FACTURA Nº" and then look a couple of lines ahead for the actual number.
        for i, line in enumerate(self.lines):
            if re.search(r"FACTURA N", line, re.IGNORECASE):
                # The actual number "VO-2025005930" is on line i+2 (Line 5 in debug output)
                if i + 2 < len(self.lines):
                    target_line = self.lines[i+2]
                    # Regex to capture "VO-2025005930" from "VO-2025005930NORTHGATE ESPAÑA RENTING FLEXIBLE S.A."
                    match = re.search(r"IMPORTE(VO-[A-Z0-9-]+)NORTHGATE", target_line)
                    if match:
                        self.numero_factura = match.group(1).strip()
                        break
        if self.numero_factura is None:
            super()._extract_numero_factura()

    def _extract_fecha(self):
        # Based on debug output, "FECHA" is on Line 4, and the date "29/05/25" is on Line 1
        # The date is also part of "29/05/25B85629020CALLE SIERRA DE ARACENA..." on line 1.
        # We need to extract the date from line 1 directly.
        if len(self.lines) > 1:
            date_line = self.lines[1]
            date_regex = r"(\d{2}/\d{2}/\d{2})"
            match = re.search(date_regex, date_line)
            if match:
                # Convert YY to YYYY (assuming 20xx for 25)
                year_short = match.group(1).split('/')[-1]
                if len(year_short) == 2:
                    full_date = match.group(1)[:-2] + "20" + year_short
                    self.fecha = full_date
                else:
                    self.fecha = match.group(1)
        if self.fecha is None:
            super()._extract_fecha()

    def _extract_modelo(self):
        # Extract model from "RENAULT KANGOO EXPRESS 1.5 DCI 55KW PROFESIONAL E6 (75CV)" on line 11
        for i, line in enumerate(self.lines):
            if i == 11 and "RENAULT KANGOO EXPRESS" in line:
                # Regex to capture the model from this specific line
                model_regex = r'([\d\.,]+)?\s*(RENAULT KANGOO EXPRESS 1\.5 DCI 55KW PROFESIONAL E6 \(75CV\))'
                match = re.search(model_regex, line, re.IGNORECASE)
                if match:
                    self.modelo = match.group(2).strip()
                    break
        if self.modelo is None:
            super()._extract_modelo()

    def _extract_matricula(self):
        # Extract license plate from "2343-LGT" which is on line 10
        for i, line in enumerate(self.lines):
            if i == 10:
                matricula_regex = r'([A-Z0-9-]+)'
                match = re.search(matricula_regex, line, re.IGNORECASE)
                if match:
                    self.matricula = match.group(1).strip()
                    break
        if self.matricula is None:
            super()._extract_matricula()

    def _extract_cif(self):
        # Extract CIF from "CIF/NIF: A28659423" on line 9
        for i, line in enumerate(self.lines):
            if i == 9 and "CIF/NIF:" in line:
                extracted_cif = _extract_nif_cif(line)
                if extracted_cif and extracted_cif != "B85629020":
                    self.cif = extracted_cif
                    break
        if self.cif is None:
            super()._extract_cif()

    def _extract_importe_and_base(self):
        # Extract total amount from "TOTAL FACTURA 7.470,01 6.173,56" on line 19
        for i, line in enumerate(self.lines):
            if i == 19 and "TOTAL FACTURA" in line:
                values = re.findall(r'(\d+(?:[.,]\d{3})*[.,]\d{2})', line)
                if len(values) >= 2:
                    self.importe = values[0]
                    self.base_imponible = values[1]
                break
        if self.importe is None or self.base_imponible is None:
            super()._extract_importe_and_base()
