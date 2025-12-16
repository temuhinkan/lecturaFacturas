# document_utils.py

from typing import List
import os

# Importaciones de dependencias para el visor de documentos
try:
    import fitz # PyMuPDF
    VIEWER_AVAILABLE = True
except ImportError:
    fitz = None
    VIEWER_AVAILABLE = False


def get_document_lines(file_path: str) -> List[str]:
    """
    Lee el texto de un PDF/Imagen (o usa placeholder) para usarlo como referencia en el editor.
    """
    lines = []
    
    # 1. Intento con PyMuPDF (fitz) para PDFs
    if fitz and file_path and os.path.exists(file_path) and file_path.lower().endswith(('.pdf', '.xps', '.epub', '.cbz')):
        try:
            doc = fitz.open(file_path)
            for page in doc:
                # Usar sort=True para una mejor reconstrucción de líneas
                text = page.get_text("text", sort=True) 
                lines.extend([l for l in text.splitlines() if l.strip()])
            doc.close()
            if lines:
                return lines
        except Exception:
            pass

    # 2. Fallback (Placeholder)
    if not lines:
        return [
            "Línea 00: IMP-CAP 41 EdN3",
            "Línea 01: 29/05/2025",
            "Línea 02: B85629020",
            "Línea 03: CALLE SIERRA DE ARACENA - NUM: 62",
            "Línea 04: NEW SATELITE, S.L.",
            "Línea 05: 28691 VILLANEVA DE LA CAÑADA",
            "Línea 06: FACTURA Nº 2025/123",
            "Línea 07: FECHA 29/05/2025",
            "Línea 08: BASE: 100,00 - IVA: 21,00 - TOTAL: 121,00"
        ]
    
    return lines