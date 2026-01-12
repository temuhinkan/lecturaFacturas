import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Tuple, List, Optional, Any, Dict
import re
import fitz  # PyMuPDF
from PIL import Image, ImageTk, ImageDraw

# Importaciones de módulos propios
import database 
import logic
from config import EXTRACTORS_DIR

class ExtractorGeneratorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Editor de Reglas de Extracción (Optimizado)")
        self.root.geometry("1400x900")
        
        # Variables de estado
        self.current_pdf_path = None
        self.pdf_doc = None
        self.current_page = 0
        self.lines = []
        self.zoom = 1.0
        
        self.setup_ui()
        
    def setup_ui(self):
        """Estructura de la interfaz principal."""
        # Paneles principales (Izquierda: Reglas | Derecha: Visor)
        self.main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.main_paned.pack(fill=tk.BOTH, expand=True)
        
        self.left_panel = ttk.Frame(self.main_paned)
        self.right_panel = ttk.Frame(self.main_paned)
        
        self.main_paned.add(self.left_panel, weight=1)
        self.main_paned.add(self.right_panel, weight=2)
        
        self._setup_editor_panel()
        self._setup_viewer_panel()

    def _setup_editor_panel(self):
        """Panel de configuración de reglas."""
        padding = {'padx': 10, 'pady': 5}
        
        # Selección de Extractor y Campo
        header_frame = ttk.LabelFrame(self.left_panel, text="Configuración Base")
        header_frame.pack(fill=tk.X, **padding)
        
        

        ttk.Label(header_frame, text="Extractor:").grid(row=0, column=0, sticky=tk.W)
        self.combo_extractor = ttk.Combobox(header_frame, values=self._get_extractors_list())
        #self.combo_extractor.grid(row=0, column=1, fill=tk.X, expand=True)
        self.combo_extractor.grid(row=0, column=1, sticky="ew") # Cambiado fill por sticky
        
        ttk.Label(header_frame, text="Campo:").grid(row=1, column=0, sticky=tk.W)
        self.combo_field = ttk.Combobox(header_frame, values=self._get_fields_list())
        #self.combo_field.grid(row=1, column=1, fill=tk.X, expand=True)
        self.combo_field.grid(row=1, column=1, sticky="ew") # Cambiado fill por sticky
        
        header_frame.columnconfigure(1, weight=1)
        # Configuración de la Regla
        rule_frame = ttk.LabelFrame(self.left_panel, text="Parámetros de la Regla")
        rule_frame.pack(fill=tk.BOTH, expand=True, **padding)
        
        self.rule_type = tk.StringVar(value="VARIABLE")
        ttk.Radiobutton(rule_frame, text="Variable (Referencia)", variable=self.rule_type, value="VARIABLE").pack(anchor=tk.W)
        ttk.Radiobutton(rule_frame, text="Fija (Línea absoluta)", variable=self.rule_type, value="FIXED").pack(anchor=tk.W)
        ttk.Radiobutton(rule_frame, text="Valor Fijo", variable=self.rule_type, value="FIXED_VALUE").pack(anchor=tk.W)
        
        # Entradas dinámicas
        self.entries = {}
        for label, key in [("Texto Ref:", "ref_text"), ("Línea:", "line"), ("Offset:", "offset"), ("Segmento:", "segment"), ("Valor:", "value")]:
            f = ttk.Frame(rule_frame)
            f.pack(fill=tk.X, pady=2)
            ttk.Label(f, text=label, width=12).pack(side=tk.LEFT)
            ent = ttk.Entry(f)
            ent.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.entries[key] = ent

        # Botones de Acción
        btn_frame = ttk.Frame(self.left_panel)
        btn_frame.pack(fill=tk.X, **padding)
        
        ttk.Button(btn_frame, text="🧪 Probar Regla", command=self.on_test_rule).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="💾 Guardar Regla", command=self.on_save_rule).pack(side=tk.LEFT, padx=5)

    def _setup_viewer_panel(self):
        """Visor de PDF integrado."""
        ctrl_frame = ttk.Frame(self.right_panel)
        ctrl_frame.pack(fill=tk.X)
        
        ttk.Button(ctrl_frame, text="Abrir Factura", command=self.load_pdf).pack(side=tk.LEFT, padx=5)
        self.lbl_page = ttk.Label(ctrl_frame, text="Página: -")
        self.lbl_page.pack(side=tk.LEFT, padx=5)
        
        # Canvas con scroll para el PDF
        self.canvas = tk.Canvas(self.right_panel, bg="gray")
        self.canvas.pack(fill=tk.BOTH, expand=True)

    # --- Lógica de Negocio ---

    def load_pdf(self):
        path = filedialog.askopenfilename(filetypes=[("PDF/Images", "*.pdf *.png *.jpg")])
        if not path: return
        
        self.current_pdf_path = path
        self.lines = logic._get_pdf_lines(path) # Usamos la lógica optimizada
        
        if path.lower().endswith('.pdf'):
            self.pdf_doc = fitz.open(path)
            self.show_page(0)
        else:
            self._load_image(path)

    def show_page(self, page_num):
        if not self.pdf_doc: return
        self.current_page = page_num
        page = self.pdf_doc.load_page(page_num)
        pix = page.get_pixmap(matrix=fitz.Matrix(self.zoom, self.zoom))
        
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        self.tk_img = ImageTk.PhotoImage(img)
        
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_img)
        self.canvas.config(scrollregion=self.canvas.bbox(tk.ALL))
        self.lbl_page.config(text=f"Página: {page_num + 1} / {len(self.pdf_doc)}")

    def on_test_rule(self):
        """Prueba la regla actual contra el texto cargado del PDF."""
        if not self.lines:
            messagebox.showwarning("Aviso", "Cargue primero un documento para probar.")
            return
            
        rule = {
            'type': self.rule_type.get(),
            'ref_text': self.entries['ref_text'].get(),
            'line': int(self.entries['line'].get() or 0),
            'offset': int(self.entries['offset'].get() or 0),
            'segment': self.entries['segment'].get() or "1",
            'value': self.entries['value'].get()
        }
        
        # Usamos el motor de logic.py para garantizar consistencia
        result = logic.apply_extraction_rule(self.lines, rule)
        
        if result:
            messagebox.showinfo("Resultado", f"Valor extraído: '{result}'")
        else:
            messagebox.showerror("Fallo", "La regla no encontró ningún dato.")

    def on_save_rule(self):
        """Guarda la regla en la BBDD."""
        ext_name = self.combo_extractor.get()
        field_name = self.combo_field.get()
        
        if not ext_name or not field_name:
            messagebox.showerror("Error", "Debe seleccionar un extractor y un campo.")
            return
            
        rule_data = {
            'type': self.rule_type.get(),
            'ref_text': self.entries['ref_text'].get(),
            'offset': int(self.entries['offset'].get() or 0),
            'segment': self.entries['segment'].get() or "1",
            'value': self.entries['value'].get(),
            'line': int(self.entries['line'].get() or 0),
            'attempt_order': 1
        }
        
        success = database.save_extractor_configuration(ext_name, field_name, rule_data)
        if success:
            messagebox.showinfo("Éxito", "Regla guardada correctamente en la base de datos.")

    def _get_extractors_list(self) -> List[str]:
        mapping = database.get_extraction_mapping()
        return list(mapping.keys())

    def _get_fields_list(self) -> List[str]:
        with database.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT field_name FROM extraction_fields")
            return [row['field_name'] for row in cursor.fetchall()]

if __name__ == "__main__":
    root = tk.Tk()
    # Inicializar BBDD si no existe
    database.setup_database()
    app = ExtractorGeneratorGUI(root)
    root.mainloop()