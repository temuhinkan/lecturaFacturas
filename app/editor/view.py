import tkinter as tk
from tkinter import ttk, scrolledtext

class EditorView(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Estación de Trabajo de Facturas - Editor Profesional")
        self.geometry("1500x950")
        
        self._build_layout()

    def _build_layout(self):
        # --- Barra Superior (Toolbar) ---
        self.toolbar = ttk.Frame(self, padding=5)
        self.toolbar.pack(side=tk.TOP, fill=tk.X)
        
        # 1. Controles de navegación (Omitidos los detalles para brevedad, mantener igual)
        self.btn_prev = ttk.Button(self.toolbar, text="◀ Ant.", width=5)
        self.btn_prev.pack(side=tk.LEFT, padx=2)
        self.lbl_page = ttk.Label(self.toolbar, text="Pág: 1/1", font=('Arial', 10, 'bold'))
        self.lbl_page.pack(side=tk.LEFT, padx=5)
        self.btn_next = ttk.Button(self.toolbar, text="Sig. ▶", width=5)
        self.btn_next.pack(side=tk.LEFT, padx=2)
        
        ttk.Separator(self.toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        self.btn_zoom_in = ttk.Button(self.toolbar, text="🔍+", width=4)
        self.btn_zoom_in.pack(side=tk.LEFT)
        self.btn_zoom_out = ttk.Button(self.toolbar, text="🔍-", width=4)
        self.btn_zoom_out.pack(side=tk.LEFT)
        self.btn_rotate = ttk.Button(self.toolbar, text="🔄 Rotar", width=8)
        self.btn_rotate.pack(side=tk.LEFT, padx=5)

        # Selector de Extractor (Lado Derecho)
        self.selector_frame = ttk.Frame(self.toolbar)
        self.selector_frame.pack(side=tk.RIGHT, padx=10)
        self.combo_extractor = ttk.Combobox(self.selector_frame, state="readonly", width=22)
        self.combo_extractor.pack(side=tk.LEFT, padx=5)
        self.btn_reprocesar = ttk.Button(self.selector_frame, text="⚡ Re-procesar", width=12)
        self.btn_reprocesar.pack(side=tk.LEFT, padx=5)
        self.lbl_extractor = ttk.Label(self.toolbar, text="Extractor: --", foreground="blue", font=('Arial', 9, 'italic'))
        self.lbl_extractor.pack(side=tk.RIGHT, padx=15)

        # --- Contenedor Principal ---
        self.main_container = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.main_container.pack(fill=tk.BOTH, expand=True)

        # 1. PANEL IZQUIERDO: VISOR DE PDF
        self.viewer_frame = ttk.Frame(self.main_container)
        self.main_container.add(self.viewer_frame, weight=4)

        # Crear barras de desplazamiento
        self.v_scroll = ttk.Scrollbar(self.viewer_frame, orient=tk.VERTICAL)
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.h_scroll = ttk.Scrollbar(self.viewer_frame, orient=tk.HORIZONTAL)
        self.h_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        # Vincular Canvas con Scrolls (SOLO UNA VEZ)
        self.canvas = tk.Canvas(
            self.viewer_frame, 
            bg="gray70",
            highlightthickness=0,
            xscrollcommand=self.h_scroll.set,   # El canvas le dice al scroll dónde está
            yscrollcommand=self.v_scroll.set
        )
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Configurar los comandos de los scrollbars (CRÍTICO: El scroll mueve al canvas)
        self.v_scroll.config(command=self.canvas.yview)
        self.h_scroll.config(command=self.canvas.xview)

        # 2. PANEL DERECHO: DATOS Y LOGS
        self.right_panel = ttk.Frame(self.main_container)
        self.main_container.add(self.right_panel, weight=1)

        # --- PRIMERO: CREAR EL CONTENEDOR DE DATOS ---
        self.data_panel = ttk.LabelFrame(self.right_panel, text=" Datos de la Factura ", padding=10)
        self.data_panel.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # --- SEGUNDO: AHORA SÍ PODEMOS CREAR EL CHECK_FRAME DENTRO DE DATA_PANEL ---
        self.check_frame = ttk.Frame(self.data_panel)
        self.check_frame.pack(fill=tk.X, pady=5)

        self.var_auto_aprender = tk.BooleanVar(value=True)
        self.chk_aprender = ttk.Checkbutton(
            self.check_frame, 
            text="Auto-aprender correcciones", 
            variable=self.var_auto_aprender
        )
        self.chk_aprender.pack(side=tk.LEFT)

        # Contenedor para los campos (Entry) que inyecta el controlador
        self.fields_container = ttk.Frame(self.data_panel)
        self.fields_container.pack(fill=tk.BOTH, expand=True)

        # Sub-panel inferior: Log
        self.log_panel = ttk.LabelFrame(self.right_panel, text=" Log de Proceso / Debug ", padding=5)
        self.log_panel.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
        self.txt_log = scrolledtext.ScrolledText(self.log_panel, height=12, font=('Consolas', 9), bg="#f8f9fa")
        self.txt_log.pack(fill=tk.BOTH, expand=True)

        # Menú Contextual
        self.context_menu = tk.Menu(self, tearoff=0)