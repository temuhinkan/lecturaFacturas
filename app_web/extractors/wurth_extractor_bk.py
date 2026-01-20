import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_nif_cif, _calculate_base_from_total, VAT_RATE, _extract_from_line

class WurthExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        self.vat_rate = VAT_RATE

    def _extract_emisor(self):
        # Fijar directamente el emisor. Para este tipo de factura, es constante.
        self.emisor = "WÜRTH ESPAÑA, S.A."
        self.cif_emisor = "A08472276"
        self.cif="B85629020"
        print(f"TRAZA: Emisor fijado: {self.emisor}")

    def _extract_numero_factura(self):
        # Lógica: Buscar 'Nº factura' (L30) y tomar el valor en la línea siguiente (L31: 4733937515)
        print("--- TRAZA: _extract_numero_factura ---")
        for i, line in enumerate(self.lines):
            # Busca la etiqueta "Nº factura" en una línea propia
            if re.search(r"^\s*Nº factura\s*$", line.strip(), re.IGNORECASE):
                print(f"TRAZA: 'Nº factura' encontrado en línea {i}")
                # El valor está 1 línea después
                target_index = i + 1
                if target_index < len(self.lines):
                    num_line = self.lines[target_index].strip()
                    print(f"TRAZA: Línea {target_index} (Valor): '{num_line}'")
                    # Patrón para capturar solo dígitos
                    num_match = re.search(r'(\d+)', num_line)
                    if num_match:
                        self.numero_factura = num_match.group(1).strip()
                        print(f"TRAZA: Número de Factura extraído: {self.numero_factura}")
                        return
        self.numero_factura = None
        print(f"TRAZA: Número de Factura final: {self.numero_factura}")

    def _extract_fecha(self):
        # Lógica: Buscar 'Fecha' (L36) y tomar el valor en la línea siguiente (L37: 22.04.2025)
        print("--- TRAZA: _extract_fecha ---")
        date_pattern = r'(\d{2}[-./]\d{2}[-./]\d{4})'
        for i, line in enumerate(self.lines):
            # Busca la etiqueta "Fecha" en una línea propia
            if re.search(r"^\s*Fecha\s*$", line.strip(), re.IGNORECASE):
                print(f"TRAZA: 'Fecha' encontrado en línea {i}")
                # El valor está 1 línea después
                target_index = i + 1
                if target_index < len(self.lines):
                    date_line = self.lines[target_index].strip()
                    print(f"TRAZA: Línea {target_index} (Valor): '{date_line}'")
                    # Patrón de fecha DD.MM.YYYY
                    date_match = re.search(date_pattern, date_line)
                    if date_match:
                        # Se normaliza a formato con barras /
                        self.fecha = date_match.group(1).replace('.', '/').strip() 
                        print(f"TRAZA: Fecha extraída: {self.fecha}")
                        return
        self.fecha = None
        print(f"TRAZA: Fecha final: {self.fecha}")

    def _extract_importe_and_base(self):
        # Los valores están a 5 líneas de distancia de sus respectivas cabeceras de columna.
        print("--- TRAZA: _extract_importe_and_base ---")
        
        # Diccionario para almacenar los índices de las anclas
        anchor_indices = {}
        for i, line in enumerate(self.lines):
            if "Importe total EUR" in line.strip(): 
                anchor_indices['total'] = i
            if "Valor neto EUR" in line.strip(): 
                anchor_indices['base'] = i
            if "Impte. IVA EUR" in line.strip(): 
                anchor_indices['iva_amount'] = i

        # 1. Extraer Importe Total (5 líneas después de 'Importe total EUR')
        if 'total' in anchor_indices:
            total_index = anchor_indices['total'] + 5 
            if total_index < len(self.lines):
                line_with_total = self.lines[total_index].strip()
                print(f"TRAZA: Línea {total_index} (Importe Total): '{line_with_total}'")
                self.importe = _extract_amount(line_with_total) 
                print(f"TRAZA: Importe Total extraído: {self.importe}")

        # 2. Extraer Base Imponible (5 líneas después de 'Valor neto EUR')
        if 'base' in anchor_indices:
            base_index = anchor_indices['base'] + 5 
            if base_index < len(self.lines):
                line_with_base = self.lines[base_index].strip()
                print(f"TRAZA: Línea {base_index} (Base Imponible): '{line_with_base}'")
                self.base_imponible = _extract_amount(line_with_base) 
                print(f"TRAZA: Base Imponible extraída: {self.base_imponible}")

        # 3. Extraer IVA (Importe) (5 líneas después de 'Impte. IVA EUR')
        if 'iva_amount' in anchor_indices:
            iva_index = anchor_indices['iva_amount'] + 5 
            if iva_index < len(self.lines):
                line_with_iva = self.lines[iva_index].strip()
                print(f"TRAZA: Línea {iva_index} (IVA Directo): '{line_with_iva}'")
                self.iva = _extract_amount(line_with_iva)
                print(f"TRAZA: IVA extraído (directo): {self.iva}")

        # Fallback de la clase base si aún no se encuentran valores.
        if self.importe is None or self.base_imponible is None or self.iva is None:
             super()._extract_importe_and_base()

        print(f"TRAZA: Importes finales: Total={self.importe}, Base={self.base_imponible}, IVA={self.iva}")