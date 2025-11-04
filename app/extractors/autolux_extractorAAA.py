# 🚨 MAPPING SUGERIDO PARA main_extractor_gui.py
# Copie la siguiente línea y péguela en el diccionario EXTRACTION_MAPPING:
#     "autolux": "extractors.autolux_extractor.AutoluxExtractor",

import re
from extractors.base_invoice_extractor import BaseInvoiceExtractor

class AutoluxExtractor(BaseInvoiceExtractor):
    # 1. Parámetros de la Factura (Se rellenan con el campo CIF y TIPO del GUI)
    EMISOR_CIF = "B02819530"
    TIPO_FACTURA = "COMPRA"

    # 2. Palabras Clave para Búsqueda (Señaladores)
    # Dejamos estos vacíos si hay mapeo por línea, o con patrones genéricos.
    CLAVES_NUM_FACTURA = [r"Factura N.?\s*:\s*(\w+)", r"Nº\s*FACTURA:\s*(\w+)"]
    CLAVES_FECHA = [r"Fecha\s*:\s*(\d{2}/\d{2}/\d{4})", r"FECHA\s+(\d{2}/\d{2}/\d{4})"]
    CLAVES_BASE = [r"BASE IMPONIBLE\s*([\d\.,]+)", r"TOTAL BASE\s*([\d\.,]+)"]
    CLAVES_TOTAL = [r"TOTAL FACTURA\s*([\d\.,]+)", r"Total\s*a\s*Pagar\s*([\d\.,]+)"]

    def __init__(self, lines, pdf_path=None):
        super().__init__(lines, pdf_path)

    # --- MÉTODOS DE EXTRACCIÓN PERSONALIZADOS ---
def extract_numero_factura(self):
        # Extracción basada en el mapeo de línea 1 (¡Línea Fija!)
        try:
         return self.clean_value(self.lines[1])
        except (IndexError, ValueError):
            pass
        return super().extract_numero_factura()


def extract_emisor(self):
        # Extracción basada en el mapeo de línea 23 (¡Línea Fija!)
        try:
         return self.clean_value(self.lines[23])
        except (IndexError, ValueError):
            pass
        return super().extract_emisor()


def extract_base_imponible(self):
        # Extracción robusta por posición relativa al texto: "Base" (Línea 16)
        try:
            # Línea de cabecera mapeada: L16
            header_line = self.lines[16]
            # Línea de valor esperada: L17
            value_line = self.lines[17]
            
            # Tokenizar las líneas
            header_tokens = [t.strip().lower() for t in header_line.split() if t.strip()]
            value_tokens = [t.strip() for t in value_line.split() if t.strip()]
            
            # 1. Buscar el índice del token que CONTIENE la palabra clave
            keyword = 'Base'.lower()
            token_index = -1
            
            # Intentar encontrar la palabra clave mapeada en la cabecera
            try:
                token_index = next(i for i, token in enumerate(header_tokens) if keyword in token)
            except StopIteration:
                # Fallback: Usar la posición del token más probable si el mapeo falla
                token_index = 1 
             
            # 2. Extraer el valor de la línea siguiente usando el índice encontrado.
            if field_name == 'Importe' and token_index == -1:
                # Si no encuentra 'TOTAL FACTURA', forzar el último elemento de la línea de valor
                token_index = -1

            if 0 <= token_index < len(value_tokens):
                value_str = value_tokens[token_index]
                return self.parse_float(value_str)
            
        except (IndexError, ValueError):
            pass
        return super().extract_base_imponible()


def extract_importe_total(self):
        # Extracción robusta por posición relativa al texto: "TOTAL FACTURA" (Línea 16)
        try:
            # Línea de cabecera mapeada: L16
            header_line = self.lines[16]
            # Línea de valor esperada: L17
            value_line = self.lines[17]
            
            # Tokenizar las líneas
            header_tokens = [t.strip().lower() for t in header_line.split() if t.strip()]
            value_tokens = [t.strip() for t in value_line.split() if t.strip()]
            
            # 1. Buscar el índice del token que CONTIENE la palabra clave
            keyword = 'TOTAL FACTURA'.lower()
            token_index = -1
            
            # Intentar encontrar la palabra clave mapeada en la cabecera
            try:
                token_index = next(i for i, token in enumerate(header_tokens) if keyword in token)
            except StopIteration:
                # Fallback: Usar la posición del token más probable si el mapeo falla
                token_index = -1 
             
            # 2. Extraer el valor de la línea siguiente usando el índice encontrado.
            if field_name == 'Importe' and token_index == -1:
                # Si no encuentra 'TOTAL FACTURA', forzar el último elemento de la línea de valor
                token_index = -1

            if 0 <= token_index < len(value_tokens):
                value_str = value_tokens[token_index]
                return self.parse_float(value_str)
            
        except (IndexError, ValueError):
            pass
        return super().extract_importe_total()


def extract_iva(self):
        # Extracción robusta por posición relativa al texto: "IVA" (Línea 16)
        try:
            # Línea de cabecera mapeada: L16
            header_line = self.lines[16]
            # Línea de valor esperada: L17
            value_line = self.lines[17]
            
            # Tokenizar las líneas
            header_tokens = [t.strip().lower() for t in header_line.split() if t.strip()]
            value_tokens = [t.strip() for t in value_line.split() if t.strip()]
            
            # 1. Buscar el índice del token que CONTIENE la palabra clave
            keyword = 'IVA'.lower()
            token_index = -1
            
            # Intentar encontrar la palabra clave mapeada en la cabecera
            try:
                token_index = next(i for i, token in enumerate(header_tokens) if keyword in token)
            except StopIteration:
                # Fallback: Usar la posición del token más probable si el mapeo falla
                token_index = 2 
             
            # 2. Extraer el valor de la línea siguiente usando el índice encontrado.
            if field_name == 'Importe' and token_index == -1:
                # Si no encuentra 'TOTAL FACTURA', forzar el último elemento de la línea de valor
                token_index = -1

            if 0 <= token_index < len(value_tokens):
                value_str = value_tokens[token_index]
                return self.parse_float(value_str)
            
        except (IndexError, ValueError):
            pass
        return super().extract_iva()


def extract_cliente(self) -> str:
        # Cliente mapeado como valor fijo
        return "NEW SATELITE, S.L."
    # -------------------------------------------
    
    # Si no se define el método personalizado, se llama a la implementación base
    # (ej. si extract_numero_factura no se mapea, se usa la lógica del padre)

