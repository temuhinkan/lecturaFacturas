import os
import sys
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Tuple, List, Optional, Any, Dict
import io
import sqlite3
import traceback
import importlib.util
import re
import json # Necesario para mostrar reglas como JSON en el listado

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
    print("⚠️ ADVERTENCIA: Visor no disponible. Instale 'PyMuPDF' y 'Pillow'. (pip install PyMuPDF Pillow)")

# --- Importaciones de Módulos (Se asume su existencia) ---
# Se asume que estos módulos (database y utils) existen en el mismo entorno.
try:
    import database 
    import utils 
except ImportError:
    # Mocks para que la GUI funcione sin dependencias externas
    class MockDatabase:
        DB_NAME = 'mock_invoices.db'
        def _clean_numeric_value(self, value):
            if isinstance(value, (int, float)): return value
            value = str(value).replace('.', '').replace(',', '.')
            try: return float(value)
            except: return None
    database = MockDatabase()
    class MockUtils:
        def calculate_total_and_vat(self, base_str, vat_rate):
            try:
                base = float(base_str.replace(',', '.'))
                iva = base * vat_rate
                total = base + iva
                return f"{total:.2f}".replace('.', ','), f"{iva:.2f}".replace('.', ',')
            except:
                return "0,00", "0,00"
    utils = MockUtils()
    print("⚠️ ADVERTENCIA: Módulos 'database' y 'utils' no encontrados. Usando Mocks.")

# --- Importación de Constantes ---
try:
    from config import DEFAULT_VAT_RATE, EXTRACTORS_DIR 
    if not os.path.isdir(EXTRACTORS_DIR):
        os.makedirs(EXTRACTORS_DIR, exist_ok=True)
except ImportError:
    DEFAULT_VAT_RATE = 0.21
    EXTRACTORS_DIR = 'extractors'
    os.makedirs(EXTRACTORS_DIR, exist_ok=True)


# --- MOCKUP DE REGLAS PARA LA GUI (Mejorado para simular BASE_EXTRACTION_MAPPING) ---
MOCK_EXTRACTION_FIELDS = [
    'TIPO', 'FECHA', 'NUM_FACTURA', 'EMISOR', 'CIF_EMISOR', 'CLIENTE', 
    'CIF', 'MODELO', 'MATRICULA', 'IMPORTE', 'BASE', 'IVA', 'TASAS'
]

# Las reglas son ahora una lista de diccionarios, incluso si solo hay una regla.
MOCK_EXTRACTION_MAPPING = {
    'TIPO': [{'type': 'FIXED_VALUE', 'value': 'COMPRA'}],
    'FECHA': [
        {'type': 'VARIABLE', 'ref_text': 'Fecha', 'offset': 0, 'segment': 2},
        {'type': 'VARIABLE', 'ref_text': 'Fecha de venta', 'offset': 1, 'segment': 1},
        {'type': 'FIXED', 'line': 1, 'segment': '2-99'}
    ],
    'NUM_FACTURA': [
        {'type': 'VARIABLE', 'ref_text': 'FACTURA NÚMERO', 'offset': 0, 'segment': 2},
        {'type': 'FIXED', 'line': 6, 'segment': 2}
    ],
    'IMPORTE': [
        {'type': 'VARIABLE', 'ref_text': 'TOTAL A PAGAR', 'offset': 0, 'segment': 2}
    ],
    'EMISOR': [{'type': 'FIXED_VALUE', 'value': 'AutoDocs, S.L.'}],
    'BASE': [], # Campo sin reglas definidas, para simular
}

NEW_RULE_TEMPLATE = {
    'type': 'VARIABLE',
    'ref_text': '',
    'offset': 0,
    'segment': 2,
    'value': ''
}
# ------------------------------------


# --- UTILIDAD: Función de lectura de texto (MOCK/PLACEHOLDER) ---
def _get_document_lines(file_path: str) -> List[str]:
    """
    Lee el texto de un PDF/Imagen (o usa placeholder) para usarlo como referencia en el editor.
    """
    lines = []
    
    # 1. Intento con PyMuPDF (fitz) para PDFs
    if fitz and file_path and file_path.lower().endswith(('.pdf', '.xps', '.epub', '.cbz')):
        try:
            doc = fitz.open(file_path)
            for page in doc:
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


