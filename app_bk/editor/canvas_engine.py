import fitz  # PyMuPDF
from PIL import Image, ImageTk
import math

class CanvasEngine:
    def __init__(self):
        self.pdf_doc = None
        self.current_page = 0
        self.zoom_level = 1.0
        self.rotation = 0  # 0, 90, 180, 270
        
        # Referencias para Tkinter
        self.tk_image = None 
        self.page_width = 0
        self.page_height = 0

    def load_document(self, path):
        """Carga el documento y reinicia valores."""
        self.pdf_doc = fitz.open(path)
        self.current_page = 0
        self.zoom_level = 1.0
        self.rotation = 0

    def get_page_image(self, page_num=None):
        """Renderiza la página actual con zoom y rotación."""
        if page_num is not None:
            self.current_page = page_num
            
        page = self.pdf_doc.load_page(self.current_page)
        
        # Aplicamos Zoom y Rotación
        # 72 DPI es el estándar, multiplicamos por zoom para calidad
        mat = fitz.Matrix(self.zoom_level, self.zoom_level).prerotate(self.rotation)
        pix = page.get_pixmap(matrix=mat)
        
        # Convertir a formato compatible con Tkinter
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        self.page_width, self.page_height = pix.width, pix.height
        self.tk_image = ImageTk.PhotoImage(img)
        return self.tk_image

    def get_text_from_coords(self, x1, y1, x2, y2):
        """
        Traduce coordenadas del Canvas (pantalla) a coordenadas reales 
        del PDF para extraer el texto.
        """
        page = self.pdf_doc.load_page(self.current_page)
        
        # Invertimos la matriz de renderizado para obtener las coordenadas originales
        mat = fitz.Matrix(self.zoom_level, self.zoom_level).prerotate(self.rotation)
        inv_mat = ~mat 
        
        # Rectángulo en la pantalla -> Rectángulo en el PDF
        pdf_rect = fitz.Rect(x1, y1, x2, y2) * inv_mat
        
        # Extraer texto de esa área específica
        return page.get_text("text", clip=pdf_rect).strip()

    def zoom_in(self):
        self.zoom_level = min(self.zoom_level + 0.2, 5.0)
        
    def zoom_out(self):
        self.zoom_level = max(self.zoom_level - 0.2, 0.2)

    def rotate_cw(self):
        self.rotation = (self.rotation + 90) % 360