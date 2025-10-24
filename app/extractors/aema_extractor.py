import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _calculate_base_from_total, VAT_RATE, _calculate_total_from_base

class AemaExtractor(BaseInvoiceExtractor):
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        self.vat_rate = 0.21 # Tasa fija del 21%
        
        # Inicialización de atributos
        self.importe = None
        self.base_imponible = None
        self.iva = None

    # --- CAMPOS SIMPLES ---
    def _extract_emisor(self):
        self.emisor = "NEUMÁTICOS AEMA, S.A."

    def _extract_cif(self):
        # El CIF de NEUMÁTICOS AEMA S.A. es A-28.625.036
        self.cif = "A28625036" # Limpio y sin puntos

    def _extract_fecha(self):
        # La fecha (31/03/2025) está en la Línea 05 o adyacente a "Fecha:" (Línea 06).
        date_pattern = r'(\d{2}[-/]\d{2}[-/]\d{4})'
        for i, line in enumerate(self.lines):
            if re.search(r"Fecha:", line, re.IGNORECASE) or i == 5:
                target_lines = [self.lines[i], self.lines[i-1]] if i > 0 else [self.lines[i]]
                for t_line in target_lines:
                    fecha_match = re.search(date_pattern, t_line)
                    if fecha_match:
                        self.fecha = fecha_match.group(1).strip().replace('-', '/')
                        return
        
    # --- CAMPO COMPLEJO: NÚMERO DE FACTURA ---
    def _extract_numero_factura(self):
        # Número de factura: FV-CR-02-2025-000226 (Línea 07)
        invoice_pattern = r'([A-Z]{2}-CR-\d{2}-\d{4}-\d{6})' 
        for line in self.lines:
            match = re.search(invoice_pattern, line, re.IGNORECASE)
            if match:
                self.numero_factura = match.group(1).strip()
                return
        super()._extract_numero_factura()

    # --- CAMPOS COMPLEJOS: IMPORTES (Extracción de Base y Total prioritarias) ---
    def _extract_importe_and_base(self):
        
        # 1. Extraer Base Imponible (SUBTOTAL: Línea 228 -> Valor: Línea 229)
        subtotal_index = -1
        print("--- DEBUG: Búsqueda de SUBTOTAL (Base Imponible) ---")
        for i, line in enumerate(self.lines):
            print(f"DEBUG: Revisando línea {i:03d}: '{line.strip()}'")
            if re.search(r"\bSUBTOTAL\b", line.strip(), re.IGNORECASE):
                subtotal_index = i
                print(f"DEBUG: Coincidencia de 'SUBTOTAL' encontrada en la línea {i:03d}.")
                break # Encontrado el SUBTOTAL del resumen

        if subtotal_index != -1 and subtotal_index + 1 < len(self.lines):
            line_with_base = self.lines[subtotal_index + 1]
            print(f"DEBUG: Línea seleccionada para el valor base ({subtotal_index + 1:03d}): '{line_with_base.strip()}'")
            
            base_amount_str = _extract_amount(line_with_base)
            
            if base_amount_str:
                self.base_imponible = base_amount_str
                print(f"DEBUG: Base Imponible extraída: {self.base_imponible}")
            else:
                print("DEBUG: _extract_amount NO pudo extraer el valor base de la línea siguiente.")
        else:
            print("DEBUG: Etiqueta SUBTOTAL no encontrada o no hay línea siguiente.")


        # 2. Extraer Importe Total (TOTAL: Línea 234 -> Valor: Línea 235)
        # Se itera desde el final para asegurar el último TOTAL del fichero.
        total_index = -1
        print("--- DEBUG: Búsqueda de TOTAL (Importe Total) ---")
        for i in range(len(self.lines) - 1, -1, -1):
            line = self.lines[i]
            # Buscamos la palabra TOTAL en la zona de pie (i > 200)
            if re.search(r"\bTOTAL\b", line.strip(), re.IGNORECASE) and i > 200: 
                total_index = i
                print(f"DEBUG: Coincidencia de 'TOTAL' encontrada en la línea {i:03d} (iterando al revés).")
                break 

        if total_index != -1 and total_index + 1 < len(self.lines):
            line_with_total = self.lines[total_index + 1]
            print(f"DEBUG: Línea seleccionada para el valor total ({total_index + 1:03d}): '{line_with_total.strip()}'")

            total_amount_str = _extract_amount(line_with_total)
            if total_amount_str:
                self.importe = total_amount_str
                print(f"DEBUG: Importe Total extraído: {self.importe}")
            else:
                print("DEBUG: _extract_amount NO pudo extraer el valor total de la línea siguiente.")
        else:
            print("DEBUG: Etiqueta TOTAL no encontrada en el pie del documento.")


        # 3. Cálculo de respaldo y verificación de IVA
        
        # A. Si se encontró la Base, calcular Total e IVA
        if self.base_imponible:
            print(f"DEBUG: Calculando Total e IVA a partir de la Base Imponible: {self.base_imponible}")
            # Limpiar el separador de miles (punto) antes de pasar a la utilidad
            base_for_calc = self.base_imponible.strip().replace('€', '').replace('.', '')
            
            # Recalcular Total e IVA
            calculated_total, calculated_iva = _calculate_total_from_base(base_for_calc, self.vat_rate)
            
            if calculated_iva:
                 self.iva = calculated_iva
            
            # Si no se encontró el importe en el paso 2, usar el calculado
            if not self.importe and calculated_total:
                 self.importe = calculated_total
        
        # B. Si no se encontró la Base (SUBTOTAL) pero sí el Total, calcular la Base
        elif self.importe:
            print(f"DEBUG: Calculando Base Imponible e IVA a partir del Importe Total: {self.importe}")
            # Limpiar el separador de miles (punto) antes de pasar a la utilidad
            total_for_calc = self.importe.strip().replace('€', '').replace('.', '')
            
            self.base_imponible = _calculate_base_from_total(total_for_calc, self.vat_rate)
            
            # Recalcular IVA
            if self.base_imponible:
                 _, self.iva = _calculate_total_from_base(self.base_imponible, self.vat_rate)


        # 4. Fallback: Intentar extraer IVA explícitamente (Línea 231) si todavía falta
        if self.iva is None:
            print("DEBUG: Intentando extraer IVA directamente.")
            iva_pattern = r'IVA\s*\(\s*21,00%\s*\)'
            for i, line in enumerate(self.lines):
                if re.search(iva_pattern, line, re.IGNORECASE):
                    if i + 1 < len(self.lines):
                        iva_amount_str = _extract_amount(self.lines[i + 1])
                        if iva_amount_str:
                            self.iva = iva_amount_str
                            print(f"DEBUG: IVA extraído directamente: {self.iva}")
                            break

        # Fallback de la clase base si todo falla
        if self.importe is None or self.base_imponible is None:
             print("DEBUG: Fallback a la superclase.")
             super()._extract_importe_and_base()
        
        print(f"--- DEBUG: Resultados Finales ---")
        print(f"DEBUG: Base Imponible (self.base_imponible): {self.base_imponible}")
        print(f"DEBUG: Importe Total (self.importe): {self.importe}")
        print(f"DEBUG: IVA (self.iva): {self.iva}")
        print("---------------------------------")


    # --- OTROS CAMPOS ---
    def _extract_modelo(self):
        found_models = []
        for line in self.lines:
            modelo_match = re.search(r'Marca/Modelo:\s*(.+?)(?:Ktms\s*:\s*|$)', line, re.IGNORECASE)
            if modelo_match:
                model_name = modelo_match.group(1).strip()
                if model_name: 
                    found_models.append(model_name)
        
        if found_models:
            self.modelo = ", ".join(list(set(found_models)))
        else:
            self.modelo = None

    def _extract_matricula(self):
        found_matriculas = []
        for line in self.lines:
            matricula_match = re.search(r'Matrícula:\s*([A-Z0-9]+)', line, re.IGNORECASE)
            if matricula_match:
                found_matriculas.append(matricula_match.group(1).strip())
        
        if found_matriculas:
            self.matricula = ", ".join(list(set(found_matriculas)))
        else:
            self.matricula = None