class InvoiceApp:
    
    FORM_FIELDS = [
        ("Path", "file_path", 1),
        ("Extractor", "extractor_name", 2),
        ("Log Data", "log_data", 3), 
        ("Tipo Doc.", "tipo", 4),
        ("Fecha", "fecha", 5),
        ("Nº Factura", "numero_factura", 6),
        ("Emisor", "emisor", 7),
        ("CIF Emisor", "cif_emisor", 8),
        ("Cliente", "cliente", 9),
        ("CIF Cliente", "cif", 10),
        ("Modelo", "modelo", 11),
        ("Matrícula", "matricula", 12),
        ("Base Imponible", "base", 13),
        ("IVA", "iva", 14),
        ("Importe Total", "importe", 15),
        ("Tasas", "tasas", 16)
    ]
    
    def __init__(self, master):
        self.master = master
        master.title("Extractor Generator GUI")

        # 1. PARSEAR ARGUMENTOS DE sys.argv
        self.data = self._parse_argv()
        
        self.file_path = self.data.get('file_path')
        self.log_data = self.data.get('log_data', "No hay log de extracción disponible.")
        self.extractor_name = self.data.get('extractor_name', 'NuevoExtractor') 
        
        # Lógica para determinar el extractor real
        self.extractor_name, self.log_data = self._determine_extractor_and_add_trace(self.log_data, self.extractor_name)
        
        # Estado del visor y variables del editor de reglas
        self.doc: Optional[fitz.Document] = None
        self.page_num = 0
        self.zoom = 1.0
        self.photo_image: Optional[ImageTk.PhotoImage] = None
        self.image_display: Optional[int] = None
        
        # ESTADOS PARA SELECCIÓN DE TEXTO DE ÁREA (NUEVOS)
        self.selected_word: Optional[str] = None # Contiene el texto seleccionado (puede ser un bloque)
        self.selected_line_content: Optional[str] = None # Contiene una referencia (puede ser el mismo texto si es corto)
        self.start_x: Optional[int] = None # Inicio X de la selección de arrastre (coordenada Canvas)
        self.start_y: Optional[int] = None # Inicio Y de la selección de arrastre (coordenada Canvas)
        self.selection_rect_id: Optional[int] = None # ID del rectángulo de selección temporal

        # Variables de la GUI para el texto seleccionado
        self.word_var = tk.StringVar(value="[Ninguna]")
        self.line_ref_var = tk.StringVar(value="[Ninguna]")
        
        self.rule_target_var: Optional[tk.StringVar] = None
        self.rule_vars: Dict[str, tk.StringVar] = {}
        self.extractor_name_label_var: Optional[tk.StringVar] = None 
        # MODIFICADO: Ahora guarda un dict con 'var' (StringVar) y 'widget' (Entry)
        self.form_entries: Dict[str, Dict[str, Any]] = {} 
        
        # NUEVO: Estado para el campo del formulario de datos que se desea editar
        self.active_data_field: Optional[str] = None 
        
        # ESTADOS para el Editor de Reglas
        self.current_field_rules: List[Dict] = []
        self.current_rule_index: Optional[int] = None # Índice de la regla siendo editada (None para nueva regla)
        
        # Inicializar GUI
        self._create_widgets()
        
        # 2. Cargar datos al formulario
        self.load_data_to_form()

        # 3. Cargar documento DESPUÉS de que la GUI esté lista
        if self.file_path and os.path.exists(self.file_path):
             self.master.after_idle(lambda: self._open_document(self.file_path))

    def _determine_extractor_and_add_trace(self, log_data: str, fallback_name: str) -> Tuple[str, str]:
        """Busca el extractor real usado en el log_data y añade la traza de decisión."""
        
        new_extractor_name = fallback_name
        trace_status = "ADVERTENCIA (G. Extractor): El extractor real usado no se pudo determinar a partir del log."
        
        # 1. Búsqueda de Extractor Específico (Ej: extractors.aema_extractor.AemaExtractor -> aema_extractor)
        specific_match = re.search(r'Extractor encontrado en mapeo:\s*extractors\.(\w+_extractor)\.\w+', log_data)
        
        # 2. Búsqueda de Extractor Genérico
        generic_used = 'Using generic extraction function (BaseInvoiceExtractor)' in log_data
        
        used_extractor_path = None

        if specific_match:
            new_extractor_name = specific_match.group(1)
            used_extractor_path = specific_match.group(0).split(':')[-1].strip() 
            trace_status = f"✅ Extractor Específico detectado: {used_extractor_path}"

        elif generic_used:
            new_extractor_name = 'base_invoice_extractor'
            used_extractor_path = 'extractors.base_invoice_extractor.BaseInvoiceExtractor'
            trace_status = "⚠️ Extractor Genérico detectado: BaseInvoiceExtractor"
        
        # 3. Generar traza final
        
        trace_line = "--- INFO (G. Extractor) ---\n"
        trace_line += f"🔍 ESTADO DEL LOG: {trace_status}\n"
        trace_line += f"🛠️ NOMBRE SUGERIDO PARA GENERACIÓN: {new_extractor_name}.py\n"
        trace_line += f"⬅️ NOMBRE RECIBIDO (Fallback/Original): {fallback_name}.py\n"
        trace_line += "---------------------------\n\n"
        
        new_log_data = trace_line + log_data
        
        return new_extractor_name, new_log_data

    
    def _parse_argv(self) -> Dict[str, Any]:
        """Parsea los argumentos de sys.argv en un diccionario."""
        data = {}
        for _, key, index in self.FORM_FIELDS:
            if index < len(sys.argv) and sys.argv[index].strip() != "":
                val = sys.argv[index].strip()
                data[key] = None if val.upper() in ('NONE', 'NULL') else val
            else:
                data[key] = None
        return data

    def _create_widgets(self):
        # 1. Paneles (Dividido Horizontalmente)
        self.paned_window = ttk.PanedWindow(self.master, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True)

        # 2. Panel Izquierdo: Visor
        self.left_frame = ttk.Frame(self.paned_window, padding="10")
        self.paned_window.add(self.left_frame, weight=3)
        self._create_viewer_panel(self.left_frame)

        # 3. Panel Derecho: Notebook (Formulario, Log, Editor de Reglas)
        self.right_frame = ttk.Frame(self.paned_window, padding="10")
        self.paned_window.add(self.right_frame, weight=2)
        
        # Uso de Notebook para las pestañas
        self.notebook = ttk.Notebook(self.right_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Contenedores para las pestañas
        self.tab_form_log = ttk.Frame(self.notebook)
        self.tab_rule_editor = ttk.Frame(self.notebook)
        
        self.notebook.add(self.tab_form_log, text='Datos / Log') 
        self.notebook.add(self.tab_rule_editor, text='Editor de Reglas de Extracción')

        # Variables para la GUI
        self.extractor_name_label_var = tk.StringVar(value=f"{self.extractor_name}.py") 

        # Construir contenido
        self._create_form_log_panel(self.tab_form_log) 
        self._create_rule_editor_panel(self.tab_rule_editor)


    def _set_active_data_field(self, field_key: str, event):
        """Establece el campo del formulario de datos como objetivo de la selección de texto."""
        
        # Restaurar color de fondo del campo anteriormente activo
        if self.active_data_field and self.active_data_field in self.form_entries:
            try:
                # Restaurar estilo (asumiendo que TEntry es el default)
                self.form_entries[self.active_data_field]['widget'].config(style='TEntry')
            except tk.TclError:
                pass # Ignorar si el estilo no se puede cambiar

        self.active_data_field = field_key
        
        # Marcar visualmente el campo activo con un estilo temporal (ttk usa estilos)
        try:
            # Creamos un estilo temporal para resaltar
            highlight_style = 'Highlighted.TEntry'
            style = ttk.Style()
            style.configure(highlight_style, fieldbackground='yellow')
            event.widget.config(style=highlight_style)
        except tk.TclError:
             pass # Si falla el estilo, seguimos sin resaltado

        self.word_var.set(f"¡Campo '{field_key}' ACTIVO! **Arrastre** en el PDF para seleccionar texto.")
        self.line_ref_var.set("") # Limpiar la línea de referencia


    def _create_form_log_panel(self, parent):
        """
        Panel principal que contiene los controles del extractor, el formulario de edición de datos 
        de la factura y el log de extracción.
        """
        
        parent.config(padding="10")

        # 1. Controles de Extracción/Generación
        generator_frame = ttk.LabelFrame(parent, text="Generador de Extractores", padding=10)
        generator_frame.pack(fill=tk.X, pady=5)
        
        # Campo de Extractor Name
        ttk.Label(generator_frame, text="Extractor Activo:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Label(generator_frame, textvariable=self.extractor_name_label_var, anchor='w').grid(row=0, column=1, sticky=tk.EW, padx=5, pady=2)
        
        # Botón principal para lanzar el editor de código
        ttk.Button(generator_frame, 
                   text=f"🛠️ Abrir/Crear {self.extractor_name}.py", 
                   command=self.open_extractor_editor
                   ).grid(row=1, column=0, columnspan=2, sticky=tk.EW, pady=5)
        
        generator_frame.columnconfigure(1, weight=1)

        # 2. Formulario de Datos de Factura (Editable) 
        form_frame = ttk.LabelFrame(parent, text="Datos de Factura (Edición). Haga clic para activar un campo.", padding=10)
        form_frame.pack(fill=tk.X, pady=10)
        
        i = 0
        for label_text, key, _ in self.FORM_FIELDS:
            if key in ['file_path', 'extractor_name', 'log_data']:
                continue
            
            ttk.Label(form_frame, text=f"{label_text}:").grid(row=i, column=0, sticky=tk.W, padx=5, pady=2)
            
            var = tk.StringVar(value=self.data.get(key, ""))
            
            entry = ttk.Entry(form_frame, textvariable=var, width=40)
            entry.grid(row=i, column=1, sticky=tk.EW, padx=5, pady=2)

            # MODIFICADO: Almacenar tanto la variable como el widget
            self.form_entries[key] = {'var': var, 'widget': entry} 
            
            entry.bind('<Return>', lambda event, k=key: self.save_field_and_recalculate(k, event.widget.get()))
            # BINDING: Seleccionar el campo de datos activo al hacer clic
            entry.bind('<Button-1>', lambda event, k=key: self._set_active_data_field(k, event)) 

            i += 1
            
        form_frame.columnconfigure(1, weight=1)

        # 3. Log de Extracción
        log_frame = ttk.LabelFrame(parent, text="Log de Extracción", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.log_text = ScrolledText(log_frame, wrap=tk.WORD, height=10, state=tk.DISABLED, font=('Consolas', 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, self.log_data)
        self.log_text.config(state=tk.DISABLED)


    def load_data_to_form(self):
        """Carga los datos iniciales de self.data al formulario."""
        for key, entry_data in self.form_entries.items():
            var = entry_data['var']
            value = self.data.get(key)
            if value is None:
                value = ""
            
            if key in ['base', 'iva', 'importe', 'tasas'] and str(value).strip() != "":
                try:
                    # Formatear números para la visualización (ej. 100.00 -> 100,00)
                    formatted_value = f"{float(value):.2f}".replace('.', ',')
                    var.set(formatted_value)
                except (ValueError, TypeError):
                    var.set(str(value))
            else:
                 var.set(str(value))


    def save_field_and_recalculate(self, edited_column: str, edited_value: str):
        """
        Guarda el valor editado en la BBDD y recalcula Base/IVA/Importe (incluyendo Tasas).
        """
        if not self.file_path:
            messagebox.showerror("Error", "No se ha cargado una ruta de archivo.")
            return

        # --- 1. Limpieza y Validación ---
        cleaned_edited_value = database._clean_numeric_value(edited_value)
        is_numeric_field = edited_column in ['base', 'iva', 'importe', 'tasas']
        
        if is_numeric_field and edited_value.strip() != "" and cleaned_edited_value is None:
            messagebox.showerror("Error de Formato", f"El valor introducido para '{edited_column}' no es un número válido.")
            return

        try:
            # Determinar el valor final que se guardará en la BBDD
            if is_numeric_field:
                # Si es numérico, usa el float limpio o None si la entrada está vacía
                value_to_save = cleaned_edited_value if edited_value.strip() != "" else None
            else:
                # Si no es numérico, guarda la cadena tal cual
                value_to_save = edited_value

            # ----------------------------------------------------
            # 🔴 PUNTO 1 DE GUARDADO: Guardar el valor que el usuario acaba de editar
            # ----------------------------------------------------
            rows = database.update_invoice_field(
                file_path=self.file_path, 
                field_name=edited_column, 
                new_value=value_to_save
            )

            if rows == 0:
                raise Exception(f"No se pudo guardar el campo '{edited_column}'. (0 filas afectadas en BBDD)")
                
            # ----------------------------------------------------
            # 2. Recalcular
            # ----------------------------------------------------
            
            recalculated_fields = [] # Campos que deben ser guardados después del cálculo

            # Solo si se edita un campo financiero (Base, IVA, Importe, Tasas)
            if edited_column in ['base', 'iva', 'importe', 'tasas']:
                
                # 2.1 Recuperar todos los valores actuales (de la GUI)
                base = database._clean_numeric_value(self.form_entries.get('base', {}).get('var', tk.StringVar()).get()) or 0.0
                iva = database._clean_numeric_value(self.form_entries.get('iva', {}).get('var', tk.StringVar()).get()) or 0.0
                importe = database._clean_numeric_value(self.form_entries.get('importe', {}).get('var', tk.StringVar()).get()) or 0.0
                tasas = database._clean_numeric_value(self.form_entries.get('tasas', {}).get('var', tk.StringVar()).get()) or 0.0
                
                # 2.2 Asignar el nuevo valor limpio al recálculo
                if edited_column == 'base':
                    base = value_to_save if value_to_save is not None else 0.0
                elif edited_column == 'iva':
                    iva = value_to_save if value_to_save is not None else 0.0
                elif edited_column == 'importe':
                    importe = value_to_save if value_to_save is not None else 0.0
                elif edited_column == 'tasas':
                    tasas = value_to_save if value_to_save is not None else 0.0
                
                # 2.3 Lógica de recálculo principal (Base, IVA, Importe)
                
                if edited_column == 'base':
                    # Base -> Calcula IVA y sub-total (Base+IVA) -> Suma Tasas para Importe Total
                    total_sin_tasas_str, vat_str = utils.calculate_total_and_vat(str(base).replace('.', ','), vat_rate=DEFAULT_VAT_RATE)
                    iva = database._clean_numeric_value(vat_str)
                    importe_sin_tasas = database._clean_numeric_value(total_sin_tasas_str)
                    importe = importe_sin_tasas + tasas
                    recalculated_fields = ['iva', 'importe']

                elif edited_column == 'importe':
                    # Importe Total -> Desglosa Base/IVA -> Mantiene Tasas Fijas
                    _importe_sin_tasas = (importe if importe is not None else 0.0) - tasas
                    
                    if DEFAULT_VAT_RATE != -1 and DEFAULT_VAT_RATE != 0: 
                        # Base = Subtotal / (1 + Tasa_IVA)
                        base = _importe_sin_tasas / (1 + DEFAULT_VAT_RATE)
                        iva = _importe_sin_tasas - base
                    else: 
                        # Tasa 0% o -1 (no aplica) -> Subtotal es la Base, IVA=0
                        base = _importe_sin_tasas 
                        iva = 0.0 
                    recalculated_fields = ['base', 'iva']

                elif edited_column == 'iva':
                    _iva = iva if iva is not None else 0.0
                    
                    if DEFAULT_VAT_RATE <= 0:
                        # Si la Tasa es 0% o -1 (no aplica), el IVA debe ser 0.
                        # Si el usuario intentó poner un IVA distinto de cero, emitimos advertencia y lo forzamos a 0.
                        if _iva != 0.0:
                            messagebox.showwarning("Advertencia de Recálculo", 
                                                    f"La tasa de IVA es {DEFAULT_VAT_RATE*100}% (o no aplica). El valor de IVA se guarda como 0.00 y se recalcula el Importe.")
                            _iva = 0.0
                            value_to_save = 0.0 # Valor corregido para la BBDD
                        
                        # Base y el Importe son Base + Tasas (sin IVA)
                        base = base # Mantener la base original
                        importe = base + _iva + tasas
                        recalculated_fields = ['importe'] # Solo Importe necesita recálculo
                        
                    elif DEFAULT_VAT_RATE > 0:
                        # Cálculo estándar: Base = IVA / Tasa
                        base = _iva / DEFAULT_VAT_RATE
                        importe = base + _iva + tasas # Base + IVA + Tasas
                        recalculated_fields = ['base', 'importe']
                    
                    # Actualizamos la variable 'iva' local con el valor final (podría ser 0.0 forzado)
                    iva = _iva 
                
                elif edited_column == 'tasas':
                    # Tasas editadas: Recalcular solo el Importe Total
                    importe = base + iva + tasas
                    recalculated_fields = ['importe']

                # ----------------------------------------------------
                # 🔴 PUNTO 2 DE GUARDADO: Guardar los valores recalculados
                # ----------------------------------------------------
                
                # Guardar los valores calculados en la BBDD
                if 'base' in recalculated_fields:
                    database.update_invoice_field(self.file_path, 'base', base)
                if 'iva' in recalculated_fields or (edited_column == 'iva' and DEFAULT_VAT_RATE <= 0):
                    # Guardar IVA si fue recalculado O si fue forzado a 0.0 al editar el IVA.
                    database.update_invoice_field(self.file_path, 'iva', iva)
                if 'importe' in recalculated_fields:
                    database.update_invoice_field(self.file_path, 'importe', importe)
                
                # El campo 'tasas' ya se guardó en el PUNTO 1 de guardado (el valor editado)
                
                # 3. Actualizar la GUI con los valores finales recalculados
                self.form_entries['base']['var'].set(f"{(base or 0.0):.2f}".replace('.', ','))
                self.form_entries['iva']['var'].set(f"{(iva or 0.0):.2f}".replace('.', ','))
                self.form_entries['importe']['var'].set(f"{(importe or 0.0):.2f}".replace('.', ','))
                self.form_entries['tasas']['var'].set(f"{(tasas or 0.0):.2f}".replace('.', ',')) # CORREGIDO: Usar 'tasas' aquí
                
                # Mensaje final
                if edited_column in ['base', 'iva', 'importe']:
                    messagebox.showinfo("Guardado Exitoso", "Valores Base, IVA e Importe Total recalculados y guardados en BBDD.")
                else:
                    messagebox.showinfo("Guardado Exitoso", "Tasa actualizada. Importe Total recalculado y guardado en BBDD.")
                
            else:
                # 3. Actualizar la GUI solo para el campo editado (no financiero)
                self.form_entries[edited_column]['var'].set(edited_value)
                messagebox.showinfo("Guardado Exitoso", f"Campo '{edited_column}' guardado en BBDD.")

        except Exception as e:
            messagebox.showerror("Error de Guardado/BBDD", f"Error al actualizar la base de datos o al recalcular: {e}\n{traceback.format_exc()}")

        # ... (Resto de las funciones de Editor de Reglas sin cambios) ...

    def _get_current_rule_dict(self) -> Dict[str, Any]:
        """Convierte los valores del formulario actual en un diccionario de regla Python (limpio)."""
        rule_type = self.rule_vars['type'].get()
        rule_dict = {'type': rule_type}

        # Valores brutos de las variables
        ref_text_val = self.rule_vars['ref_text'].get()
        offset_str = self.rule_vars['offset'].get()
        segment_val = self.rule_vars['segment'].get()
        value_val = self.rule_vars['value'].get()

        try:
            offset_val = int(offset_str)
        except ValueError:
            offset_val = 0

        if rule_type == 'FIXED_VALUE':
            if value_val:
                rule_dict['value'] = value_val
        elif rule_type == 'FIXED':
            if offset_val >= 0:
                # 'line' es 1-based, 'offset' en la GUI se usa como 0-based
                rule_dict['line'] = offset_val + 1
            if segment_val:
                rule_dict['segment'] = segment_val
        elif rule_type == 'VARIABLE':
            if ref_text_val:
                rule_dict['ref_text'] = ref_text_val
            if offset_val != 0:
                rule_dict['offset'] = offset_val
            if segment_val:
                rule_dict['segment'] = segment_val
        
        # Limpieza: Eliminar valores por defecto o vacíos que no deben incluirse en la regla
        if 'ref_text' in rule_dict and not rule_dict['ref_text']: del rule_dict['ref_text']
        if 'offset' in rule_dict and rule_dict['offset'] == 0: del rule_dict['offset']
        if 'segment' in rule_dict and not rule_dict['segment']: del rule_dict['segment']
        if 'value' in rule_dict and not rule_dict['value']: del rule_dict['value']
        
        # Eliminar 'line' si la regla no es 'FIXED'
        if rule_type != 'FIXED' and 'line' in rule_dict: 
            # Si se usó 'line' en FIXED, se elimina si se cambia de tipo
            rule_dict.pop('line', None) 
        
        return rule_dict


    def _load_rules_for_selected_field(self, *args):
        """Carga las reglas para el campo seleccionado y actualiza la lista."""
        
        field_key = self.rule_target_var.get()
        self.current_field_rules = MOCK_EXTRACTION_MAPPING.get(field_key, [])
        self.current_rule_index = None # Resetear el índice de la regla activa
        
        # 1. Limpiar y rellenar Listbox
        self.rules_listbox.delete(0, tk.END)
        if not self.current_field_rules:
            self.rules_listbox.insert(tk.END, "⚠️ No hay reglas definidas para este campo. ¡Añade una!")
            # Si no hay reglas, cargar la plantilla de nueva regla
            self.current_rule_index = None
            rule_to_load = NEW_RULE_TEMPLATE
            self.rule_action_label.set("Nueva Regla: Defina los parámetros.")
        else:
            for i, rule in enumerate(self.current_field_rules):
                # Formatear la regla para una visualización compacta
                # Usar json.dumps para formatear y luego limpiar el JSON para que parezca Python dict
                rule_str = json.dumps(rule, ensure_ascii=False).replace('"', "'")
                self.rules_listbox.insert(tk.END, f"Regla {i+1}: {rule_str}")
                
            # Seleccionar la primera regla por defecto y cargarla al editor
            self.rules_listbox.select_set(0)
            self._load_selected_rule_to_form()
            return # Evita doble carga
            
        # 2. Cargar la plantilla de nueva regla (Solo si no hay reglas)
        self._load_selected_rule_to_form()
        
    
    def _load_selected_rule_to_form(self, *args):
        """Carga la regla seleccionada en el Listbox al formulario de edición."""
        try:
            selected_indices = self.rules_listbox.curselection()
            
            if not selected_indices or not self.current_field_rules:
                self.current_rule_index = None
                rule_to_load = NEW_RULE_TEMPLATE
                self.rule_action_label.set("Nueva Regla: Defina los parámetros.")
            else:
                self.current_rule_index = selected_indices[0]
                rule_to_load = self.current_field_rules[self.current_rule_index]
                self.rule_action_label.set(f"Editando Regla {self.current_rule_index + 1}: Modifique parámetros.")


            # 1. Cargar valores al formulario de edición
            for key in self.rule_vars.keys():
                value = rule_to_load.get(key)
                
                # Manejar los casos especiales:
                if key == 'offset' and 'line' in rule_to_load:
                    # Si es FIXED y tiene 'line' (1-based), convertir a 'offset' (0-based) para la GUI
                    value = str(rule_to_load.get('line') - 1)
                elif key == 'type' and value is None:
                    value = NEW_RULE_TEMPLATE['type'] # Default

                # Para cualquier campo que no esté en la regla (ej. 'value' en VARIABLE)
                if value is None:
                    value = '' if key not in ['offset', 'segment'] else '0'


                self.rule_vars[key].set(str(value))
            
            # 2. Regenerar el código para reflejar la regla cargada
            self._generate_rule_code()

        except IndexError:
            self.current_rule_index = None
            self._generate_rule_code()
            pass 

    
    def _add_new_rule(self):
        """Añade la regla actualmente definida en el editor a la lista de reglas del campo activo."""
        field_key = self.rule_target_var.get()
        new_rule = self._get_current_rule_dict()
        
        # Una regla debe tener al menos el 'type' y otro parámetro relevante
        if len(new_rule) <= 1 or (len(new_rule) == 2 and 'offset' in new_rule and new_rule.get('offset', 0) == 0 and new_rule.get('line', 1) == 1): 
            messagebox.showwarning("Advertencia", "La regla está incompleta. Debe definir al menos el tipo y un valor/referencia/segmento.")
            return
            
        # Añadir al Mock Mapping
        if field_key not in MOCK_EXTRACTION_MAPPING:
            MOCK_EXTRACTION_MAPPING[field_key] = []
            
        MOCK_EXTRACTION_MAPPING[field_key].append(new_rule)
        
        messagebox.showinfo("Regla Añadida", f"Nueva regla añadida al campo '{field_key}'.")
        
        # 1. Recargar la lista de reglas para reflejar el cambio
        self._load_rules_for_selected_field()
        
        # 2. Seleccionar la nueva regla en el listbox (último elemento)
        if self.rules_listbox.size() > 0:
            self.rules_listbox.select_clear(0, tk.END)
            self.rules_listbox.select_set(self.rules_listbox.size() - 1)
            self.rules_listbox.event_generate("<<ListboxSelect>>")


    def _create_rule_editor_panel(self, parent):
        """Panel para editar las reglas de extracción."""
        
        parent.config(padding="10")

        # 1. Selección del Campo (Key)
        field_selection_frame = ttk.LabelFrame(parent, text="1. Seleccionar Campo de Extracción", padding=10)
        field_selection_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(field_selection_frame, text="Campo de Destino:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        
        self.rule_target_var = tk.StringVar()
        self.rule_target_var.set(MOCK_EXTRACTION_FIELDS[0])
        
        field_combobox = ttk.Combobox(
            field_selection_frame, 
            textvariable=self.rule_target_var, 
            values=MOCK_EXTRACTION_FIELDS, 
            state='readonly'
        )
        field_combobox.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=2)
        field_selection_frame.columnconfigure(1, weight=1)
        
        # Binding para cargar las reglas al cambiar el campo
        self.rule_target_var.trace_add("write", self._load_rules_for_selected_field)


        # 2. Lista de Reglas Activas (Nuevo Componente)
        list_frame = ttk.LabelFrame(parent, text="2. Reglas Activas para el Campo Seleccionado", padding=10)
        list_frame.pack(fill=tk.X, pady=10)
        
        # Listbox para mostrar las reglas
        self.rules_listbox = tk.Listbox(list_frame, height=5, font=('Consolas', 9))
        self.rules_listbox.pack(fill=tk.X, expand=True)
        self.rules_listbox.bind('<<ListboxSelect>>', self._load_selected_rule_to_form)

        # 3. Definición de la Regla (Formulario)
        rule_definition_frame = ttk.LabelFrame(parent, text="3. Editor de Regla Activa", padding=10)
        rule_definition_frame.pack(fill=tk.X, pady=10)
        
        self.rule_action_label = tk.StringVar(value="Nueva Regla: Defina los parámetros.")
        ttk.Label(rule_definition_frame, textvariable=self.rule_action_label, font=('TkDefaultFont', 10, 'bold')).grid(row=0, column=0, columnspan=2, sticky=tk.EW, pady=5)

        self.rule_vars = {
            'type': tk.StringVar(value=NEW_RULE_TEMPLATE['type']),
            'ref_text': tk.StringVar(value=NEW_RULE_TEMPLATE['ref_text']),
            'offset': tk.StringVar(value=str(NEW_RULE_TEMPLATE['offset'])),
            'segment': tk.StringVar(value=str(NEW_RULE_TEMPLATE['segment'])),
            'value': tk.StringVar(value=NEW_RULE_TEMPLATE['value']),
        }
        
        # Type
        ttk.Label(rule_definition_frame, text="Tipo de Regla ('type'):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        type_combobox = ttk.Combobox(
            rule_definition_frame, 
            textvariable=self.rule_vars['type'], 
            values=['FIXED_VALUE', 'FIXED', 'VARIABLE'], 
            state='readonly'
        )
        type_combobox.grid(row=1, column=1, sticky=tk.EW, padx=5, pady=2)
        
        # Ref Text
        ttk.Label(rule_definition_frame, text="Texto Referencia ('ref_text'):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(rule_definition_frame, textvariable=self.rule_vars['ref_text']).grid(row=2, column=1, sticky=tk.EW, padx=5, pady=2)

        # Offset
        ttk.Label(rule_definition_frame, text="Línea Offset ('offset'/ 'line'-1):").grid(row=3, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(rule_definition_frame, textvariable=self.rule_vars['offset']).grid(row=3, column=1, sticky=tk.EW, padx=5, pady=2)

        # Segment
        ttk.Label(rule_definition_frame, text="Segmento ('segment'):").grid(row=4, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(rule_definition_frame, textvariable=self.rule_vars['segment']).grid(row=4, column=1, sticky=tk.EW, padx=5, pady=2)
        
        # Value (for FIXED_VALUE)
        ttk.Label(rule_definition_frame, text="Valor Fijo ('value'):").grid(row=5, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(rule_definition_frame, textvariable=self.rule_vars['value']).grid(row=5, column=1, sticky=tk.EW, padx=5, pady=2)

        rule_definition_frame.columnconfigure(1, weight=1)

        # 4. Generación de Código y Botones de Acción
        code_output_frame = ttk.LabelFrame(parent, text="4. Regla Generada (Para Copiar en el Extractor)", padding=10)
        code_output_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        self.generated_rule_text = ScrolledText(code_output_frame, wrap=tk.WORD, height=8, font=('Consolas', 9))
        self.generated_rule_text.pack(fill=tk.BOTH, expand=True)
        
        # Frame para los botones de acción
        action_button_frame = ttk.Frame(code_output_frame)
        action_button_frame.pack(fill=tk.X, pady=5)
        
        # Botón para generar el código (siempre presente)
        ttk.Button(action_button_frame, 
                   text="📝 Actualizar Código de Regla", 
                   command=self._generate_rule_code
                   ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))
                   
        # Botón para añadir la regla (NUEVO)
        ttk.Button(action_button_frame, 
                   text="➕ Añadir Regla al Campo", 
                   command=self._add_new_rule
                   ).pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=(5, 0))
        
        # Bindings para regenerar el código al cambiar los campos
        for var in self.rule_vars.values():
             var.trace_add("write", lambda *args: self._generate_rule_code())
        
        # Inicializar la carga de reglas al inicio
        self.master.after_idle(self._load_rules_for_selected_field)
    
    def _generate_rule_code(self):
        """Genera el código Python de la regla de mapeo actual."""
        
        # 1. Obtener el diccionario de la regla (limpio)
        rule_dict = self._get_current_rule_dict()
        
        # 2. Formatear para visualización (con comillas alrededor de strings)
        rule_parts = []
        for k, v in rule_dict.items():
            if isinstance(v, str):
                # Añadir comillas simples, escapando comillas internas
                v_formatted = f"'{v.replace("'", "\\'")}'"
            else:
                v_formatted = str(v)
            rule_parts.append(f"{k}: {v_formatted}")
        
        field_key = self.rule_target_var.get()
        
        if self.current_rule_index is not None:
             header = f"# Código de Regla {self.current_rule_index + 1} para '{field_key}' (REEMPLAZAR EN LISTA)\n"
             instruction = "# Copie y use este código para actualizar la regla existente en su extractor.\n"
        else:
             header = f"# Código para NUEVA Regla para '{field_key}'\n"
             instruction = "# Copie y pegue esta línea en la lista de reglas de '{field_key}' en su extractor.\n"

        generated_code = header
        generated_code += instruction
        generated_code += f"{{ {', '.join(rule_parts)} }}"
        
        self.generated_rule_text.config(state=tk.NORMAL)
        self.generated_rule_text.delete(1.0, tk.END)
        self.generated_rule_text.insert(tk.END, generated_code)
        self.generated_rule_text.config(state=tk.DISABLED)

        
    def open_extractor_editor(self):
        """Crea o abre el archivo del extractor, añadiendo el texto del documento como referencia."""
        
        extractor_filename = f"{self.extractor_name}.py"
        extractor_path = os.path.join(EXTRACTORS_DIR, extractor_filename)
        
        is_new = not os.path.exists(extractor_path)
        
        document_lines = _get_document_lines(self.file_path)
        numbered_lines = [f"Line {i:02}: {line}" for i, line in enumerate(document_lines)]
        lines_commented = "\n# --- LÍNEAS DE REFERENCIA DEL DOCUMENTO --- \n# " + "\n# ".join(numbered_lines) + "\n# -----------------------------------------\n"
        
        if is_new:
            try:
                class_name = "".join(word.capitalize() for word in self.extractor_name.replace('-', '_').split('_'))
                if not class_name.endswith('Extractor'):
                    class_name += 'Extractor'
                
                new_content = f"""
# Extractor generado automáticamente para {extractor_filename}
# Herencia de base_invoice_extractor.py
from base_invoice_extractor import BaseInvoiceExtractor
from typing import Dict, Any, List
import re 
# from utils import extract_and_format_date 

class {class_name}(BaseInvoiceExtractor):
    EMISOR_NAME = "{self.data.get('emisor', 'UNKNOWN')}"
    EMISOR_CIF = "{self.data.get('cif_emisor', 'UNKNOWN')}"
    
    # 1. DEFINA AQUÍ SU MAPEO ESPECÍFICO (Reemplace o extienda el genérico)
    # SPECIFIC_EXTRACTION_MAPPING debe contener una lista de reglas para cada campo.
    
    SPECIFIC_EXTRACTION_MAPPING = {{
        # Ejemplo para TIPO (si se necesita sobrescribir la regla base):
        # 'TIPO': [
        #    {{ 'type': 'FIXED_VALUE', 'value': 'COMPRA' }}
        # ],
        # Ejemplo para FECHA:
        # 'FECHA': [
        #    # {{ 'type': 'VARIABLE', 'ref_text': 'Fecha de emisión', 'offset': 0, 'segment': 2 }}
        # ]
    }}
    
    def extract_data(self, lines: List[str]) -> Dict[str, Any]:
        
        # El mapeo genérico se encarga de aplicar las reglas de SPECIFIC_EXTRACTION_MAPPING si existen.
        extracted_data = super().extract_data(lines)
        
        # 2. AGREGAR LÓGICA DE EXTRACCIÓN ESPECÍFICA AQUÍ (si es necesario un post-proceso):
        
        return extracted_data
        
{lines_commented}
"""
                
                with open(extractor_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                messagebox.showinfo("Extractor Creado", f"Se ha creado el archivo plantilla en:\n{extractor_path}\nAhora se abrirá en su editor.")
                
            except Exception as e:
                messagebox.showerror("Error de Creación", f"No se pudo crear el archivo del extractor '{extractor_path}'. Error: {e}")
                return
        else:
             messagebox.showinfo("Extractor Existente", f"El archivo '{extractor_filename}' ya existe y se abrirá para su edición.")

        try:
            if sys.platform == "win32":
                os.startfile(extractor_path)
            elif sys.platform == "darwin": 
                subprocess.call(('open', extractor_path))
            else: 
                subprocess.call(('xdg-open', extractor_path))
                
        except Exception as e:
            messagebox.showerror("Error al Abrir Editor", f"No se pudo abrir el archivo en el editor por defecto.\nAbra manualmente: {extractor_path}\nError: {e}")

    # --- Funciones de Visor ---
    def _create_viewer_panel(self, parent):
        # Frame contenedor para el Canvas y las barras de desplazamiento
        canvas_container = ttk.Frame(parent)
        # 1. Panel de Selección de Texto (Nuevo)
        selection_frame = ttk.LabelFrame(parent, text="Selección de Texto (Arrastre el ratón para seleccionar)", padding=5)
        selection_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(selection_frame, text="Texto Seleccionado:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Label(selection_frame, textvariable=self.word_var, foreground="blue", font=('TkDefaultFont', 10, 'bold'), wraplength=400, justify=tk.LEFT, anchor='w').grid(row=0, column=1, sticky=tk.EW, padx=5, pady=2)
        
        ttk.Label(selection_frame, text="Referencia:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Label(selection_frame, textvariable=self.line_ref_var, wraplength=400, justify=tk.LEFT, anchor='w').grid(row=1, column=1, sticky=tk.EW, padx=5, pady=2)
        
        # Botones para aplicar a la regla y a los datos (MODIFICADOS)
        button_frame = ttk.Frame(selection_frame)
        button_frame.grid(row=2, column=0, columnspan=2, sticky=tk.EW, pady=5)
        
        # NUEVO BOTÓN para aplicar a campo de Datos activo
        ttk.Button(button_frame, 
                   text="➡️ Aplicar a Campo de Datos Activo", 
                   command=self._apply_to_data_field
                   ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5)) 

        # Botón para aplicar a ref_text del editor de reglas
        ttk.Button(button_frame, 
                   text="✏️ Aplicar a 'ref_text' (Regla)", 
                   command=lambda: self._apply_to_rule_field('ref_text')
                   ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(5, 0))
                   
        # Botón para aplicar a value del editor de reglas
        ttk.Button(button_frame, 
                   text="Aplicar a 'value' (Regla)", 
                   command=lambda: self._apply_to_rule_field('value')
                   ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(5, 0))

        
        selection_frame.columnconfigure(1, weight=1)

        # 2. Canvas y Scrollbars
        canvas_container.pack(fill=tk.BOTH, expand=True, pady=5)
        
        vscrollbar = ttk.Scrollbar(canvas_container, orient=tk.VERTICAL)
        vscrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        hscrollbar = ttk.Scrollbar(canvas_container, orient=tk.HORIZONTAL)
        hscrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        self.canvas = tk.Canvas(
            canvas_container, 
            bg="lightgray", 
            borderwidth=2, 
            relief="sunken",
            yscrollcommand=vscrollbar.set, 
            xscrollcommand=hscrollbar.set  
        )
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        vscrollbar.config(command=self.canvas.yview)
        hscrollbar.config(command=self.canvas.xview)
        
        # NUEVAS VINCULACIONES para selección de área (arrastrar)
        self.canvas.bind('<Button-1>', self._on_selection_start)
        self.canvas.bind('<B1-Motion>', self._on_selection_drag)
        self.canvas.bind('<ButtonRelease-1>', self._on_selection_release) 
        
        self.canvas.bind('<Configure>', self._on_canvas_resize)
        
        # 3. Frame de control (Botones de Zoom/Página)
        control_frame = ttk.Frame(parent)
        control_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(control_frame, text="Zoom In (+)", command=lambda: self.change_zoom(0.1)).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Zoom Out (-)", command=lambda: self.change_zoom(-0.1)).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(control_frame, text="< Página", command=lambda: self.change_page(-1)).pack(side=tk.RIGHT, padx=5)
        self.page_label = ttk.Label(control_frame, text="Página 0 de 0", width=15, anchor='center')
        self.page_label.pack(side=tk.RIGHT, padx=5)
        ttk.Button(control_frame, text="Página >", command=lambda: self.change_page(1)).pack(side=tk.RIGHT, padx=5)

    
    def _apply_to_data_field(self):
        """Aplica la palabra seleccionada al campo del formulario de datos activo y lo guarda."""
        if not self.selected_word:
            messagebox.showwarning("Advertencia", "No se ha seleccionado ningún texto. **Arrastre** en el documento.")
            return

        field_key = self.active_data_field

        if not field_key:
            messagebox.showwarning("Advertencia", "No hay un campo de datos activo. Haga clic en un campo del formulario en la pestaña 'Datos / Log' para activarlo.")
            return
            
        # 1. Aplicar al campo en la GUI
        self.form_entries[field_key]['var'].set(self.selected_word) 
        
        # 2. Guardar y recalcular
        self.save_field_and_recalculate(field_key, self.selected_word)
        
        # 3. Desactivar el campo y restaurar el estilo
        if field_key in self.form_entries:
            try:
                # Restaurar estilo (asumiendo que TEntry es el default)
                self.form_entries[field_key]['widget'].config(style='TEntry')
            except tk.TclError:
                pass # Ignorar si falla el estilo
                
        self.active_data_field = None
        self.word_var.set(f"Campo '{field_key}' actualizado y guardado.")
        
        # Navegar a la pestaña de Datos / Log para confirmación
        self.notebook.select(self.tab_form_log)


    def _apply_to_rule_field(self, target_key: str):
        """Aplica el texto seleccionado a un campo de la regla activa."""
        if not self.selected_word:
            messagebox.showwarning("Advertencia", "No se ha seleccionado ningún texto. **Arrastre** en el documento.")
            return

        if target_key in self.rule_vars:
            # Aplicar la palabra seleccionada
            self.rule_vars[target_key].set(self.selected_word)
            
            # Navegar a la pestaña del editor de reglas
            self.notebook.select(self.tab_rule_editor)
            messagebox.showinfo("Aplicado a Regla", f"Texto '{self.selected_word}' aplicado al campo de regla '{target_key}'.")


    def _on_selection_start(self, event):
        """Marca el punto de inicio de la selección y borra selecciones anteriores."""
        if not self.doc or not VIEWER_AVAILABLE: return
        
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)
        
        # Borrar el rectángulo de selección anterior
        self.canvas.delete("selection_rect")
        self.selection_rect_id = None

    def _on_selection_drag(self, event):
        """Dibuja el rectángulo de selección mientras se arrastra."""
        if self.start_x is None or self.start_y is None:
            return

        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)

        # Borrar el rectángulo anterior (para redibujarlo actualizado)
        self.canvas.delete("selection_rect")
        
        # Dibujar el nuevo rectángulo de selección
        self.selection_rect_id = self.canvas.create_rectangle(
            self.start_x, self.start_y, x, y, 
            outline='red', 
            width=2, 
            dash=(3, 3),
            tags="selection_rect" # Añadir tag para fácil manejo
        )


    def _on_selection_release(self, event):
        """Finaliza la selección, obtiene el texto y actualiza la GUI."""
        if not self.doc or not VIEWER_AVAILABLE:
            return

        end_x = self.canvas.canvasx(event.x)
        end_y = self.canvas.canvasy(event.y)

        if self.start_x is None or self.start_y is None:
             # Si no se ha iniciado bien, salir
             self.canvas.delete("selection_rect")
             return

        # 1. Borrar el rectángulo de selección temporal (si queda alguno)
        self.canvas.delete("selection_rect")
        self.selection_rect_id = None

        # 2. Definir el rectángulo de selección en coordenadas del Canvas (Absolutas)
        rect_canvas = (
            min(self.start_x, end_x), 
            min(self.start_y, end_y), 
            max(self.start_x, end_x), 
            max(self.start_y, end_y)
        )
        
        # 3. Convertir a coordenadas PDF (no escaladas)
        x_start_pdf = rect_canvas[0] / self.zoom
        y_start_pdf = rect_canvas[1] / self.zoom
        x_end_pdf = rect_canvas[2] / self.zoom
        y_end_pdf = rect_canvas[3] / self.zoom

        # Crear el clip de PyMuPDF
        clip_rect = fitz.Rect(x_start_pdf, y_start_pdf, x_end_pdf, y_end_pdf)

        self.start_x = None
        self.start_y = None
        
        try:
            page = self.doc.load_page(self.page_num)
            
            # Usar get_text con el clipping rect para obtener todo el texto dentro del área
            selected_text_raw = page.get_text(clip=clip_rect, sort=True)
            
            # Limpiar y formatear el texto seleccionado (eliminar saltos de línea y espacios extra)
            self.selected_word = " ".join(selected_text_raw.split()).strip()
            
            # 4. Actualizar el estado y la GUI
            if self.selected_word:
                # Mostrar el texto completo
                self.word_var.set(self.selected_word)
                
                # Usar el texto seleccionado como referencia o un resumen si es muy largo
                if len(self.selected_word) > 100:
                    self.selected_line_content = f"Bloque seleccionado ({len(self.selected_word)} caracteres)."
                else:
                    self.selected_line_content = self.selected_word
                    
                self.line_ref_var.set(self.selected_line_content)

            else:
                self.selected_word = None
                self.selected_line_content = None
                
                self.word_var.set("[Ninguna]")
                self.line_ref_var.set("[Ninguna]")
                messagebox.showwarning("Selección", "No se encontró texto en el área seleccionada. Intente de nuevo.")

        except Exception as e:
            messagebox.showerror("Error de Selección", f"Error al intentar seleccionar texto: {e}")
            self.word_var.set("[Error]")
            self.line_ref_var.set("[Error]")

    def _open_document(self, path: str):
        if not VIEWER_AVAILABLE:
            self.page_label.config(text="Visor no disponible.")
            return

        try:
            self.doc = fitz.open(path)
            self.page_num = 0
            self.page_label.config(text=f"Página 1 de {len(self.doc)}")
            self.render_page()
        except Exception as e:
            messagebox.showerror("Error de Documento", f"No se pudo abrir el documento '{path}': {e}")
            self.doc = None
            self.page_label.config(text="Documento no válido")

    def _on_canvas_resize(self, event):
        # Al redimensionar el canvas, no necesitamos recalcular zoom, solo redibujar
        if self.doc:
            self.render_page()

    def render_page(self):
        if not self.doc or not VIEWER_AVAILABLE or not self.doc.page_count > self.page_num:
            self.canvas.delete("all")
            # Restablecer el scrollregion cuando no hay documento
            self.canvas.config(scrollregion=(0, 0, 0, 0)) 
            return

        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        if canvas_width <= 1 or canvas_height <= 1:
            return

        try:
            page = self.doc.load_page(self.page_num)
            
            # La matriz de zoom aplica la escala deseada
            matrix = fitz.Matrix(self.zoom, self.zoom)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            image = Image.open(io.BytesIO(pix.tobytes("ppm")))

            img_width, img_height = image.size
            
            self.photo_image = ImageTk.PhotoImage(image)
            
            self.canvas.delete("all")
            
            # 1. Establecer la región de desplazamiento igual al tamaño de la imagen con zoom.
            self.canvas.config(scrollregion=(0, 0, img_width, img_height))
            
            # 2. Colocar la imagen en la esquina superior izquierda del área de desplazamiento (0, 0).
            self.image_display = self.canvas.create_image(
                0, 0, 
                image=self.photo_image, 
                anchor="nw" # Usar 'nw' (NorthWest/Noroeste) para la esquina superior izquierda
            )

        except Exception as e:
            self.canvas.delete("all")
            self.canvas.config(scrollregion=(0, 0, 0, 0)) # Restablecer scrollregion
            self.canvas.create_text(canvas_width // 2, canvas_height // 2, 
                                    text=f"Error al renderizar página {self.page_num + 1}: {e}", 
                                    fill="red", anchor="center")
            
    def change_zoom(self, delta: float):
        """Ajusta el nivel de zoom y renderiza la página."""
        if self.doc:
            # Asegura que el zoom sea positivo
            self.zoom = max(0.1, self.zoom + delta)
            self.render_page()
            
    def change_page(self, delta: int):
        """Cambia la página del documento y renderiza."""
        if self.doc:
            new_page_num = self.page_num + delta
            if 0 <= new_page_num < len(self.doc):
                self.page_num = new_page_num
                self.page_label.config(text=f"Página {self.page_num + 1} de {len(self.doc)}")
                self.render_page()


# --- Ejecución de la Aplicación ---
if __name__ == '__main__':
    EXPECTED_ARGS = 17 
    if len(sys.argv) < EXPECTED_ARGS:
         print(f"ADVERTENCIA: Se esperaban {EXPECTED_ARGS-1} argumentos de datos. Usando placeholders para la prueba.")
         while len(sys.argv) < EXPECTED_ARGS:
             sys.argv.append("")
         
         if not sys.argv[1]:
              sys.argv[1] = "placeholder_factura.pdf" 
         if not sys.argv[2]:
              sys.argv[2] = "placeholder_extractor" 
         if not sys.argv[3]:
              sys.argv[3] = "DEBUG FLOW: Procesando archivo. Extractor encontrado en mapeo: extractors.aema_extractor.AemaExtractor. Extracción exitosa." 

    root = tk.Tk()
    # Inicializar el estilo para poder usar 'TEntry' si es necesario
    style = ttk.Style()
    style.configure('TEntry', fieldbackground='white')
    
    app = InvoiceApp(root)
    root.mainloop()