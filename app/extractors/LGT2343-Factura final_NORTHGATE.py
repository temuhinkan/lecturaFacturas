
# Extractor generado automáticamente para LGT2343-Factura final_NORTHGATE.py
from base_invoice_extractor import BaseInvoiceExtractor
from typing import Dict, Any, List

class Lgt2343Factura finalNorthgateExtractor(BaseInvoiceExtractor):
    # Sobrescribir estas variables si se conocen
    EMISOR_NAME = "NORTHGATE ESPAÑA RENTING FLEXIBLE S.A."
    EMISOR_CIF = "A28659423"
    
    # Puede sobrescribir BASE_EXTRACTION_MAPPING con un mapeo específico si es necesario
    
    def extract_data(self, lines: List[str]) -> Dict[str, Any]:
        # 1. Ejecutar la lógica de extracción genérica (hereda el mapeo base y limpieza)
        extracted_data = super().extract_data(lines)
        
        # 2. AGREGAR LÓGICA DE EXTRACCIÓN ESPECÍFICA AQUÍ:
        #
        # Ejemplo: Sobrescribir el número de factura si se encuentra un patrón mejor
        # extracted_data['numero_factura'] = self._find_number(lines, 'Nº. DE FACTURA:')
        
        # Ejemplo: Buscar un campo que la lógica base no encontró
        # for line in lines:
        #     if 'DATO_ESPECIFICO:' in line:
        #         extracted_data['campo_nuevo'] = line.split(':')[-1].strip()
        
        return extracted_data
        

# --- LÍNEAS DE REFERENCIA DEL DOCUMENTO --- 
# NORTHGATE ESPAÑA RENTING FLEXIBLE S.A.
#                                    NEW SATELITE, S.L.
#  Avd. de Bruselas,20                                           CALLE SIERRA DE ARACENA - NUM: 62
#  28108 Alcobendas
#  MADRID
#                                                  28691 VILLANEVA DE LA CAÑADA CIF/NIF: A28659423
#                                                B85629020
# 
# 
# 
# 
# 
#  FACTURA Nº        VO-2025005930
# 
#  FECHA               29/05/25
# 
# 
# CANTIDAD   CONCEPTO                                                   PRECIO UNITARIO            IMPORTE
# 
# 
#     1         Matrícula:              2343-LGT
#                                                                                                                                                                                                                                                                                                                                                                    EdN3
#              Modelo:             RENAULT KANGOO EXPRESS 1.5 DCI 55KW PRO                                                               41
# 
#               Bastidor:              VF1FW50J163465317                                                                  6.033,06                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             IMP-CAP
#             Kilómetros:           107.966
# 
#            Cargo por transferencia 2343-LGT                                                                    140,5
# 
# 
# 
#                                                  BASE IMPONIBLE                           6.173,56
# 
#                                                              IVA        21,00%                         1.296,45
# 
# 
#                                                    TOTAL FACTURA                            7.470,01
# -----------------------------------------

