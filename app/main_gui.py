
import os
import csv
import sqlite3
import sys
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Tuple, List, Optional, Any, Dict
import io 

# Importaciones de dependencias para el visor de documentos
try:
    import fitz # PyMuPDF
    from PIL import Image, ImageTk 
    VIEWER_AVAILABLE = True
except ImportError:
    fitz = None
    Image = None
    ImageTk = None
    VIEWER_AVAILABLE = False
    print("⚠️ ADVERTENCIA: Visor no disponible. Instale 'PyMuPDF' y 'Pillow' (pip install PyMuPDF Pillow).")


# Importar las partes refactorizadas
# Asegúrese de que estos módulos existen en su entorno
import database 
import logic
from config import TESSERACT_CMD_PATH, DEFAULT_VAT_RATE_STR, DEFAULT_VAT_RATE
from logic import extraer_datos
# update_invoice_field ahora funciona correctamente
# 🚨 CORRECCIÓN: Se añade DuplicateInvoiceError a las importaciones
from database import fetch_all_invoices, delete_invoice_data, fetch_all_invoices_OK, fetch_all_invoices_exported, insert_invoice_data, update_invoice_field, delete_entire_database_schema, is_invoice_processed, DuplicateInvoiceError 
# Se asume que 'utils' existe y contiene 'calculate_total_and_vat'
from utils import calculate_total_and_vat  

# 🚨 Llamar a la función de inicialización de la BBDD al inicio
# Esto creará la tabla 'extractors' si no existe y la llenará con los datos
# iniciales de INITIAL_EXTRACTION_MAPPING si la tabla está vacía.
database.initialize_extractors_data() # <--- ¡NUEVA LÍNEA CLAVE!

