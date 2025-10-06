import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_nif_cif, _extract_from_line, _calculate_base_from_total, VAT_RATE

class AemaExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)

    def _extract_emisor(self):
        for line in self.lines:
            if re.search(r"NEUMÁTICOS AEMA,\s*S\.A\.", line, re.IGNORECASE):
                self.emisor = "NEUMÁTICOS AEMA, S.A."
                break

    def _extract_numero_factura(self):
        invoice_regex = r"([A-Z0-9-]+)\s*Número:FACTURA DE VENTA"
        for line in self.lines:
            if re.search(r"Número:FACTURA DE VENTA", line, re.IGNORECASE):
                match = re.search(invoice_regex, line, re.IGNORECASE)
                if match:
                    self.numero_factura = match.group(1)
                    break

    def _extract_fecha(self):
        for line in self.lines:
            if re.search(r"Fecha:", line, re.IGNORECASE):
                self.fecha = _extract_from_line(line, r'(\d{2}[-/]\d{2}[-/]\d{4})')
                if self.fecha:
                    break
    
    def _extract_cif(self):
        for line in self.lines:
            extracted_cif = _extract_nif_cif(line)
            if extracted_cif and extracted_cif != "B85629020":
                self.cif = extracted_cif
                break

    def _extract_importe_and_base(self):
        for i, line in enumerate(self.lines):
            if re.search(r"Retención", line, re.IGNORECASE) and i + 1 < len(self.lines):
                self.importe = _extract_amount(self.lines[i+1]).replace('.', '')
                if self.importe:
                    self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)
                    break
    def _extract_modelo(self):
        found_models = []
        for line in self.lines:
            # Modificación aquí: la regex para capturar el modelo
            # Captura cualquier carácter (excepto salto de línea) que no esté seguido de "Ktms"
            # r'Modelo:\s*(.+?)(?:\s*Ktms\b|$)'
            # Explicación:
            # (.+?)       -> Captura uno o más caracteres (no avaro)
            # (?:\s*Ktms\b|$) -> Es un grupo no capturador (?:...) que busca:
            #                    - \s*Ktms\b: cero o más espacios, la palabra "Ktms" y un límite de palabra
            #                    - |$: o el fin de la línea ($)
            # Esto asegura que la captura se detiene antes de "Ktms" o al final de la línea.

            modelo_match = re.search(r'Modelo:\s*(.+?)(?:\s*Ktms\b|$)', line, re.IGNORECASE)
            if modelo_match:
                # Group 1 contiene el modelo sin "Ktms"
                model_name = modelo_match.group(1).strip()
                if model_name: # Asegurarse de no añadir cadenas vacías
                    found_models.append(model_name)
        
        if found_models:
            self.modelo = ", ".join(found_models)
        else:
            self.modelo = None

    def _extract_matricula(self):
        # Lista para almacenar todas las matrículas encontradas
        found_matriculas = []
        for line in self.lines:
            matricula_match = re.search(r'Matrícula:\s*([A-Z0-9]+)', line, re.IGNORECASE)
            if matricula_match:
                found_matriculas.append(matricula_match.group(1).strip())
        
        # Unir todas las matrículas encontradas con un separador (por ejemplo, ", ")
        if found_matriculas:
            self.matricula = ", ".join(found_matriculas)
        else:
            self.matricula = None # O podrías dejarlo como una cadena vacía si prefieres