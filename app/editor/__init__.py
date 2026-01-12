import fitz
from PIL import Image, ImageTk
import io
import pytesseract  # <--- IMPORTANTE: Necesario para leer imágenes
from .view import EditorView
from .controller import EditorController

# Configuración básica de ruta Tesseract si estás en Windows (ajusta si es necesario)
# from config import TESSERACT_CMD_PATH
# if TESSERACT_CMD_PATH:
#     pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD_PATH

class PDFEngine:
    def __init__(self):
        self.pdf_doc = None
        self.current_page = 0
        self.zoom = 1.0
        self.rotation = 0
        self.page_width = 0
        self.page_height = 0

    def load_document(self, path):
        self.pdf_doc = fitz.open(path)
        self.current_page = 0

    def get_page_image(self):
        if not self.pdf_doc: return None
        page = self.pdf_doc.load_page(self.current_page)
        mat = fitz.Matrix(self.zoom, self.zoom).prerotate(self.rotation)
        pix = page.get_pixmap(matrix=mat)
        self.page_width = pix.width
        self.page_height = pix.height
        img_data = pix.tobytes("ppm")
        return ImageTk.PhotoImage(Image.open(io.BytesIO(img_data)))

    def get_text_from_coords(self, x1, y1, x2, y2):
        """
        Intenta extraer texto digital. Si falla, hace OCR del área seleccionada.
        """
        if not self.pdf_doc: return ""
        try:
            page = self.pdf_doc.load_page(self.current_page)
            
            # 1. Calcular la matriz inversa para ir de Pantalla -> Coordenadas PDF Original
            mat = fitz.Matrix(self.zoom, self.zoom).prerotate(self.rotation)
            inv_mat = ~mat
            
            p1 = fitz.Point(x1, y1) * inv_mat
            p2 = fitz.Point(x2, y2) * inv_mat
            rect = fitz.Rect(p1, p2)
            
            # 2. INTENTO A: Extracción directa (funciona en PDFs digitales)
            texto = page.get_text("text", clip=rect).strip()
            
            # 3. INTENTO B: Si no hay texto, usamos OCR (Tesseract) sobre la imagen
            if not texto:
                # Obtenemos la imagen de esa pequeña área.
                # Usamos un zoom de 2x (matrix=2) para mejorar la precisión del OCR
                pix = page.get_pixmap(clip=rect, matrix=fitz.Matrix(2, 2))
                
                # Convertimos pixmap a imagen PIL
                img_data = pix.tobytes("png")
                pil_image = Image.open(io.BytesIO(img_data))
                
                # Ejecutamos Tesseract
                # --psm 6 asume un bloque de texto uniforme
                texto = pytesseract.image_to_string(pil_image, lang='spa', config='--psm 6')
                
            return texto.strip()

        except Exception as e:
            print(f"❌ Error extrayendo texto/OCR: {e}")
            return ""

    def find_nearest_anchor(self, target_coords):
        if not self.pdf_doc: return None
        page = self.pdf_doc[self.current_page]
        words = page.get_text("words") 
        
        # Si no hay palabras (es una imagen), el ancla no funcionará con 'words'.
        # En una versión futura podrías hacer OCR de toda la página, pero es lento.
        if not words:
            return None

        center_x = (target_coords[0] + target_coords[2]) / 2
        center_y = (target_coords[1] + target_coords[3]) / 2
        
        best_anchor = None
        min_dist = float('inf')
        
        for w in words:
            if any(char.isdigit() for char in w[4]) and len(w[4]) < 10:
                continue
            
            anchor_x = (w[0] + w[2]) / 2
            anchor_y = (w[1] + w[3]) / 2
            dist = ((center_x - anchor_x)**2 + (center_y - anchor_y)**2)**0.5
            
            if dist < min_dist:
                min_dist = dist
                best_anchor = {
                    'texto': w[4],
                    'x': w[0],
                    'y': w[1]
                }
                
        return best_anchor

    def zoom_in(self): self.zoom += 0.2
    def zoom_out(self): self.zoom = max(0.2, self.zoom - 0.2)
    def rotate_cw(self): self.rotation = (self.rotation + 90) % 360

    

def abrir_editor(parent, path, all_files=None, current_idx=0):
    view = EditorView(parent)
    engine = PDFEngine()
    controller = EditorController(view, engine, all_files, current_idx)
    controller.load_file(path)