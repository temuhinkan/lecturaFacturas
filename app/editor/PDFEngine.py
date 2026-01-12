import fitz
from PIL import Image, ImageTk
import io

class PDFEngine:
    def __init__(self):
        self.pdf_doc = None
        self.current_page = 0
        self.zoom = 1.0
        self.rotation = 0

    def load_document(self, path):
        self.pdf_doc = fitz.open(path)
        self.current_page = 0

    def get_page_image(self):
        page = self.pdf_doc.load_page(self.current_page)
        mat = fitz.Matrix(self.zoom, self.zoom).prerotate(self.rotation)
        pix = page.get_pixmap(matrix=mat)
        img_data = pix.tobytes("ppm")
        return ImageTk.PhotoImage(Image.open(io.BytesIO(img_data)))

    def zoom_in(self): self.zoom += 0.2
    def zoom_out(self): self.zoom = max(0.2, self.zoom - 0.2)
    def rotate_cw(self): self.rotation = (self.rotation + 90) % 360