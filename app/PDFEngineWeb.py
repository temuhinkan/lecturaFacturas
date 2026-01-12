import fitz  # PyMuPDF
import base64
import io
from PIL import Image
import pytesseract

# Intenta importar la configuración, si falla usa valores por defecto
try:
    from config import TESSERACT_CMD_PATH
    if TESSERACT_CMD_PATH:
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD_PATH
except ImportError:
    pass

class PDFEngineWeb:
    def __init__(self):
        self.doc = None
        self.current_page = 0
        self.zoom = 1.0
        self.rotation = 0
        
        # Guardamos dimensiones actuales para cálculos de coordenadas
        self.current_width = 0
        self.current_height = 0

    def load_document(self, source):
        """
        Carga el documento. 
        'source' puede ser una ruta de archivo (str) o bytes (si viene de una subida web).
        """
        try:
            if isinstance(source, bytes):
                self.doc = fitz.open(stream=source, filetype="pdf")
            else:
                self.doc = fitz.open(source)
            self.current_page = 0
            return True
        except Exception as e:
            print(f"Error cargando documento: {e}")
            return False

    def get_page_image_b64(self):
        """
        Renderiza la página actual y devuelve:
        1. String Base64 de la imagen (para Flet).
        2. Ancho de la imagen generada.
        3. Alto de la imagen generada.
        """
        if not self.doc: return None, 0, 0

        page = self.doc.load_page(self.current_page)
        
        # Aplicar Zoom y Rotación
        mat = fitz.Matrix(self.zoom, self.zoom).prerotate(self.rotation)
        pix = page.get_pixmap(matrix=mat)
        
        # Guardar dimensiones actuales para los cálculos de click
        self.current_width = pix.width
        self.current_height = pix.height
        
        # Convertir a PNG bytes y luego a Base64 string
        img_bytes = pix.tobytes("png")
        base64_str = base64.b64encode(img_bytes).decode("utf-8")
        
        return base64_str, pix.width, pix.height

    def get_text_from_web_coords(self, x1, y1, x2, y2):
        """
        Traduce las coordenadas del navegador (donde el usuario dibujó el rectángulo)
        a las coordenadas reales del PDF y extrae el texto/OCR.
        """
        if not self.doc: return ""

        try:
            page = self.doc.load_page(self.current_page)
            
            # 1. Crear la matriz que usamos para generar la imagen (Zoom/Rotación)
            mat = fitz.Matrix(self.zoom, self.zoom).prerotate(self.rotation)
            
            # 2. Invertirla para ir de Pantalla -> PDF Original
            inv_mat = ~mat
            
            # 3. Transformar los puntos del rectángulo
            p1 = fitz.Point(x1, y1) * inv_mat
            p2 = fitz.Point(x2, y2) * inv_mat
            rect_pdf = fitz.Rect(p1, p2)
            
            # 4. INTENTO A: Texto Digital
            texto = page.get_text("text", clip=rect_pdf).strip()
            
            # 5. INTENTO B: OCR (Si no hay texto digital)
            if not texto:
                # Extraer imagen de esa zona con alta resolución para OCR
                pix = page.get_pixmap(clip=rect_pdf, matrix=fitz.Matrix(2, 2))
                img_data = pix.tobytes("png")
                pil_image = Image.open(io.BytesIO(img_data))
                
                # Ejecutar Tesseract
                texto = pytesseract.image_to_string(pil_image, lang='spa', config='--psm 6')
            
            return texto.strip()

        except Exception as e:
            print(f"Error extrayendo texto web: {e}")
            return ""

    def zoom_in(self):
        self.zoom += 0.25

    def zoom_out(self):
        self.zoom = max(0.25, self.zoom - 0.25)

    def rotate_cw(self):
        self.rotation = (self.rotation + 90) % 360
        
    def next_page(self):
        if self.doc and self.current_page < len(self.doc) - 1:
            self.current_page += 1

    def prev_page(self):
        if self.doc and self.current_page > 0:
            self.current_page -= 1