class InvoiceApp:
    def __init__(self, master):
        self.master = master
        master.title("Invoice Extractor App")
        database.setup_database() # Inicializar la BBDD

        self.tree: Optional[ttk.Treeview] = None
        self.log_text: Optional[ScrolledText] = None
        self.selected_file_path: Optional[str] = None
        
        # Atributos para el visor
        self.path_entry: Optional[ttk.Entry] = None
        self.file_name_entry: Optional[ttk.Entry] = None 
        
        # Atributos del Visor con Scroll
        self.viewer_canvas: Optional[tk.Canvas] = None
        self.viewer_content_frame: Optional[ttk.Frame] = None
        self.viewer_label: Optional[ttk.Label] = None
        self.canvas_window = None # ID de la ventana incrustada en el canvas
        self.current_image = None 
        
        # Atributos de Control (Variables para Checkboxes)
        self.files_to_process: List[str] = []
        self.process_button: Optional[ttk.Button] = None 
        self.debug_var = tk.BooleanVar(value=False) # Modo Debug
        self.reprocess_var = tk.BooleanVar(value=False) # Forzar Re-proceso
        self.log_var = tk.BooleanVar(value=True) # Ver Log de Selección (por defecto SÍ)
        
        # Zoom: Inicializar el factor de zoom a 1.0 (100%)
        self.current_zoom: float = 1.0 
        self.zoom_label_var = tk.StringVar(value=f"Zoom: {int(self.current_zoom * 100)}%") 

        # Paginación: Inicializar la página actual y el total
        self.current_page: int = 1
        self.total_pages: int = 1
        self.page_label_var = tk.StringVar(value=f"Página: {self.current_page} de {self.total_pages}") 

        self.setup_gui()
        self.load_data_to_tree()
        
        self.filesProcess: List[str] = []

        self.master.after(50, self._initial_sash_position)

    # ------------------------------------------------------------------
    # --- AJUSTES DE GUI Y CONFIGURACIÓN ---
    # ------------------------------------------------------------------

    def _initial_sash_position(self):
        """Ajusta la posición inicial de la barra divisoria."""
        try:
            self.master.update_idletasks() 
            window_width = self.master.winfo_width()
            initial_pos = int(window_width * 0.4)
            self.pane_window.sashpos(0, initial_pos)
        except tk.TclError:
            pass
            
            
    def setup_gui(self):
        self.main_frame = ttk.Frame(self.master, padding="10")
        self.main_frame.pack(fill='both', expand=True)

        # 1. PanedWindow para dividir la interfaz (Visor vs Tabla)
        self.pane_window = ttk.PanedWindow(self.main_frame, orient=tk.HORIZONTAL)
        self.pane_window.pack(fill='both', expand=True, pady=10)

        # ========================================================
        # PANEL IZQUIERDO: Visor de Documentos (40% de peso)
        # ========================================================
        viewer_panel = ttk.Frame(self.pane_window, padding="5")
        self.pane_window.add(viewer_panel, weight=2) 
        
        # 2. Campo de Ruta Completa del Fichero
        path_frame = ttk.LabelFrame(viewer_panel, text="Ruta Completa del Fichero", padding="5")
        path_frame.pack(side='top', fill='x', pady=(0, 5))
        
        self.path_entry = ttk.Entry(path_frame, state='readonly', width=50)
        self.path_entry.pack(fill='x', expand=True)
        self.show_file_path("Ningún archivo seleccionado.", clear=True)
        
        # 3. Campo de Nombre Corto del Fichero
        name_frame = ttk.LabelFrame(viewer_panel, text="Nombre del Archivo Seleccionado", padding="5")
        name_frame.pack(side='top', fill='x', pady=(0, 5))
        
        self.file_name_entry = ttk.Entry(name_frame, state='readonly', width=50)
        self.file_name_entry.pack(fill='x', expand=True)
        self.show_file_name("Ningún archivo seleccionado.", clear=True)

        # 4. Controles de Zoom y Paginación
        controls_frame = ttk.Frame(viewer_panel)
        controls_frame.pack(side='top', fill='x', pady=(5, 5))
        
        # Sub-frame de Zoom
        zoom_frame = ttk.Frame(controls_frame)
        zoom_frame.pack(side='left', padx=(0, 15))
        ttk.Label(zoom_frame, text="Zoom:").pack(side='left', padx=(0, 5))
        ttk.Button(zoom_frame, text="-", width=3, command=self.zoom_out).pack(side='left', padx=5)
        ttk.Button(zoom_frame, text="+", width=3, command=self.zoom_in).pack(side='left', padx=5)
        self.zoom_label = ttk.Label(zoom_frame, textvariable=self.zoom_label_var)
        self.zoom_label.pack(side='left', padx=10)

        # Sub-frame de Paginación
        page_frame = ttk.Frame(controls_frame)
        page_frame.pack(side='left', padx=(15, 0))
        ttk.Label(page_frame, text="Páginas:").pack(side='left', padx=(0, 5))
        ttk.Button(page_frame, text="<", width=3, command=self.prev_page).pack(side='left', padx=5)
        self.page_label = ttk.Label(page_frame, textvariable=self.page_label_var)
        self.page_label.pack(side='left', padx=10)
        ttk.Button(page_frame, text=">", width=3, command=self.next_page).pack(side='left', padx=5)


        # 5. Visor de Documentos (con Scroll)
        viewer_frame = ttk.LabelFrame(viewer_panel, text="Visor de Documentos", padding="5")
        viewer_frame.pack(side='top', fill='both', expand=True)

        # Frame para contener el Canvas y la barra de desplazamiento vertical
        canvas_v_frame = ttk.Frame(viewer_frame)
        canvas_v_frame.pack(side='top', fill='both', expand=True)

        # Canvas para el scrolling del contenido
        self.viewer_canvas = tk.Canvas(canvas_v_frame, borderwidth=0, highlightthickness=0, bg='light gray')
        self.viewer_canvas.pack(side='left', fill='both', expand=True)
        
        # Scrollbar Vertical
        v_scrollbar = ttk.Scrollbar(canvas_v_frame, orient=tk.VERTICAL, command=self.viewer_canvas.yview)
        v_scrollbar.pack(side='right', fill='y')
        self.viewer_canvas.config(yscrollcommand=v_scrollbar.set)
        
        # Scrollbar Horizontal (en la parte inferior del LabelFrame)
        h_scrollbar = ttk.Scrollbar(viewer_frame, orient=tk.HORIZONTAL, command=self.viewer_canvas.xview)
        h_scrollbar.pack(side='bottom', fill='x')
        self.viewer_canvas.config(xscrollcommand=h_scrollbar.set)
        
        # Frame dentro del Canvas para contener la imagen (el contenido scrollable)
        self.viewer_content_frame = ttk.Frame(self.viewer_canvas)
        # La ventana dentro del canvas que contendrá el frame con la imagen
        self.canvas_window = self.viewer_canvas.create_window((0, 0), window=self.viewer_content_frame, anchor="nw")

        # Vincular el evento <Configure> del marco de contenido para actualizar el scrollregion
        # El scrollregion se ajusta automáticamente al tamaño del contenido del frame
        self.viewer_content_frame.bind("<Configure>", 
                                       lambda event: self.viewer_canvas.config(scrollregion=self.viewer_canvas.bbox("all")))


        # Configurar el Label de la imagen dentro del frame de contenido
        if VIEWER_AVAILABLE:
            self.viewer_label = ttk.Label(self.viewer_content_frame, text="Seleccione una fila para ver el documento.")
        else:
            self.viewer_label = ttk.Label(self.viewer_content_frame, text="El visor requiere PyMuPDF y Pillow.\nPor favor, ejecute: pip install PyMuPDF Pillow", foreground='red')

        self.viewer_label.pack(expand=True, fill='both')


        # ========================================================
        # PANEL DERECHO: Tabla, Botones y Log (60% de peso)
        # ========================================================
        table_panel = ttk.Frame(self.pane_window, padding="5")
        self.pane_window.add(table_panel, weight=3) 

        table_panel = ttk.Frame(self.pane_window, padding="5")
        self.pane_window.add(table_panel, weight=3) 

        # Marco de Botones
        button_frame = ttk.Frame(table_panel)
        button_frame.pack(side='top', fill='x', pady=5)
        # -------------------------------------------------------------
        # 1. Botones de Selección
        select_frame = ttk.LabelFrame(button_frame, text="1. Seleccionar Ficheros/Carpeta", padding="5")
        select_frame.pack(side='left', padx=(0, 5))
        ttk.Button(select_frame, text="Archivos", command=self.select_files_dialog).pack(side='left', padx=5, pady=5)
        ttk.Button(select_frame, text="Carpeta", command=self.select_folder_dialog).pack(side='left', padx=5, pady=5)

        # 2. Botón y Opciones de Procesamiento
        process_options_frame = ttk.LabelFrame(button_frame, text="2. Opciones de Procesamiento", padding="5")
        process_options_frame.pack(side='left', padx=10)

        # Checkboxes
        check_frame = ttk.Frame(process_options_frame)
        check_frame.pack(side='top', fill='x')
        ttk.Checkbutton(check_frame, text="Forzar Re-proceso", variable=self.reprocess_var).pack(side='left', padx=5)
        ttk.Checkbutton(check_frame, text="Modo Debug", variable=self.debug_var).pack(side='left', padx=5)

        # Botón de Procesar
        self.process_button = ttk.Button(process_options_frame, text="Procesar (0 archivos)", command=self.process_selected_files)
        self.process_button.pack(side='top', fill='x', pady=5)

        # --- Contenedor para apilar 3 y 4 a la derecha ---
        # Este nuevo frame irá a la derecha de todo lo anterior.
        right_stack_frame = ttk.Frame(button_frame)
        right_stack_frame.pack(side='left', padx=(5, 0))

        # 3. Botones de Acciones (arriba a la derecha)
        op_frame1 = ttk.LabelFrame(right_stack_frame, text="3. Acciones", padding="5")
        op_frame1.pack(side='top', fill='x', pady=(0, 5)) # Empaquetado arriba en el nuevo contenedor
        ttk.Button(op_frame1, text="Exportar a CSV", command=self.export_to_csv).pack(side='left', padx=5, pady=5)
        ttk.Button(op_frame1, text="Editor de facturas", command=self.launch_extractor_generator).pack(side='left', padx=5, pady=5)

        # 4. Botones de Operación y Validar (debajo del 3)
        op_frame = ttk.LabelFrame(right_stack_frame, text="4. Operaciones", padding="5")
        op_frame.pack(side='top', fill='x') # Empaquetado debajo del 3 en el nuevo contenedor

        # --- CONTENIDO DEL FRAME 4 ---
        ttk.Button(op_frame, text="🔄 Recargar BBDD", command=self.reload_database).pack(side='left', padx=5, pady=5) 
        ttk.Button(op_frame, text="🔄 Ver Exportados", command=self.reload_database_exported).pack(side='left', padx=5, pady=5) 
        ttk.Button(op_frame, text="Limpiar BBDD", command=self.confirm_clear_database).pack(side='left', padx=5, pady=5)
        ttk.Button(op_frame, text="Eliminar", command=self.delete_selected_invoices).pack(side='left', padx=5, pady=5)
        ttk.Button(op_frame, text="Validar", command=self.validate_invoice).pack(side='left', padx=5, pady=5)
        # -------------------------------------------------------------

        # Marco de la Tabla (Treeview)
        tree_frame = ttk.Frame(table_panel)
        tree_frame.pack(side='top', fill='both', expand=True)

        columns = ("path", "file_name", "tipo", "fecha", "numero_factura", "emisor", "cif_emisor", "cliente", "cif", "modelo", "matricula", "base", "iva", "importe", "is_validated", "tasas")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show='headings')
        self.tree.tag_configure('validated', background='light green')
        self.tree.tag_configure('unvalidated', background='light yellow')

        self.tree.heading("file_name", text="Archivo", anchor="w")
        self.tree.heading("tipo", text="Tipo", anchor="center")
        self.tree.heading("fecha", text="Fecha", anchor="center")
        self.tree.heading("numero_factura", text="Nº Factura", anchor="center")
        self.tree.heading("emisor", text="Emisor", anchor="w")
        self.tree.heading("cif_emisor", text="CIF  Emisor", anchor="w")
        self.tree.heading("cliente", text="Cliente", anchor="w")
        self.tree.heading("cif", text="CIF", anchor="center")
        self.tree.heading("modelo", text="Modelo", anchor="center")
        self.tree.heading("matricula", text="Matrícula", anchor="center")
        self.tree.heading("base", text="Base", anchor="e")
        self.tree.heading("iva", text="IVA", anchor="e")
        self.tree.heading("importe", text="Importe", anchor="e")
        self.tree.heading("tasas", text="tasas", anchor="e") 
        self.tree.heading("is_validated", text="Validada", anchor="center")
        
        self.tree.column("path", width=0, stretch=tk.NO) 
        self.tree.column("tasas", width=0, stretch=tk.NO) 
        self.tree.column("file_name", width=150, anchor="w")
        self.tree.column("base", width=80, anchor="e")
        self.tree.column("importe", width=80, anchor="e")
        
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        vsb.pack(side='right', fill='y')
        hsb.pack(side='bottom', fill='x')
        self.tree.pack(side='top', fill='both', expand=True)

        self.tree.bind('<<TreeviewSelect>>', self.on_item_select)
        self.tree.bind('<Double-1>', self.on_double_click)
        
        # Marco del Log (abajo del panel derecho)
        log_frame = ttk.LabelFrame(table_panel, text="Log de Extracción", padding="5")
        log_frame.pack(side='bottom', fill='x', pady=5, ipady=5)
        
        # Checkbox para control de visibilidad del log
        log_check_frame = ttk.Frame(log_frame)
        log_check_frame.pack(side='top', fill='x')
        ttk.Checkbutton(log_check_frame, text="Ver Log Detalle al Seleccionar Fila", variable=self.log_var, command=self.on_log_checkbox_toggle).pack(side='right', padx=5)

        self.log_text = ScrolledText(log_frame, wrap=tk.WORD, height=8, width=80)
        self.log_text.pack(fill='both', expand=True)
        self.log_text.insert(tk.END, f"Listo. Tasa de IVA por defecto: {DEFAULT_VAT_RATE_STR}\n")

    # ------------------------------------------------------------------
    # --- MÉTODOS DE VISTAS Y ACTUALIZACIONES ---
    # ------------------------------------------------------------------
    
    # --- Paginación, Zoom, Vistas (sin cambios) ---
    def _get_total_pages(self, file_path: str) -> int:
        if not VIEWER_AVAILABLE:
            return 1
            
        file_extension = os.path.splitext(file_path)[1].lower()
        if file_extension == ".pdf":
            try:
                doc = fitz.open(file_path)
                num_pages = len(doc)
                doc.close()
                return num_pages
            except Exception:
                return 1 
        elif file_extension in ['.jpg', '.jpeg', '.png', '.tiff', '.tif']:
            return 1
        return 1

    def _update_page_label(self):
        self.page_label_var.set(f"Página: {self.current_page} de {self.total_pages}")

    def next_page(self):
        if self.selected_file_path and self.current_page < self.total_pages:
            self.current_page += 1
            self._reload_viewer()

    def prev_page(self):
        if self.selected_file_path and self.current_page > 1:
            self.current_page -= 1
            self._reload_viewer()
            
    def _update_zoom_label(self):
        self.zoom_label_var.set(f"Zoom: {int(self.current_zoom * 100)}%")

    def _reload_viewer(self):
        if self.selected_file_path and VIEWER_AVAILABLE:
            self.display_document_preview(self.selected_file_path)
        self._update_zoom_label()
        self._update_page_label() 

    def zoom_in(self):
        if self.current_zoom < 3.0: 
            self.current_zoom += 0.25
            self._reload_viewer()

    def zoom_out(self):
        if self.current_zoom > 0.25: 
            self.current_zoom -= 0.25
            self._reload_viewer()
            
    def _update_process_buttons_text(self):
        count = len(self.files_to_process)
        if self.process_button:
            self.process_button.config(text=f"Procesar ({count} archivos)")
            
    def show_file_name(self, name: str, clear: bool = False):
        if self.file_name_entry:
            self.file_name_entry.configure(state='normal')
            self.file_name_entry.delete(0, tk.END)
            self.file_name_entry.insert(0, name)
            self.file_name_entry.configure(state='readonly')
    
    def show_file_path(self, path: str, clear: bool = False):
        if self.path_entry:
            self.path_entry.configure(state='normal')
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, path)
            self.path_entry.configure(state='readonly')

    def update_log_display(self, text: str, clear: bool = False):
        if self.log_text:
            if clear: self.log_text.delete('1.0', tk.END)
            self.log_text.insert(tk.END, text + "\n")
            self.log_text.see(tk.END)

    def on_log_checkbox_toggle(self):
        if self.tree.selection():
            self.on_item_select(None)
            
    def on_item_select(self, event):
        selected_items = self.tree.selection()
        
        if not selected_items:
            self.selected_file_path = None
            self.show_file_path("Ningún archivo seleccionado.", clear=True)
            self.show_file_name("Ningún archivo seleccionado.", clear=True)
            if self.viewer_label:
                self.viewer_canvas.itemconfig(self.canvas_window, width=1, height=1) 
                self.viewer_label.config(image='', text="Seleccione una fila para ver el documento.")
            self.update_log_display("Ningún archivo seleccionado.", clear=True)
            
            self.current_page = 1
            self.total_pages = 1
            self.current_zoom = 1.0
            self._update_zoom_label()
            self._update_page_label()
            return

        item = selected_items[0]
        new_file_path = self.tree.item(item, 'values')[0]
        file_name = self.tree.item(item, 'values')[1]

        if new_file_path != self.selected_file_path:
             self.current_zoom = 1.0
             self._update_zoom_label()
             self.current_page = 1
             self.total_pages = self._get_total_pages(new_file_path)
             self._update_page_label()


        self.selected_file_path = new_file_path
        self.show_file_path(self.selected_file_path)
        self.show_file_name(file_name)
        
        if VIEWER_AVAILABLE:
            self.display_document_preview(self.selected_file_path) 
        else:
            self.viewer_label.config(text="El visor no está disponible (instale PyMuPDF y Pillow).")

        if self.log_var.get():
            log_data = self._get_log_data_for_path(self.selected_file_path)
            self.update_log_display(f"Ruta: {self.selected_file_path}\nLog de Extracción:\n{log_data}", clear=True)
        else:
            self.update_log_display("Log de selección oculto.", clear=True)
            
    def display_document_preview(self, file_path: str):
        if not VIEWER_AVAILABLE:
            self.viewer_label.config(text="El visor no está disponible (instale PyMuPDF y Pillow).")
            return

        file_extension = os.path.splitext(file_path)[1].lower()
        image_to_display = None
        
        try:
            if file_extension == ".pdf":
                doc = fitz.open(file_path)
                if len(doc) > 0 and self.current_page <= len(doc):
                    page = doc.load_page(self.current_page - 1) 
                    mat = fitz.Matrix(self.current_zoom, self.current_zoom)
                    pix = page.get_pixmap(matrix=mat, alpha=False)
                    doc.close()

                    img_data = pix.tobytes("ppm")
                    image_to_display = Image.open(io.BytesIO(img_data))
                else:
                    self.viewer_label.config(text="PDF vacío o página fuera de rango.")
                    doc.close()
                    return
            
            elif file_extension in ['.jpg', '.jpeg', '.png', '.tiff', '.tif']:
                img = Image.open(file_path)
                img_width, img_height = img.size
                new_width = int(img_width * self.current_zoom)
                new_height = int(img_height * self.current_zoom)
                
                if new_width > 0 and new_height > 0:
                    image_to_display = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                else:
                    self.viewer_label.config(text="Error al calcular tamaño de imagen con el zoom actual.")
                    return
            
            else:
                self.viewer_label.config(text="Formato de archivo no soportado para previsualización.")
                return

            self.current_image = ImageTk.PhotoImage(image_to_display)
            
            img_w, img_h = image_to_display.size

            self.viewer_canvas.itemconfig(self.canvas_window, width=img_w, height=img_h)

            self.viewer_label.config(image=self.current_image, text="")
            self.viewer_label.image = self.current_image 
            
            self.viewer_canvas.xview_moveto(0)
            self.viewer_canvas.yview_moveto(0)

        except Exception as e:
            self.viewer_label.config(text=f"Error al cargar la previsualización: {e}")
            self.current_image = None
            
    # ------------------------------------------------------------------
    # --- MÉTODOS DE SELECCIÓN Y PROCESAMIENTO (sin cambios) ---
    # ------------------------------------------------------------------
    
    def select_files_dialog(self):
        file_paths = filedialog.askopenfilenames(
            title="Seleccionar archivos de factura (PDF, JPG, PNG, etc.)",
            filetypes=[("Archivos de Documento", "*.pdf *.jpg *.jpeg *.png *.tiff *.tif")]
        )
        if file_paths:
            self.files_to_process = list(file_paths)
            self._update_process_buttons_text()
            self.update_log_display(f"Seleccionados {len(self.files_to_process)} archivos. Listo para procesar.", clear=True)

    def select_folder_dialog(self):
        folder_path = filedialog.askdirectory(
            title="Seleccionar carpeta que contiene facturas"
        )
        if folder_path:
            supported_extensions = ('.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.tif')
            self.files_to_process = []
            
            for root, _, files in os.walk(folder_path):
                for file_name in files:
                    if file_name.lower().endswith(supported_extensions):
                        self.files_to_process.append(os.path.join(root, file_name))

            self._update_process_buttons_text()
            self.update_log_display(f"Seleccionados {len(self.files_to_process)} archivos de la carpeta: {folder_path}. Listo para procesar.", clear=True)
    
    def process_selected_files(self):
        if not self.files_to_process:
            messagebox.showwarning("Procesar", "Primero debe seleccionar archivos usando los botones '1. Seleccionar...'.")
            return
            
        file_paths = self.files_to_process 
        force_reprocess = self.reprocess_var.get()
        debug_mode = self.debug_var.get()

        total_processed = 0
        self.update_log_display(f"--- Iniciando procesamiento de {len(file_paths)} archivos (Debug={debug_mode}, Forzar={force_reprocess})... ---", clear=True)

        KEYS = ['Tipo', 'Fecha', 'Número de Factura', 'Emisor', 'CIF Emisor','Cliente', 'CIF', 'Modelo', 'Matricula', 'Importe', 'Base', 'IVA', 'Tasas']

        for i, file_path in enumerate(file_paths):
            self.update_log_display(f"[{i+1}/{len(file_paths)}] Procesando: {os.path.basename(file_path)}...")

            if not force_reprocess and is_invoice_processed(file_path): 
                self.update_log_display("  -> Ya procesado. Saltando.")
                continue

            extraction_result = extraer_datos(file_path, debug_mode=debug_mode) 

            if len(extraction_result) == 13:
                print("tamaño",len(extraction_result))
            if len(extraction_result) == 14:
                data_tuple, log_data = extraction_result[:-1], extraction_result[-1]

            else:
                data_tuple = logic._pad_data(extraction_result) 
                log_data = "Error de formato de resultado."

            data_dict = dict(zip(KEYS, data_tuple))
            data_dict['Archivo'] = os.path.basename(file_path)
            data_dict['DebugLines'] = log_data

            try:
                insert_invoice_data(data_dict, original_path=file_path, is_validated=0) 
                self.update_log_display(f"  -> Datos de factura guardados/actualizados: {data_dict.get('Número de Factura', 'N/A')}")
                self.filesProcess.append(file_path)
                total_processed += 1
            except DuplicateInvoiceError as e: # type: ignore
            # 🚨 ERROR CONTROLADO: Muestra el popup de duplicado.
                messagebox.showerror("Error de Inserción", f"¡La factura es un duplicado!\n\n{str(e)}")
                continue
            except sqlite3.Error as e:
            # Otros errores de BBDD
                messagebox.showerror("Error de Base de Datos", f"Fallo al insertar la factura: {e}")
        
            except Exception as e:
            # Cualquier otro error inesperado
                messagebox.showerror("Error Inesperado", f"Ocurrió un error al procesar la factura: {e}")


        self.update_log_display(f"--- Procesamiento finalizado. {total_processed} archivos procesados/re-procesados. ---")
        self.load_data_to_tree()
        self.launch_extractor_generatorProcesed()
        self.files_to_process = []
        self._update_process_buttons_text()


    # ------------------------------------------------------------------
    # --- Nuevo Método de Recarga ---
    # ------------------------------------------------------------------

    def reload_database(self):
        """Recarga los datos de la BBDD y actualiza el Treeview."""
        self.load_data_to_tree()
        self.update_log_display("Base de datos recargada. La tabla ha sido actualizada.", clear=True)
        messagebox.showinfo("Recarga Completa", "Los datos de la base de datos han sido recargados y la tabla ha sido actualizada.")

    def reload_database_exported(self):
        """Recarga los datos de la BBDD y actualiza el Treeview."""
        self.load_data_to_tree_exported()
        self.update_log_display("Base de datos recargada. La tabla ha sido actualizada.", clear=True)
        messagebox.showinfo("Recarga Completa", "Los datos de la base de datos han sido recargados y la tabla ha sido actualizada.")
    
    # ------------------------------------------------------------------
    # --- MÉTODOS DE BBDD Y EDICIÓN ---
    # ------------------------------------------------------------------
    def safe_float(self, value):
        """Convierte un valor a float, devolviendo 0.0 si no es numérico o es None."""
        try:
            if value is None or value == "":
                return 0.0
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def load_data_to_tree(self):
        """Carga los datos de la BBDD al Treeview."""
        # Limpiar tabla
        for i in self.tree.get_children():
            self.tree.delete(i)

        try:
            invoices = fetch_all_invoices()
            for inv in invoices:
                values = (
                    inv.get('path'),
                    inv.get('file_name'),
                    inv.get('tipo'),
                    inv.get('fecha'),
                    inv.get('numero_factura'),
                    inv.get('emisor'),
                    inv.get('cif_emisor'),
                    inv.get('cliente'),
                    inv.get('cif'),
                    inv.get('modelo'),
                    inv.get('matricula'),
                    f"{self.safe_float(inv.get('base')):.2f}".replace('.', ','),
                    f"{self.safe_float(inv.get('iva')):.2f}".replace('.', ','),
                    f"{self.safe_float(inv.get('importe')):.2f}".replace('.', ','),
                    "✅" if inv.get('is_validated') == 1 else "❌",
                    f"{self.safe_float(inv.get('tasas')):.2f}".replace('.', ','),
                )
                tag = 'validated' if inv.get('is_validated') == 1 else 'unvalidated'
                self.tree.insert('', tk.END, values=values, tags=(tag,))

        except Exception as e:
            messagebox.showerror("Error de BBDD", f"Fallo al cargar datos de la base de datos: {e}")

    def load_data_to_tree_exported(self):
        """Carga los datos de la BBDD al Treeview."""
        # Limpiar tabla
        for i in self.tree.get_children():
            self.tree.delete(i)

        try:
            invoices = fetch_all_invoices_exported()
            for inv in invoices:
                values = (
                    inv.get('path'),
                    inv.get('file_name'),
                    inv.get('tipo'),
                    inv.get('fecha'),
                    inv.get('numero_factura'),
                    inv.get('emisor'),
                    inv.get('cif_emisor'),
                    inv.get('cliente'),
                    inv.get('cif'),
                    inv.get('modelo'),
                    inv.get('matricula'),
                    f"{self.safe_float(inv.get('base')):.2f}".replace('.', ','),
                    f"{self.safe_float(inv.get('iva')):.2f}".replace('.', ','),
                    f"{self.safe_float(inv.get('importe')):.2f}".replace('.', ','),
                    "✅" if inv.get('is_validated') == 1 else "❌",
                    f"{self.safe_float(inv.get('tasas')):.2f}".replace('.', ','),
                )
                tag = 'validated' if inv.get('is_validated') == 1 else 'unvalidated'
                self.tree.insert('', tk.END, values=values, tags=(tag,))

        except Exception as e:
            messagebox.showerror("Error de BBDD", f"Fallo al cargar datos de la base de datos: {e}")

    
        
    def _get_log_data_for_path(self, file_path: str) -> str:
        """Busca el log_data para un path dado directamente en la BBDD."""
        if not file_path:
            return "Ruta no válida."
        import sqlite3 # Importar para usar sqlite3.connect y Row
        conn = sqlite3.connect(database.DB_NAME)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT log_data FROM processed_invoices WHERE path = ?", (file_path,))
            result = cursor.fetchone()
            return result[0] if result and result[0] else "Log no disponible."
        except Exception as e:
            return f"Error al recuperar log_data: {e}"
        finally:
            conn.close()

    def on_double_click(self, event):
        """Maneja el doble click para activar la edición de celda."""
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell": return

        column_id = self.tree.identify_column(event.x)
        column_index = int(column_id.replace('#', '')) - 1

        TREE_COLUMNS = ("path", "file_name", "tipo", "fecha", "numero_factura", "emisor", "cid_emisor", "cliente", "cif", "modelo", "matricula", "base", "iva", "importe", "is_validated", "tasas")
        TREE_COLUMNS = ("path", "file_name", "tipo", "fecha", "numero_factura", "emisor", "cif_emisor", "cliente", "cif", "modelo", "matricula", "base", "iva", "importe", "is_validated", "tasas")
        if column_index < 0 or column_index >= len(TREE_COLUMNS): return
        db_column_name = TREE_COLUMNS[column_index]
        item_id = self.tree.identify_row(event.y)
        # Campos no editables
        if not item_id or db_column_name in ["path", "is_validated", "tasas"]: return 

        current_value = self.tree.set(item_id, db_column_name)
        x, y, width, height = self.tree.bbox(item_id, column_id)

        # FIX TclError: Eliminamos el estilo no definido
        editor = ttk.Entry(self.tree) 
        editor.place(x=x, y=y, width=width, height=height)
        editor.insert(0, current_value)
        editor.focus_set()

        def save_edit(event=None):
            new_value = editor.get()
            file_path = self.tree.set(item_id, "path")

            if new_value != current_value:
                # La función update_invoice_field ahora devolverá cursor.rowcount
                rows_affected = update_invoice_field(file_path, db_column_name, new_value)
                
                if rows_affected > 0:
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
        import sqlite3 # Importar para usar sqlite3.connect y Row
        conn = sqlite3.connect(database.DB_NAME) 
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT base, iva, importe FROM processed_invoices WHERE path = ?", (file_path,))
        row = cursor.fetchone()
        conn.close()
        if not row: return

        # database._clean_numeric_value se ha movido/definido en database.py
        cleaned_edited_value = database._clean_numeric_value(edited_value)
        base, iva, importe = row['base'], row['iva'], row['importe']

        if edited_column == 'base':
            base = cleaned_edited_value
            # calculate_total_and_vat se importa de utils.py
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

        conn = sqlite3.connect(database.DB_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE processed_invoices SET base = ?, iva = ?, importe = ? WHERE path = ?",
                       (base, iva, importe, file_path))
        conn.commit()
        conn.close()

    def validate_invoice(self):
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("Validación", "Seleccione un registro para validar.")
            return

        item_id = selected_items[0]
        file_path = self.tree.item(item_id, 'values')[0]

        if update_invoice_field(file_path, 'is_validated', 1): 
             messagebox.showinfo("Validación", "Registro marcado como validado.")
             self.load_data_to_tree()
        else:
             messagebox.showerror("Error", "Fallo al validar el registro.")

    def export_to_csv(self):
        output_file = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("Archivos CSV", "*.csv")],
            title="Guardar datos de factura como CSV"
        )
        if not output_file: return

        try:
            invoices = fetch_all_invoices_OK() 
            if not invoices:
                messagebox.showinfo("Exportación", "No hay datos para exportar.")
                return

            # Lista para guardar los paths de las facturas que se van a exportar
            exported_paths = []
            
            # Obtener los nombres de los campos para el encabezado del CSV
            # Eliminamos 'exportado' de los campos que vamos a escribir al CSV para
            # evitar duplicidad o problemas si se quiere añadir después, pero lo incluimos
            # si realmente quieres verlo en el CSV. Aquí lo mantendremos para simplicidad.
            fieldnames = list(invoices[0].keys()) 

            with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=';') 
                writer.writeheader()
                writer.writerows(invoices)
                
                # Recorremos la lista de facturas para obtener los paths
                for inv in invoices:
                    exported_paths.append(inv.get('path'))

            # --- PARTE CLAVE: ACTUALIZAR EL ESTADO EN LA BBDD ---
            from datetime import datetime
            # Usar el formato ISO para consistencia con 'procesado_en'
            export_timestamp = datetime.now().isoformat() 
            
            # Llamamos a la nueva función para actualizar el campo 'exportado'
            rows_updated = database.update_invoices_exported_status(exported_paths, export_timestamp) 
            
            # Recargar la tabla para mostrar el nuevo estado 'exportado' si es visible
            self.load_data_to_tree() 
            # -----------------------------------------------------

            messagebox.showinfo("Exportación Exitosa", f"Datos exportados a: {output_file}\n{rows_updated} registros actualizados en BBDD.")
        
        except Exception as e:
            messagebox.showerror("Error de Exportación", f"Fallo al exportar a CSV: {e}")

    def delete_selected_invoices(self):
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("Eliminar", "Seleccione al menos un registro para eliminar.")
            return

        paths_to_delete = [self.tree.item(item, 'values')[0] for item in selected_items]
        if messagebox.askyesno("Confirmar Eliminación", f"¿Está seguro de que desea eliminar {len(paths_to_delete)} registro(s)?"):
            deleted_count = delete_invoice_data(paths_to_delete) 
            messagebox.showinfo("Eliminación", f"{deleted_count} registro(s) eliminados.")
            self.load_data_to_tree()
            self.update_log_display("Registros eliminados.", clear=True)

    def confirm_clear_database(self):
        if messagebox.askyesno("ADVERTENCIA: Limpiar BBDD", "¿Está ABSOLUTAMENTE seguro de que desea eliminar *toda* la tabla 'processed_invoices'?"):
            if delete_entire_database_schema(): 
                messagebox.showinfo("BBDD Limpia", "La tabla de facturas ha sido eliminada.")
                database.setup_database()
                self.load_data_to_tree()
                self.update_log_display("Base de datos completamente limpiada y re-inicializada.", clear=True)
            else:
                messagebox.showerror("Error", "Fallo al intentar eliminar la base de datos.")

    def launch_extractor_generator(self):
        if not self.selected_file_path:
            messagebox.showwarning("Generador", "Seleccione un registro en la tabla para pasar los datos al generador.")
            return

        import sqlite3 # Necesario para sqlite3.connect y Row
        conn = sqlite3.connect(database.DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM processed_invoices WHERE path = ?", (self.selected_file_path,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            messagebox.showerror("Error", "No se encontraron datos completos para la fila seleccionada.")
            return

        nombre_base_archivo = os.path.splitext(row['file_name'])[0]
        comando = [
            sys.executable,
            'extractor_generator_gui.py',
            str(row['path']),              # 1
            str(nombre_base_archivo),      # 2 (Extractor Name Suggestion)
            str(row['log_data'] or ""),    # 3 (Debug Lines)
            str(row['tipo'] or ""),        # 4
            str(row['fecha'] or ""),       # 5
            str(row['numero_factura'] or ""), # 6
            str(row['emisor'] or ""),      # 7
            str(row['cif_emisor'] or ""),  # 8
            str(row['cliente'] or ""),     # 9
            str(row['cif'] or ""),         # 10
            str(row['modelo'] or ""),      # 11
            str(row['matricula'] or ""),   # 12
            str(row['base'] if row['base'] is not None else ""), # 13
            str(row['iva'] if row['iva'] is not None else ""),   # 14
            str(row['importe'] if row['importe'] is not None else ""), # 15
            str(row['tasas'] if row['tasas'] is not None else "")  # 16
        ]

        try:
            subprocess.Popen(comando)
            messagebox.showinfo("Llamada Exitosa", "Se ha lanzado el programa 'extractor_generator_gui.py'.")
        except Exception as e:
            messagebox.showerror("Error de Ejecución", f"No se pudo ejecutar 'extractor_generator_gui.py'.\nError: {e}")

    def launch_extractor_generatorProcesed(self):
        if not self.filesProcess:
            # Si la lista está vacía, no hay nada que procesar. Salir de la función.
            return
        import sqlite3 # Necesario para sqlite3.connect y Row
        conn = sqlite3.connect(database.DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM processed_invoices WHERE path = ?", (self.filesProcess[0],))
        row = cursor.fetchone()
        conn.close()
        if not row:
            messagebox.showerror("Error", "No se encontraron datos completos para la fila seleccionada.")
            return

        nombre_base_archivo = os.path.splitext(row['file_name'])[0]
        comando = [
            sys.executable,
            'extractor_generator_gui.py',
            str(row['path']),              # 1
            str(nombre_base_archivo),      # 2 (Extractor Name Suggestion)
            str(row['log_data'] or ""),    # 3 (Debug Lines)
            str(row['tipo'] or ""),        # 4
            str(row['fecha'] or ""),       # 5
            str(row['numero_factura'] or ""), # 6
            str(row['emisor'] or ""),      # 7
            str(row['cif_emisor'] or ""),  # 8
            str(row['cliente'] or ""),     # 9
            str(row['cif'] or ""),         # 10
            str(row['modelo'] or ""),      # 11
            str(row['matricula'] or ""),   # 12
            str(row['base'] if row['base'] is not None else ""), # 13
            str(row['iva'] if row['iva'] is not None else ""),   # 14
            str(row['importe'] if row['importe'] is not None else ""), # 15
            str(row['tasas'] if row['tasas'] is not None else "")  # 16
        ]

        try:
            subprocess.Popen(comando)
        except Exception as e:
            messagebox.showerror("Error de Ejecución", f"No se pudo ejecutar 'extractor_generator_gui.py'.\nError: {e}")

# --- PUNTO DE ENTRADA --
if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1400x800") 
    app = InvoiceApp(root)
    root.mainloop()