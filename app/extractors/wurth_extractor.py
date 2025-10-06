import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_nif_cif, _calculate_base_from_total, VAT_RATE, _extract_from_line

class WurthExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        # El emisor se fijará explícitamente en _extract_emisor para mantener la consistencia
        # y asegurar que no sea sobrescrito por un valor por defecto antes de la extracción.

    def _extract_emisor(self):
        # Fijar directamente el emisor. Para este tipo de factura, es constante.
        self.emisor = "WÜRTH ESPAÑA, S.A."

    def _extract_numero_factura(self):
        # El número de factura está en la línea 16: "Nº factura 4733937515" 
        for line in self.lines: # Iterar sobre todas las líneas en lugar de un índice fijo
            match = re.search(r"Nº factura\s*(\d+)", line)
            if match:
                self.numero_factura = match.group(1).strip()
                break
        if self.numero_factura is None:
            super()._extract_numero_factura()

    def _extract_fecha(self):
        # La fecha está en la línea 16: "Fecha 22.04.2025" 
        for line in self.lines: # Iterar sobre todas las líneas
            match = re.search(r"Fecha\s*(\d{2}\.\d{2}\.\d{4})", line)
            if match:
                # Formatear la fecha de DD.MM.YYYY a DD/MM/YYYY
                self.fecha = match.group(1).replace('.', '/')
                break
        if self.fecha is None:
            super()._extract_fecha()

    def _extract_cif(self):
        # El CIF del emisor está en la línea 16: "NIF: ESB85629020" 
        # También aparece en la línea 25: "NIF: A08472276"  (este es el correcto para Würth)
        cif_pattern = r"NIF:\s*([A-Z]?\d{8}[A-Z]?)" # Regex más general para NIF/CIF
        
        for line in self.lines:
            match = re.search(cif_pattern, line, re.IGNORECASE)
            if match:
                extracted_cif = match.group(1).strip()
                # Asegurarse de que capturamos el CIF del emisor (A08472276), no el del cliente (B85629020)
                if extracted_cif == "A08472276":
                    self.cif = extracted_cif
                    return # CIF del emisor encontrado, salimos.
        
        # Si no se encuentra el CIF específico, se deja que la superclase lo intente
        if self.cif is None:
            super()._extract_cif()

    def _extract_modelo(self):
        # El modelo o descripción del artículo relevante podría estar en la línea 20: "DISCO-ABRAS-ZEBRA-FINE-P3000-D150MM" 
        # Asumiendo que es una línea completa con la descripción del modelo.
        self.modelo =""
        

    def _extract_matricula(self):
        # No se observa una matrícula explícita en el documento.
        # Se mantiene el comportamiento de la clase base.
        self.matricula=""

    def _extract_importe_and_base(self):
        self.importe = None
        self.base_imponible = None

        # La tabla con los totales está en la fuente 23.
        # Basado en la línea: "6,95 ,46,95 ,21,00%,9,86 ,56,81"
        # Portes EUR, Valor neto EUR (Base Imponible), IVA, Impte. IVA EUR, Importe total EUR
        # Los valores relevantes están en la misma línea debajo de los encabezados.
        
        for i, line in enumerate(self.lines):
            # Buscar la línea que contiene "Portes EUR" para identificar la tabla de totales.
            # O directamente la línea que contiene el "Importe total EUR" si es única.
            if re.search(r"Importe total EUR", line): # Encabezado de la columna 
                # La siguiente línea (i+1) debería contener los valores numéricos.
                if i + 1 < len(self.lines):
                    data_line = self.lines[i+1] # Línea de datos 
                    
                    # Regex para capturar números con formato decimal (coma o punto)
                    # Ex: "6,95", "46,95", "21,00", "9,86", "56,81" 
                    numeric_strings = re.findall(r'(\d+[,.]\d{2})', data_line)
                    
                    if len(numeric_strings) >= 5: # Asegurarse de que tenemos suficientes valores 
                        # Convertir los strings a float usando _extract_amount
                        numeric_values_float = [_extract_amount(s) for s in numeric_strings]
                        
                        # "Valor neto EUR" es la Base Imponible (segundo valor capturado, índice 1) 
                        self.base_imponible = numeric_values_float[1] 
                        
                        # "Importe total EUR" es el Importe total (quinto valor capturado, índice 4) 
                        self.importe = numeric_values_float[4]
                        
                        break # Salir del bucle una vez encontrados los valores

        # Si el importe o la base aún son None después de la extracción, se usa el fallback genérico.
        if self.importe is None or self.base_imponible is None:
            super()._extract_importe_and_base()