import os
import csv
import sys
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Tuple, List, Optional, Any, Dict
import io 
import sqlite3 
import traceback 

# Importaciones de dependencias para el visor de documentos (Asegurar que PyMuPDF y Pillow están importados si es posible)
try:
    import fitz # PyMuPDF
    from PIL import Image, ImageTk, ImageDraw # Añadido ImageDraw para crear iconos
    VIEWER_AVAILABLE = True
except ImportError:
    fitz = None
    Image = None
    ImageTk = None
    ImageDraw = None
    VIEWER_AVAILABLE = False
    print("⚠️ ADVERTENCIA: Visor no disponible. Instale 'PyMuPDF' y 'Pillow' (pip install PyMuPDF Pillow).")

# --- Importaciones de Módulos (Asegurar existencia) ---
import database 
import logic 
import utils 

# --- Importación de Constantes ---
try:
    # Se espera que 'config.py' contenga las constantes
    from config import DEFAULT_VAT_RATE, DEFAULT_VAT_RATE_STR
except ImportError:
    # Definiciones por defecto si config.py no existe
    DEFAULT_VAT_RATE = 0.21
    DEFAULT_VAT_RATE_STR = f"{DEFAULT_VAT_RATE * 100:.0f}%"

from database import fetch_all_invoices, delete_invoice_data, insert_invoice_data, update_invoice_field, delete_entire_database_schema, is_invoice_processed
from logic import extraer_datos 
from utils import calculate_total_and_vat 

# --- Configuración de OCR (Tesseract) ---
try:
    import pytesseract
    if sys.platform == "win32":
        # ¡AJUSTA ESTA RUTA SI ES NECESARIO!
        pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe' 
except ImportError:
    pytesseract = None
except AttributeError:
    pass

