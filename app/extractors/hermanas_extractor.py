import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_nif_cif, _extract_from_lines_with_keyword, _calculate_base_from_total, VAT_RATE, _calculate_total_from_base

class HermanasExtractor(BaseInvoiceExtractor):
    # CRÍTICO: Definición obligatoria para la identificación correcta del emisor.
    EMISOR_CIF = "R4900012H" 
    
    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)
        # Inicialización de todos los campos para evitar el error de resumen 0,00 €
        self.emisor = None
        self.numero_factura = None
        self.fecha = None
        self.cif = None
        self.base_imponible = None
        self.iva = None
        self.importe = None
        self.vat_rate = VAT_RATE

    def _extract_emisor(self):
        self.emisor = "Hermanas del Amor de Dios Casa General"

    def _extract_numero_factura(self):
        # Busca el patrón 'FG-XX/XXXX' (L09 o L22 en las facturas)
        pattern = r'(FG-?\d{2}/\d{4})'
        for line in self.lines:
            match = re.search(pattern, line)
            if match:
                self.numero_factura = match.group(1).strip().replace('-/', '/') 
                return

    def _extract_fecha(self):
        # La fecha se busca en la línea siguiente a 'FECHA:' (L10 o L23)
        self.fecha = _extract_from_lines_with_keyword(self.lines, r'FECHA:', r'(\d{2}/\d{2}/\d{4})', look_ahead=1)
        
    def _extract_importe_and_base(self):
        # --- ESTRATEGIA 1: Búsqueda de 'TOTAL A PAGAR' (La que ya funciona) ---
        
        # 1. Buscar el índice de la etiqueta TOTAL A PAGAR
        idx_total_label = -1
        for i, line in enumerate(self.lines):
            if re.search(r'TOTAL\s+A\s+PAGAR', line):
                idx_total_label = i
                break

        # Inicialización de strings de importe
        importe_total_str = None
        base_imponible_str = None
        iva_str = None
        
        # 2. Si se encuentra la etiqueta, buscar el VALOR TOTAL
        if idx_total_label != -1:
            idx_total_amount = -1
            last_valid_amount_index = -1
            
            # Recorrer todas las líneas después de la etiqueta para encontrar el valor más bajo (que es el total).
            for i in range(idx_total_label + 1, len(self.lines)):
                # Buscamos valores que parezcan dinero
                match = re.search(r'(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2}))', self.lines[i])
                
                if match:
                    # Solo consideramos valores > 0.00
                    try:
                        amount_float = float(match.group(1).replace(',', '.'))
                        if amount_float > 0.0:
                            last_valid_amount_index = i
                            importe_total_str = match.group(1).strip() 
                    except ValueError:
                        pass # Ignorar si la conversión a float falla
            
            
            idx_total_amount = last_valid_amount_index
            
            # 3. Extraer Base e IVA usando la posición relativa al Total
            if idx_total_amount != -1 and idx_total_amount >= 2:
                iva_str = self.lines[idx_total_amount - 1].strip()
                base_imponible_str = self.lines[idx_total_amount - 2].strip()


        # 4. Conversión y Asignación (Común para ambas estrategias)
        importe_total_float = None
        if importe_total_str:
            try:
                # 4.1 FIX CRÍTICO para el Total
                amount_result = _extract_amount(importe_total_str)
                
                if isinstance(amount_result, str):
                    # Forzar conversión: '847,00' -> 847.00
                    importe_total_float = float(amount_result.replace(',', '.'))
                elif isinstance(amount_result, (int, float)):
                    importe_total_float = amount_result
                
            except Exception as e:
                importe_total_float = None
        
        
        # ------------------------------------------------------------------------------------------------------
        # --- ESTRATEGIA 2: FALLBACK: Búsqueda de 'IMPORTE' si la Estrategia 1 falló (importe_total_float es 0 o None) ---
        # ------------------------------------------------------------------------------------------------------
        if importe_total_float is None or importe_total_float <= 0.0:
            
            # Buscar el índice de la primera aparición de la etiqueta IMPORTE
            idx_importe_label = -1
            for i, line in enumerate(self.lines):
                if re.search(r'\bIMPORTE\b', line, re.IGNORECASE):
                    idx_importe_label = i
                    break
            
            if idx_importe_label != -1:
                base_imponible_str_fallback = None
                importe_total_str_fallback = None

                # Base (ej: 700,00) está dos líneas después
                if idx_importe_label + 2 < len(self.lines):
                    base_line = self.lines[idx_importe_label + 2].strip()
                    match_base = re.search(r'(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2}))', base_line)
                    if match_base:
                        base_imponible_str_fallback = match_base.group(1).strip()
                
                # Total (ej: 847,00) está dos líneas antes
                if idx_importe_label - 2 >= 0:
                    total_line = self.lines[idx_importe_label - 2].strip()
                    match_total = re.search(r'(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2}))', total_line)
                    if match_total:
                        importe_total_str_fallback = match_total.group(1).strip()
                
                
                # Si encontramos la Base, la usamos como prioritaria para calcular Total e IVA
                if base_imponible_str_fallback:
                    base_imponible_str = base_imponible_str_fallback
                    
                    try:
                        base_float = float(base_imponible_str.replace(',', '.'))
                        vat_float = base_float * self.vat_rate
                        total_float = base_float + vat_float
                        
                        importe_total_str = f"{total_float:.2f}".replace('.', ',')
                        iva_str = f"{vat_float:.2f}".replace('.', ',')
                        
                        importe_total_float = total_float
                        
                    except Exception as e:
                        pass
                
                # Si no encontramos la Base, pero encontramos el Total, intentamos calcular Base e IVA
                elif importe_total_str_fallback:
                    importe_total_str = importe_total_str_fallback
                    try:
                        total_float = float(importe_total_str.replace(',', '.'))
                        importe_total_float = total_float
                        
                        base_calc_str = _calculate_base_from_total(importe_total_str, self.vat_rate)
                        if base_calc_str:
                            base_imponible_str = base_calc_str
                            base_float = float(base_calc_str.replace(',', '.'))
                            vat_float = total_float - base_float
                            iva_str = f"{vat_float:.2f}".replace('.', ',')
                            
                    except Exception as e:
                        pass
                        
        # 5. Asignación final si el importe total es válido (Se usa el resultado de la Estrategia 1 o 2)
        if importe_total_float is not None and importe_total_float > 0.0:
            
            # Asignar Importe Total (con coma)
            self.importe = f"{importe_total_float:.2f}".replace('.', ',')

            # 5.1 Asignación de Base y IVA (con bloques try/fix)
            for amount_str, target_attr in [(base_imponible_str, 'base_imponible'), (iva_str, 'iva')]:
                if amount_str: 
                    try:
                        result = _extract_amount(amount_str)
                        if isinstance(result, str):
                            float_val = float(result.replace(',', '.'))
                        elif isinstance(result, (int, float)):
                            float_val = result
                        else:
                            continue
                            
                        if target_attr == 'base_imponible':
                            self.base_imponible = f"{float_val:.2f}".replace('.', ',')
                        elif target_attr == 'iva':
                            self.iva = f"{float_val:.2f}".replace('.', ',')
                    except Exception:
                        pass
            
            return 

    def _extract_cif(self):
        # 🚨 FIX SOLICITADO: Asignar el CIF del EMISOR (R4900012H), en lugar del CIF del cliente (B85629020).
        self.cif = self.EMISOR_CIF