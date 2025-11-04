import os
from typing import Dict, Any

# --- Configuración General ---

# Nombre del archivo de base de datos SQLite
DB_NAME: str = 'facturas.db'

# Ruta al ejecutable de Tesseract OCR (requerido para OCR en Windows)
# ¡AJUSTA ESTA RUTA SI ES NECESARIO!
TESSERACT_CMD_PATH: str = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Tasa de IVA por defecto (usada para cálculos si no se extrae)
# Usar el formato decimal (0.21 para 21%)
DEFAULT_VAT_RATE: float = 0.21
DEFAULT_VAT_RATE_STR: str = "21%"

# Directorio donde se guardan los extractores dinámicos
EXTRACTORS_DIR: str = 'extractors'


# --- Mapeo de Clases de Extracción (Movido de main_extractor_gui.py) ---
# {nombre_clave_archivo: ruta_completa_a_clase}
EXTRACTION_MAPPING: Dict[str, str] = {
    "autodoc": "extractors.autodoc_extractor.AutodocExtractor",
    "stellantis": "extractors.stellantis_extractor.StellantisExtractor",
    "brildor": "extractors.brildor_extractor.BrildorExtractor",
    "hermanas": "extractors.hermanas_extractor.HermanasExtractor",
    "kiauto": "extractors.kiauto_extractor.KiautoExtractor",
    "sumauto": "extractors.sumauto_extractor.SumautoExtractor",
    "amor": "extractors.hermanas_extractor.HermanasExtractor", # Alias
    "pinchete": "extractors.pinchete_extractor.PincheteExtractor",
    "refialias": "extractors.refialias_extractor.RefialiasExtractor",
    "leroy": "extractors.leroy_extractor.LeroyExtractor",
    "poyo": "extractors.poyo_extractor.PoyoExtractor",
    "caravana": "extractors.lacaravana_extractor.LacaravanaExtractor",
    "malaga": "extractors.malaga_extractor.MalagaExtractor",
    "beroil": "extractors.beroil_extractor.BeroilExtractor",
    "berolkemi": "extractors.berolkemi_extractor.BerolkemiExtractor",
    "autocasher": "extractors.autocasher_extractor.AutocasherExtractor",
    "cesvimap": "extractors.cesvimap_extractor.CesvimapExtractor",
    "fiel": "extractors.fiel_extractor.FielExtractor",
    "pradilla": "extractors.pradilla_extractor.PradillaExtractor",
    "boxes": "extractors.boxes_extractor.BoxesExtractor",
    "hergar": "extractors.hergar_extractor.HergarExtractor",
    "musas": "extractors.musas_extractor.MusasExtractor",
    "muas": "extractors.musas_extractor.MusasExtractor", # Alias
    "aema": "extractors.aema_extractor.AemaExtractor",
    "autodescuento": "extractors.autodescuento_extractor.AutodescuentoExtractor",
    "northgate": "extractors.northgate_extractor.NorthgateExtractor",
    "recoautos": "extractors.recoautos_extractor.RecoautosExtractor",
    "colomer": "extractors.colomer_extractor.ColomerExtractor",
    "wurth": "extractors.wurth_extractor.WurthExtractor",
    "candelar": "extractors.cantelar_extractor.CantelarExtractor",
    "cantelar": "extractors.cantelar_extractor.CantelarExtractor",
    "volkswagen": "extractors.volkswagen_extractor.VolkswagenExtractor",
    "oscaro": "extractors.oscaro_extractor.OscaroExtractor",
    "adevinta": "extractors.adevinta_extractor.AdevintaExtractor",
    "amazon": "extractors.amazon_extractor.AmazonExtractor",
    "coslauto": "extractors.coslauto_extractor.CoslautoExtractor",
    "eduardo": "extractors.desguaceseduardo_extractor.DesguaceseduardoExtractor",
    "autolux":"extractors.autolux_extractor.AutoluxExtractor",
    "valdizarbe": "extractors.valdizarbe_extractor.ValdizarbeExtractor",
    "minuta": "extractors.minuta_extractor.MinutaExtractor",
    "emitida": "extractors.emitida_extractor.EmitidaExtractor",
    "autolunas": "extractors.autolunas_extractor.AutolunasExtractor",
    "guarnecidos": "extractors.guarnecidos_extractor.GuarnecidosExtractor",
    "codigo": "extractors.codigo_extractor.CodigoExtractor"
    
}

# Datos de error estándar
ERROR_DATA: tuple = (
    "ERROR_EXTRACCION", None, None, None, None, None, None, None, None, None, None, None, "Error de lectura o formato."
)