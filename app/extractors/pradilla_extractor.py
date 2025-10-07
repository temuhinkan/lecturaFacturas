import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from typing import Tuple, Any

class PradillaExtractor(BaseInvoiceExtractor):
    """
    Extractor diseñado para facturas de Gestoría Pradilla, S.L.
    Se ha reforzado la extracción de totales para evitar errores.
    """
    EMISOR_CIF = "B80481369" 

    def __init__(self, lines, pdf_path):
        super().__init__(lines, pdf_path)
        self.tipo = "PRADILLA"
        self.cliente = "NEW SATELITE SL"
        self.emisor = "GESTORIA PRADILLA, S.L."

    def _clean_number(self, value: Any) -> float | None:
        """Limpia la cadena y la convierte a float de forma segura."""
        if value is None:
            return None
        try:
            # Limpia separadores de miles, reemplaza coma decimal por punto
            clean_str = str(value).replace('.', '').replace(',', '.').strip().replace('€', '')
            # Manejar signo si existe (aunque es raro en facturas)
            sign = -1 if clean_str.startswith('-') else 1
            clean_str = clean_str.replace('-', '')
            return float(clean_str) * sign
        except ValueError:
            return None

    def extract_all(self) -> Tuple[Any, ...]:
        # Inicializar todos los campos a None antes de la extracción
        self.fecha = None
        self.numero_factura = None
        self.cif_cliente = None
        self.matricula = None
        base_imponible = None
        iva = None
        importe_total = None
        tasas = None # Tasas son los Suplidos

        text = "\n".join(self.lines)
        num_pattern = r'([0-9\.,]+)' # Patrón para capturar números
        
        # --- 1. Extracción de Metadatos ---
        
        # N°FACTURA (25019773)
        match_num = re.search(r'N°FACTURA\s*\n\s*([A-Z0-9.]+)', text)
        if match_num:
            self.numero_factura = match_num.group(1).strip()
            
        # FECHA (15/07/2025)
        match_fecha = re.search(r'FECHA\s*\n\s*(\d{2}/\d{2}/\d{4})', text)
        if match_fecha:
            self.fecha = match_fecha.group(1).strip()
            
        # CIF Cliente (B85629020)
        match_cif_cliente = re.search(r'C.I.F:\s*\n\s*([A-Z0-9]+)', text)
        if match_cif_cliente:
            self.cif_cliente = match_cif_cliente.group(1).strip()
            
        # Matrícula (0668FPM)
        match_matricula = re.search(r'Matrícula\s*Referencia\s*\n\s*([A-Z0-9]+)', text)
        if match_matricula:
            self.matricula = match_matricula.group(1).strip()
            
        # --- 2. Extracción de Totales (MÁS ROBUSTA) ---
        
        # Importe Total (TOTAL A PAGAR: 12,91)
        match_total = re.search(r'TOTAL\s+A\s+PAGAR\s*\n\s*' + num_pattern, text)
        if match_total:
             importe_total = self._clean_number(match_total.group(1))

        # Tasas/Suplidos (Valor de SUPLIDOS, 8,67)
        match_suplidos_total = re.search(r'SUPLIDOS\s*\n\s*' + num_pattern, text)
        if match_suplidos_total:
             tasas = self._clean_number(match_suplidos_total.group(1))

        # Base Imponible y IVA 
        # Busca la línea "BASE I.V.A. 21,00 %IVA IMP.FACTURA" y captura los dos números que siguen,
        # uno por línea.
        match_base_iva = re.search(
            r'BASE\s+I\.V\.A\.\s*21,00\s*%IVA\s+IMP\.FACTURA\s*\n\s*' + num_pattern + r'\s*\n\s*' + num_pattern, 
            text
        )
        if match_base_iva:
            base_imponible = self._clean_number(match_base_iva.group(1))
            iva = self._clean_number(match_base_iva.group(2))
        
        # --- 3. Ensamblaje de los 12 campos de datos. ---
        return (
            self.tipo,
            self.fecha,
            self.numero_factura,
            self.emisor, 
            self.cliente, 
            self.cif_cliente,
            None, # Modelo 
            self.matricula,
            importe_total, 
            base_imponible, 
            iva, 
            tasas # Tasas (Suplidos)
        )