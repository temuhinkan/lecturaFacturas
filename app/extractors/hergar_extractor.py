import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_from_line, _calculate_base_from_total,_calculate_total_from_base, VAT_RATE

class HergarExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        self.cif = "A-78009172" # Fixed CIF for this issuer

    def _extract_emisor(self):
        self.emisor = "GESTIÓN DE RESIDUOS S.A."

    def _extract_numero_factura(self):
        # Usamos el regex más robusto: buscar el número al inicio de la siguiente línea, ignorando espacios
        invoice_regex = r"^\s*(\d+)" 
        print(f"DEBUG: Usando regex para número: {invoice_regex}")
        
        for i, line in enumerate(self.lines):
            # Limpiamos la línea de espacios para la búsqueda del marcador
            stripped_line = line.strip() 

            # 1. Buscamos el marcador "Nº.", "N.º", "N°", etc.
            # Usamos re.match() y un patrón más flexible 'N[º°\.]+': 
            # - No se necesita el ancla '$' al final.
            # - Coincide con la secuencia 'N' seguida de uno o más símbolos de número (º, °, o .)
            if re.match(r"N[º°\.]+", stripped_line, re.IGNORECASE):
                print(f"DEBUG: Marcador encontrado en línea {i}: '{stripped_line}'")
                
                # 2. Si lo encontramos, comprobamos que hay una línea siguiente
                if i + 1 < len(self.lines):
                    full_next_line = self.lines[i+1]
                    stripped_next_line = full_next_line.strip()
                    print(f"DEBUG: Línea siguiente ({i+1}): '{stripped_next_line}'")
                    
                    # 3. Intentamos extraer el número (solo dígitos) de la siguiente línea
                    match = re.search(invoice_regex, stripped_next_line)
                    
                    if match:
                        extracted_value = match.group(1).strip()
                        print(f"DEBUG: Valor del grupo 1 (Nº Factura): '{extracted_value}'")
                        
                        self.numero_factura = extracted_value
                        break
                    else:
                        print(f"DEBUG: No se encontró coincidencia con el regex '{invoice_regex}' en '{stripped_next_line}'")

    def _extract_fecha(self):
        for line in self.lines:
            if re.search(r"FECHA:", line, re.IGNORECASE):
                self.fecha = _extract_from_line(line, r'(\d{2}[-/]\d{2}[-/]\d{4})')
                if self.fecha:
                    break

    def _extract_importe_and_base(self):
        for i, line in enumerate(self.lines):
            # Coincide con Line 31: "TOTAL FACTURA "
            if re.search(r"TOTAL FACTURA\s*", line, re.IGNORECASE) and i + 1 < len(self.lines):
                # Extrae de Line 32: "    13,51   " -> Extrae 13,51
                self.base_imponible = _extract_amount(self.lines[i+1])
                print(f"base_imponible: '{self.base_imponible}'")
                print(f"imponible: '{self.importe}'")
                if self.base_imponible:
                    # _calculate_total_from_base devuelve una tupla, por ejemplo: ('16,35', '2,84')
                    total_amount, vat_amount = _calculate_total_from_base(self.base_imponible, self.vat_rate)

                    # Asignamos solo el primer elemento (el total) a self.importe
                    self.importe = total_amount
                    
                    # Opcional: Asignar el IVA a una variable si es necesario
                    # self.iva = vat_amount 
                    
                    print(f"imponible aa: '{self.importe}'")
                    break
