# viewer_panel.py

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional, Any, Tuple
import os
import io # <--- CORRECCIÓN 1: IMPORTAR MÓDULO IO

# Importaciones de módulos necesarios
# Nota: La App principal (self.app) tendrá acceso a los demás módulos (database, utils)
# y a las constantes (DEFAULT_VAT_RATE, etc.)

# Importaciones de dependencias para el visor de documentos
try:
    import fitz # PyMuPDF
    from PIL import Image, ImageTk, ImageDraw
    VIEWER_AVAILABLE = True
except ImportError:
    fitz = None
    Image = None
    ImageTk = None
    ImageDraw = None
    VIEWER_AVAILABLE = False


class DocumentViewer:
    
    def __init__(self, parent_frame, app_instance):
        self.app = app_instance # Referencia a la clase InvoiceApp principal
        self.parent = parent_frame
        
        if not VIEWER_AVAILABLE:
            ttk.Label(parent_frame, text="Visor no disponible. Instale PyMuPDF y Pillow.").pack(expand=True, fill=tk.BOTH)
            return

        self._create_widgets()


    def _create_widgets(self):
        """Crea el canvas y los controles de navegación/zoom del visor."""
        
        # Frame de Controles (Top)
        control_frame = ttk.Frame(self.parent)
        control_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Botones de navegación de documento (Facturas)
        ttk.Button(control_frame, text="⬅️ Factura Anterior", command=lambda: self.app.load_invoice(-1)).pack(side=tk.LEFT, padx=5)
        self.app.invoice_position_label = ttk.Label(control_frame, text="Factura X de Y") # Referencia almacenada en app
        self.app.invoice_position_label.pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Factura Siguiente ➡️", command=lambda: self.app.load_invoice(1)).pack(side=tk.LEFT, padx=5)
        
        # Separador
        ttk.Separator(control_frame, orient='vertical').pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=2)
        
        # Botones de Rotación de página (90 grados)
        ttk.Button(control_frame, text="⟲ Rotar", command=lambda: self.rotate_page(90)).pack(side=tk.LEFT, padx=5)
        
        # Etiqueta de página y Botones de navegación de página
        self.page_label = ttk.Label(control_frame, text="Página 0 de 0")
        self.page_label.pack(side=tk.RIGHT, padx=5)
        ttk.Button(control_frame, text="Página >", command=lambda: self.goto_page(1)).pack(side=tk.RIGHT, padx=5)
        ttk.Button(control_frame, text="< Página", command=lambda: self.goto_page(-1)).pack(side=tk.RIGHT, padx=5)
        
        # Frame para Canvas (Contenedor del área de visualización)
        canvas_frame = ttk.Frame(self.parent, relief=tk.SUNKEN)
        canvas_frame.pack(expand=True, fill=tk.BOTH)

        # Canvas para la imagen del documento
        self.app.canvas = tk.Canvas(canvas_frame, bg='gray') # Referencia almacenada en app
        self.app.canvas.pack(expand=True, fill=tk.BOTH)
        
        # Frame de Estado (Bottom)
        status_frame = ttk.Frame(self.parent)
        status_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Label(status_frame, text="Palabra:").pack(side=tk.LEFT)
        ttk.Label(status_frame, textvariable=self.app.word_var, foreground="blue").pack(side=tk.LEFT, padx=5)
        ttk.Label(status_frame, text="| Línea Ref:").pack(side=tk.LEFT, padx=(10, 0))
        ttk.Label(status_frame, textvariable=self.app.line_ref_var, foreground="green").pack(side=tk.LEFT, padx=5)
        
        # Bindings de Eventos
        self.app.canvas.bind("<ButtonPress-1>", self._on_selection_start)
        self.app.canvas.bind("<B1-Motion>", self._on_selection_drag)
        self.app.canvas.bind("<ButtonRelease-1>", self._on_selection_release)
        
        # Bindings para Zoom (Ctrl + Rueda del ratón)
        self.app.canvas.bind("<Control-MouseWheel>", self._handle_mouse_wheel_zoom) # Windows/Linux
        self.app.canvas.bind("<Control-Button-4>", self._handle_mouse_wheel_zoom) # Unix/Mac Scroll Up
        self.app.canvas.bind("<Control-Button-5>", self._handle_mouse_wheel_zoom) # Unix/Mac Scroll Down


    def initial_load(self):
        """Carga inicial del documento en el visor al iniciar la GUI."""
        if self.app.file_path and os.path.exists(self.app.file_path):
            self._open_document(self.app.file_path)
        else:
            self.app.doc = None
            self.render_page()
            if self.app.file_path and 'placeholder' not in self.app.file_path:
                messagebox.showwarning("Advertencia Inicial", f"El archivo '{self.app.file_path}' no se encontró en disco.")
        
        # Actualizar la etiqueta de posición inicial
        total_invoices = len(self.app.invoice_file_paths)
        if self.app.invoice_position_label:
            if total_invoices > 0:
                self.app.invoice_position_label.config(text=f"Factura {self.app.current_invoice_index + 1} de {total_invoices}")
            else:
                self.app.invoice_position_label.config(text=f"Factura 0 de 0 (Sin datos en BBDD)")

    def _open_document(self, file_path):
        """Abre un documento PDF o imagen."""
        if not VIEWER_AVAILABLE: return
        if not file_path or not os.path.exists(file_path):
            self.app.doc = None
            self.render_page() # Limpia el canvas
            return

        try:
            self.app.doc = fitz.open(file_path)
            self.app.page_num = 0
            self.app.rotation = 0
            self.app.zoom_level = 1.0
            self.render_page()
        except Exception as e:
            self.app.doc = None
            messagebox.showerror("Error de Documento", f"No se pudo abrir el documento: {e}")
            self.render_page()


    def render_page(self):
        """Renderiza y muestra la página actual del documento."""
        if self.app.doc:
            self._display_page()
            
        # Actualizar la etiqueta de página
        if self.app.doc:
            num_pages = self.app.doc.page_count
            self.page_label.config(text=f"Página {self.app.page_num + 1} de {num_pages}")
        else:
            self.app.canvas.delete(tk.ALL)
            self.page_label.config(text="Página 0 de 0")


    def _display_page(self):
        """Renderiza y muestra la página del documento actual en el canvas."""
        if not self.app.doc or not VIEWER_AVAILABLE: return

        self.app.canvas.delete(tk.ALL)
        self.app.image_display = None
        
        page = self.app.doc[self.app.page_num]
        
        # --- SOLUCIÓN DE COMPATIBILIDAD MÁXIMA PARA CUALQUIER VERSIÓN DE PYMUPDF ---
        
        # Crear una matriz de identidad (escala 1,1; rotación 0)
        matrix = fitz.Matrix(1, 1) 
        
        # Aplicar primero el Zoom (Escalado)
        matrix = matrix.scale(self.app.zoom_level, self.app.zoom_level)
        
        # Aplicar luego la Rotación
        # Esto usa el método más fundamental de PyMuPDF, que aplica la rotación 
        # a la matriz existente. Debería ser universalmente compatible.
        matrix = matrix.preRotate(self.app.rotation)
        
        # Obtener el pixmap y la imagen PIL
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        img_data = pix.tobytes("ppm")
        image = Image.open(io.BytesIO(img_data)) # Ahora 'io' está importado
        
        # Convertir a PhotoImage y actualizar el canvas
        self.app.photo_image = ImageTk.PhotoImage(image=image)
        self.app.canvas.config(width=image.width, height=image.height)
        self.app.image_display = self.app.canvas.create_image(0, 0, image=self.app.photo_image, anchor=tk.NW)


    def goto_page(self, delta: int):
        """Navega a la página siguiente o anterior."""
        if not self.app.doc: return
        
        new_page = self.app.page_num + delta
        num_pages = self.app.doc.page_count
        
        if 0 <= new_page < num_pages:
            self.app.page_num = new_page
            self.render_page()
        else:
            messagebox.showinfo("Navegación", "Límite de páginas alcanzado.")
            
    def rotate_page(self, angle: int):
        """Rota la página y redibuja."""
        if not self.app.doc: return
        
        self.app.rotation = (self.app.rotation + angle) % 360
        self.render_page()

    def _handle_mouse_wheel_zoom(self, event):
        """ Controla el zoom de la página al pulsar Control + Rueda del ratón. """
        if not self.app.doc or not VIEWER_AVAILABLE: return
        ZOOM_INCREMENT = 1.10
        
        # Ajuste para diferentes sistemas operativos
        delta = event.delta if event.num is None else (1 if event.num == 4 else -1)
        
        if delta > 0:
            self.app.zoom_level *= ZOOM_INCREMENT
        else:
            self.app.zoom_level /= ZOOM_INCREMENT
        
        self.app.zoom_level = max(0.1, min(10.0, self.app.zoom_level))
        self.render_page()

    def _on_selection_start(self, event):
        # ... (Lógica completa de _on_selection_start)
        if not self.app.doc or not VIEWER_AVAILABLE: return
        self.app.start_x = self.app.canvas.canvasx(event.x)
        self.app.start_y = self.app.canvas.canvasy(event.y)
        self.app.canvas.delete("selection_rect")
        self.app.selection_rect_id = None

    def _on_selection_drag(self, event):
        # ... (Lógica completa de _on_selection_drag)
        if self.app.start_x is None or self.app.start_y is None: return
        x = self.app.canvas.canvasx(event.x)
        y = self.app.canvas.canvasy(event.y)
        self.app.canvas.delete("selection_rect")
        self.app.selection_rect_id = self.app.canvas.create_rectangle(
            self.app.start_x, self.app.start_y, x, y, 
            outline='red', width=2, dash=(3, 3), tags="selection_rect"
        )
        
    def _on_selection_release(self, event):
        # ... (Lógica completa de _on_selection_release, incluyendo la extracción de texto)
        if not self.app.doc or not VIEWER_AVAILABLE: return
        end_x = self.app.canvas.canvasx(event.x)
        end_y = self.app.canvas.canvasy(event.y)

        if self.app.start_x is None or self.app.start_y is None or abs(end_x - self.app.start_x) < 5 or abs(end_y - self.app.start_y) < 5:
            self.app.canvas.delete("selection_rect")
            self.app.start_x = None
            self.app.start_y = None
            return

        # 1. Calcular rectángulo en coordenadas del documento (des-transformación)
        page = self.app.doc[self.app.page_num]
        matrix = fitz.Matrix(self.app.zoom_level, self.app.zoom_level).preRotate(self.app.rotation)
        inv_matrix = matrix.invert()

        rect_canvas = fitz.Rect(self.app.start_x, self.app.start_y, end_x, end_y)
        rect_doc = rect_canvas.transform(inv_matrix)

        # 2. Extraer texto
        selected_text = page.get_text(clip=rect_doc).strip()
        self.app.selected_word = selected_text

        # 3. Buscar la línea de referencia (usando el motor de búsqueda interno de fitz)
        if self.app.selected_word:
            first_word = self.app.selected_word.split()[0]
            full_page_text = page.get_text("text", sort=True)

            self.app.selected_line_content = None
            for line in full_page_text.splitlines():
                if first_word in line:
                    self.app.selected_line_content = line.strip()
                    break

        # 4. Actualizar variables de la GUI
        self.app.word_var.set(f"✅ Palabra/Valor: {self.app.selected_word}")
        if self.app.selected_line_content:
            self.app.line_ref_var.set(f"🔗 Línea Referencia: {self.app.selected_line_content}")
        else:
            self.app.line_ref_var.set("⚠️ No se pudo determinar la línea de referencia.")

        # 5. Intentar actualizar el editor de reglas si es la pestaña activa
        if self.app.active_data_field and self.app.notebook.tab(self.app.notebook.select(), "text") == 'Editor de Reglas de Extracción':
            # Llamada centralizada a través de la instancia de la App
            self.app.rule_editor_panel._update_rule_editor_with_selection(self.app.selected_word, self.app.selected_line_content)
            
        # 6. Resetear
        self.app.start_x = None
        self.app.start_y = None
        
        # Eliminar el rectángulo (opcional si se quiere mantener visible)
        self.app.canvas.delete("selection_rect")