class InvoiceApp:
    def __init__(self, master):
        self.master = master
        master.title("Extractor Generator App")
        
        database.setup_database() 

        self.tree: Optional[ttk.Treeview] = None
        self.log_text: Optional[ScrolledText] = None
        
        # -----------------------------------------------
        # --- Atributos de Visor y Zoom ---
        # -----------------------------------------------
        self.doc = None                      
        self.base_image = None              
        self.viewer_canvas: Optional[tk.Canvas] = None
        self.image_tk = None                 
        
        self.zoom_level: float = 1.0        
        self.current_page: int = 0          
        self.total_pages: int = 0
        
        self.zoom_label_var = tk.StringVar(value=f"100%") 
        self.page_label_var = tk.StringVar(value=f"Página 0/0") 
        # -----------------------------------------------

        # Atributos de Control (existentes)
        self.files_to_process: List[str] = []
        self.process_button: Optional[ttk.Button] = None 
        self.debug_var = tk.BooleanVar(value=False)
        self.reprocess_var = tk.BooleanVar(value=False)
        self.log_var = tk.BooleanVar(value=True)
        self.current_file_path = None

        self.setup_gui()
        
        # 1. Carga inicial del documento pasado por argumento (si existe)
        if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
            self.current_file_path = sys.argv[1]
            self.open_document(self.current_file_path)

        self.load_data_to_tree() 
        self.master.after(50, self._initial_sash_position)

    # ------------------------------------------------------------------
    # --- AJUSTES DE GUI Y CONFIGURACIÓN ---
    # ------------------------------------------------------------------
            
    def setup_gui(self):
        self.main_frame = ttk.Frame(self.master, padding="10")
        self.main_frame.pack(fill='both', expand=True)

        self.pane_window = ttk.PanedWindow(self.main_frame, orient=tk.HORIZONTAL)
        self.pane_window.pack(fill='both', expand=True, pady=10)
        
        # ------------------------------------------------------------------
        # Panel Izquierdo (Visor de Documentos)
        # ------------------------------------------------------------------
        viewer_panel = ttk.LabelFrame(self.pane_window, text="Visor de Documentos", padding="5")
        self.pane_window.add(viewer_panel, weight=2) 
        
        # Frame para el Canvas y Scrollbars
        canvas_frame = ttk.Frame(viewer_panel)
        canvas_frame.pack(fill='both', expand=True)

        # Scrollbar Vertical
        v_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Scrollbar Horizontal
        h_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Canvas para la imagen del documento
        self.viewer_canvas = tk.Canvas(
            canvas_frame, 
            bg='white', 
            borderwidth=2, 
            relief="groove",
            yscrollcommand=v_scrollbar.set,  # Link Canvas to Scrollbar
            xscrollcommand=h_scrollbar.set   # Link Canvas to Scrollbar
        )
        self.viewer_canvas.pack(side=tk.LEFT, fill='both', expand=True)
        
        # Link Scrollbars to Canvas view
        v_scrollbar.config(command=self.viewer_canvas.yview)
        h_scrollbar.config(command=self.viewer_canvas.xview)
        
        # Bindeo para manejar el redimensionamiento del canvas
        self.viewer_canvas.bind('<Configure>', self.on_canvas_resize)
        
        # Controles del visor (Paginación y Zoom)
        viewer_controls = ttk.Frame(viewer_panel)
        viewer_controls.pack(fill='x')
        
        # Controles de Paginación
        self.prev_button = ttk.Button(viewer_controls, text="<< Anterior", command=lambda: self.change_page(-1), state=tk.DISABLED)
        self.prev_button.pack(side='left', padx=5, pady=5)
        self.page_label = ttk.Label(viewer_controls, textvariable=self.page_label_var)
        self.page_label.pack(side='left', padx=10)
        self.next_button = ttk.Button(viewer_controls, text="Siguiente >>", command=lambda: self.change_page(1), state=tk.DISABLED)
        self.next_button.pack(side='left', padx=5, pady=5)
        
        # Controles de Zoom
        zoom_frame = ttk.Frame(viewer_controls)
        zoom_frame.pack(side='right', padx=5, pady=5)
        
        self.zoom_out_button = ttk.Button(zoom_frame, text="Zoom -", command=lambda: self.change_zoom(-0.2), state=tk.DISABLED)
        self.zoom_out_button.pack(side='left', padx=5)
        
        self.zoom_label = ttk.Label(zoom_frame, textvariable=self.zoom_label_var)
        self.zoom_label.pack(side='left', padx=10)
        
        self.zoom_in_button = ttk.Button(zoom_frame, text="Zoom +", command=lambda: self.change_zoom(0.2), state=tk.DISABLED)
        self.zoom_in_button.pack(side='left', padx=5)
        
        # ------------------------------------------------------------------
        # Panel Derecho (Tabla y Log)
        # ------------------------------------------------------------------
        table_panel = ttk.Frame(self.pane_window, padding="5")
        self.pane_window.add(table_panel, weight=3) 

        # --- Etiqueta de Tasa de IVA por defecto (NUEVA ADICIÓN) ---
        ttk.Label(table_panel, text=f"Tasa IVA por Defecto: {DEFAULT_VAT_RATE_STR}", 
                  font=("TkDefaultFont", 10, "bold"), foreground="blue").pack(side='top', fill='x', pady=(0, 5))
        # ----------------------------------------------------------

        # Elementos del Panel Derecho (Tabla)
        tree_frame = ttk.Frame(table_panel)
        tree_frame.pack(side='top', fill='both', expand=True)
        
        # Columnas
        # ESTA ES LA DEFINICIÓN DE COLUMNAS, INCLUYE "IVA"
        columns = ("path", "file_name", "tipo", "fecha", "numero_factura", "emisor", "cif_emisor", "cliente", "cif", "modelo", "matricula", "base", "iva", "importe", "is_validated", "tasas")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show='headings')
        
        # Encabezados
        for col in columns:
            # ESTE ES EL ENCABEZADO QUE MUESTRA "IMPORTE IVA"
            if col == 'iva':
                self.tree.heading(col, text="Importe IVA", anchor="e") 
            else:
                self.tree.heading(col, text=col.replace('_', ' ').title(), anchor="w" if col not in ['base', 'importe', 'tasas'] else "e")
        
        # Configuración de ancho de columnas
        self.tree.column("path", width=0, stretch=tk.NO) 
        self.tree.column("file_name", width=150, anchor="w")
        self.tree.column("base", width=80, anchor="e")
        # ESTE ES EL ANCHO DE LA COLUMNA "IVA"
        self.tree.column("iva", width=80, anchor="e") 
        self.tree.column("importe", width=80, anchor="e") 
        
        # Scrollbars para la tabla
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb_tree = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb_tree.set)
        vsb.pack(side='right', fill='y')
        hsb_tree.pack(side='bottom', fill='x')
        self.tree.pack(side='top', fill='both', expand=True)

        self.tree.bind('<<TreeviewSelect>>', self.on_item_select)
        self.tree.bind('<Double-1>', self.on_double_click)

        # Log
        log_frame = ttk.LabelFrame(table_panel, text="Log de Extracción", padding="5")
        log_frame.pack(side='bottom', fill='x', pady=5, ipady=5)
        self.log_text = ScrolledText(log_frame, wrap=tk.WORD, height=8, width=80)
        self.log_text.pack(fill='both', expand=True)
        self.log_text.insert(tk.END, f"Listo. Tasa de IVA por defecto: {DEFAULT_VAT_RATE_STR}\n")

    def _initial_sash_position(self):
        try:
            self.master.update_idletasks() 
            window_width = self.master.winfo_width()
            initial_pos = int(window_width * 0.4)
            self.pane_window.sashpos(0, initial_pos)
        except tk.TclError:
            pass
            
    # ------------------------------------------------------------------
    # --- Lógica del Visor de Documentos (Zoom y Paginación) ---
    # ------------------------------------------------------------------
    
    def on_canvas_resize(self, event):
        """Maneja el evento de redimensionamiento del canvas."""
        if self.base_image and self.viewer_canvas:
            # Re-mostrar la imagen aplicando el zoom y el ajuste al nuevo tamaño del canvas
            self.resize_and_display_image(self.base_image)

    def on_item_select(self, event):
        """Maneja la selección de una fila para cargar el documento en el visor (si es necesario)."""
        try:
            selected_item = self.tree.focus()
            if selected_item:
                file_path = self.tree.item(selected_item, 'values')[0]
                if file_path and file_path != self.current_file_path:
                    self.current_file_path = file_path
                    self.current_page = 0
                    self.zoom_level = 1.0 # Reiniciar el zoom
                    self.zoom_label_var.set("100%")
                    self.open_document(file_path)
                
                # Cargar log data
                row = database.fetch_invoice_data(file_path)
                if row:
                    self.update_log_display(row.get('log_data', 'No hay datos de log.'), clear=True)

        except Exception as e:
            self.update_log_display(f"Error al seleccionar archivo: {e}", clear=True)
            self.close_document()

    def open_document(self, file_path: str):
        """Abre el documento (PDF o imagen) en el visor."""
        if not VIEWER_AVAILABLE:
            self.viewer_canvas.delete("all")
            self.page_label_var.set("Visor no disponible.")
            self.update_log_display("ADVERTENCIA: Visor no disponible. Instale 'PyMuPDF' y 'Pillow'.")
            return
            
        self.close_document() # Cerrar el documento anterior
        self.current_file_path = file_path
        
        try:
            if file_path.lower().endswith(('.pdf', '.jpg', '.jpeg', '.png')):
                if file_path.lower().endswith('.pdf'):
                    self.doc = fitz.open(file_path)
                    self.total_pages = self.doc.page_count
                else:
                    self.total_pages = 1
                
                self.show_page(self.current_page)
                
                # Habilitar botones de zoom al cargar
                self.zoom_in_button.config(state=tk.NORMAL)
                self.zoom_out_button.config(state=tk.NORMAL)
                
            else:
                raise ValueError("Formato de archivo no soportado para visualización.")

        except Exception as e:
            self.update_log_display(f"Error al cargar documento '{os.path.basename(file_path)}': {e}")
            self.close_document()
            
    def show_page(self, page_num: int):
        """Muestra una página específica del documento cargado."""
        if not VIEWER_AVAILABLE or not self.current_file_path or not self.viewer_canvas: return

        image = None
        if self.current_file_path.lower().endswith('.pdf'):
            if self.doc and 0 <= page_num < self.total_pages:
                self.current_page = page_num
                
                # Renderizar a alta resolución (Matrix(2, 2) = 200% de la resolución base)
                page = self.doc.load_page(page_num)
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2)) 
                
                # Crear la imagen PIL desde el mapa de bits
                image = Image.open(io.BytesIO(pix.tobytes("ppm")))
        
        elif self.current_file_path.lower().endswith(('.jpg', '.jpeg', '.png')):
            if page_num == 0:
                self.current_page = 0
                image = Image.open(self.current_file_path)
        
        if image:
            self.base_image = image 
            self.resize_and_display_image(self.base_image)
        
        # Actualizar etiqueta y estado de botones
        self.page_label_var.set(f"Página {self.current_page + 1}/{self.total_pages}")
        self.prev_button.config(state=tk.NORMAL if self.current_page > 0 else tk.DISABLED)
        self.next_button.config(state=tk.NORMAL if self.current_page < self.total_pages - 1 else tk.DISABLED)

    def change_zoom(self, delta: float):
        """Ajusta el nivel de zoom y redibuja la imagen."""
        if not self.base_image: return

        new_zoom = self.zoom_level + delta
        # Limitar el zoom a un rango razonable (ej. 0.5x a 4.0x)
        if 0.5 <= new_zoom <= 4.0:
            self.zoom_level = new_zoom
            self.zoom_label_var.set(f"{int(self.zoom_level * 100)}%")
            self.resize_and_display_image(self.base_image)
            
    def resize_and_display_image(self, image: Image.Image):
        """Ajusta el tamaño de la imagen al canvas, aplica el zoom y la muestra.
        Fija la región de scroll y la imagen en (0, 0).
        """
        if not image or not self.viewer_canvas: return
        
        canvas_width = self.viewer_canvas.winfo_width()
        canvas_height = self.viewer_canvas.winfo_height()
        
        if canvas_width <= 1 or canvas_height <= 1:
            return

        img_width, img_height = image.size
        
        # 1. Calcular el factor de escala inicial para ajustarse al canvas (Fit-to-View)
        scale_w = (canvas_width) / img_width 
        scale_h = (canvas_height) / img_height
        
        fit_scale = min(scale_w, scale_h)
        
        # Evitar el escalado inicial si la imagen es más pequeña que el canvas
        if fit_scale > 1.0:
            fit_scale = 1.0
            
        # 2. Aplicar el zoom actual
        final_scale = fit_scale * self.zoom_level
        
        # 3. Aplicar el redimensionamiento
        new_width = int(img_width * final_scale)
        new_height = int(img_height * final_scale)
        
        try:
            resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        except AttributeError:
            resized_image = image.resize((new_width, new_height), Image.LANCZOS)
            
        self.image_tk = ImageTk.PhotoImage(resized_image)
        
        self.viewer_canvas.delete("all")
        
        # 4. Establecer la región de scroll (dimensiones de la imagen redimensionada)
        self.viewer_canvas.config(scrollregion=(0, 0, new_width, new_height))
        
        # 5. Colocar la imagen en la esquina superior izquierda (0, 0)
        self.viewer_canvas.create_image(0, 0, image=self.image_tk, anchor='nw')
        self.viewer_canvas.image = self.image_tk # Mantener referencia

    def close_document(self):
        """Cierra el documento actual y limpia el visor."""
        if self.doc:
            self.doc.close()
            self.doc = None
        self.current_file_path = None
        self.current_page = 0
        self.total_pages = 0
        self.base_image = None
        self.zoom_level = 1.0
        self.zoom_label_var.set("100%")
        if self.viewer_canvas:
            self.viewer_canvas.delete("all")
            # Restablecer la región de scroll
            self.viewer_canvas.config(scrollregion=(0, 0, 0, 0)) 
            
        self.page_label_var.set("Página 0/0")
        
        # Deshabilitar controles
        for btn in [self.prev_button, self.next_button, self.zoom_in_button, self.zoom_out_button]:
            if btn: btn.config(state=tk.DISABLED)

    def change_page(self, delta: int):
        """Cambia la página actual del documento."""
        new_page = self.current_page + delta
        if 0 <= new_page < self.total_pages:
            # Restablecer el zoom al cambiar de página 
            self.zoom_level = 1.0
            self.zoom_label_var.set("100%")
            self.show_page(new_page)

    def update_log_display(self, message: str, clear: bool = False):
        """Actualiza el área de log de la GUI."""
        if not self.log_text: return
        self.log_text.config(state='normal')
        if clear:
            self.log_text.delete('1.0', tk.END)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')
        self.master.update_idletasks() # Forzar la actualización de la GUI

    # ------------------------------------------------------------------
    # --- MÉTODOS DE BBDD Y EDICIÓN (EXISTENTES) ---
    # ------------------------------------------------------------------

    def load_data_to_tree(self):
        """Carga los datos de la BBDD al Treeview."""
        for i in self.tree.get_children():
            self.tree.delete(i)

        try:
            invoices = fetch_all_invoices() 
            for inv in invoices:
                # Los valores numéricos vienen como float o None, se formatean aquí.
                values = (
                    inv.get('path'), inv.get('file_name'), inv.get('tipo'), inv.get('fecha'),
                    inv.get('numero_factura'), inv.get('emisor'), inv.get('cif_emisor'), inv.get('cliente'), inv.get('cif'),
                    inv.get('modelo'), inv.get('matricula'),
                    # Formateo a 2 decimales y uso de coma decimal
                    f"{inv.get('base', 0.0):.2f}".replace('.', ','),
                    # ESTA LÍNEA INSERTA EL VALOR DE IVA EN LA POSICIÓN CORRECTA
                    f"{inv.get('iva', 0.0):.2f}".replace('.', ','),
                    f"{inv.get('importe', 0.0):.2f}".replace('.', ','),
                    "✅" if inv.get('is_validated') == 1 else "❌",
                    f"{inv.get('tasas', 0.0):.2f}".replace('.', ','),
                )
                tag = 'validated' if inv.get('is_validated') == 1 else 'unvalidated'
                self.tree.insert('', tk.END, values=values, tags=(tag,))

        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error de BBDD", f"Fallo al cargar datos de la base de datos: {e}")


    def on_double_click(self, event):
        """Maneja el doble click para activar la edición de celda."""
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell": return

        column_id = self.tree.identify_column(event.x)
        column_index = int(column_id.replace('#', '')) - 1

        TREE_COLUMNS = ("path", "file_name", "tipo", "fecha", "numero_factura", "emisor", "cif_emisor" "cliente", "cif", "modelo", "matricula", "base", "iva", "importe", "is_validated", "tasas")
        if column_index < 0 or column_index >= len(TREE_COLUMNS): return
        db_column_name = TREE_COLUMNS[column_index]
        item_id = self.tree.identify_row(event.y)
        # Campos no editables
        if not item_id or db_column_name in ["path", "is_validated", "tasas"]: return 

        current_value = self.tree.set(item_id, db_column_name)
        x, y, width, height = self.tree.bbox(item_id, column_id)

        # Crear Entry para edición
        editor = ttk.Entry(self.tree) 
        editor.place(x=x, y=y, width=width, height=height)
        editor.insert(0, current_value)
        editor.focus_set()

        def save_edit(event=None):
            new_value = editor.get()
            file_path = self.tree.set(item_id, "path")

            if new_value != current_value:
                rows_affected = update_invoice_field(file_path, db_column_name, new_value)
                
                if rows_affected > 0:
                    # Recálculo si se edita base, iva o importe
                    if db_column_name in ['base', 'iva', 'importe']:
                        self.recalculate_and_update(file_path, db_column_name, new_value)
                    self.load_data_to_tree()
                else:
                    messagebox.showerror("Error de Actualización", "No se pudo actualizar el registro.")
            editor.destroy()

        editor.bind('<Return>', save_edit)
        editor.bind('<FocusOut>', save_edit)

    def recalculate_and_update(self, file_path: str, edited_column: str, edited_value: Any):
        """Recalcula Base/IVA/Importe automáticamente tras una edición numérica."""
        
        # 1. Recuperar los valores actuales
        conn = sqlite3.connect(database.DB_NAME) 
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT base, iva, importe FROM processed_invoices WHERE path = ?", (file_path,))
        row = cursor.fetchone()
        conn.close()
        if not row: return

        # 2. Obtener el valor editado limpio
        cleaned_edited_value = database._clean_numeric_value(edited_value)
        base, iva, importe = row['base'], row['iva'], row['importe']

        if edited_column == 'base':
            base = cleaned_edited_value
            # La función calculate_total_and_vat está en utils.py
            total_str, vat_str = calculate_total_and_vat(str(base), vat_rate=DEFAULT_VAT_RATE)
            importe = database._clean_numeric_value(total_str)
            iva = database._clean_numeric_value(vat_str)

        elif edited_column == 'importe':
            importe = cleaned_edited_value
            try:
                base = importe / (1 + DEFAULT_VAT_RATE)
                iva = importe - base
            except (ZeroDivisionError, TypeError):
                return

        # 3. Actualizar la BBDD con los nuevos valores
        conn = sqlite3.connect(database.DB_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE processed_invoices SET base = ?, iva = ?, importe = ? WHERE path = ?",
                       (base, iva, importe, file_path))
        conn.commit()
        conn.close()
        
# --- PUNTO DE ENTRADA --
if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1400x800") 
    app = InvoiceApp(root)
    root.mainloop()