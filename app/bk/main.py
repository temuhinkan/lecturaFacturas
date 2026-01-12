# main.py

import os
import sys
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Tuple, List, Optional, Any, Dict
import re

# Importaciones de los nuevos módulos de panel
from viewer_panel import DocumentViewer
from data_form_panel import DataFormPanel
from rule_editor_panel import RuleEditorPanel
from document_utils import get_document_lines # Importamos la función auxiliar

# Importaciones de módulos existentes (asumidos)
import database
import utils
import subprocess 
import rule_suggester # Mantenido aquí para consistencia
from extractors.base_invoice_extractor import BaseInvoiceExtractor

# Importaciones de dependencias del visor
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

# Importaciones de Constantes (asumidas)
try:
    from config import DEFAULT_VAT_RATE, EXTRACTORS_DIR 
except ImportError:
    DEFAULT_VAT_RATE = 0.21
    EXTRACTORS_DIR = 'extractors'

DEFAULT_EXTRACTOR_NAME = 'base'

# ----------------------------------------------------------------------
# CONSTANTES DE FORMULARIO (Mantenidas aquí como parte de la App principal)
# ----------------------------------------------------------------------
# (Etiqueta, Clave de BBDD, Índice en sys.argv)
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
    ("Concepto", "concepto", 13),
    ("Base Imponible", "base", 14),
    ("IVA", "iva", 15),
    ("Importe Total", "importe", 16),
    ("Tasas", "tasas", 17)
]
# ----------------------------------------------------------------------


class InvoiceApp:
    
    def __init__(self, master):
        self.master = master
        master.title("Extractor Generator GUI")
        
        # --- ESTADO COMPARTIDO (MANTENIDO AQUÍ) ---
        self.FORM_FIELDS = FORM_FIELDS # Referencia a la constante
        self.doc: Optional[fitz.Document] = None 
        self.page_num = 0
        self.rotation = 0  
        self.zoom_level = 1.0
        self.photo_image: Optional[ImageTk.PhotoImage] = None 
        self.image_display: Optional[int] = None
        
        # ESTADOS PARA SELECCIÓN DE TEXTO DE ÁREA
        self.selected_word: Optional[str] = None 
        self.selected_line_content: Optional[str] = None 
        self.start_x: Optional[int] = None 
        self.start_y: Optional[int] = None 
        self.selection_rect_id: Optional[int] = None 
        
        # Variables de la GUI (Compartidas)
        self.word_var = tk.StringVar(value="[Ninguna]")
        self.line_ref_var = tk.StringVar(value="[Ninguna]")
        self.rule_target_var: Optional[tk.StringVar] = None
        self.rule_vars: Dict[str, tk.StringVar] = {}
        self.extractor_name_label_var: Optional[tk.StringVar] = None 
        self.form_entries: Dict[str, Dict[str, Any]] = {} 
        self.active_data_field: Optional[str] = None 
        self.current_field_rules: List[Dict] = []
        self.current_rule_index: Optional[int] = None 
        self.current_extractor_mapping: Dict[str, List[Dict[str, Any]]] = {}
        
        # Variables de Navegación
        self.invoice_file_paths: List[str] = self._load_invoice_paths() 
        self.current_invoice_index: int = 0 
        self.invoice_position_label: Optional[ttk.Label] = None
        self.log_text: Optional[tk.Text] = None # Referencia al widget para actualizar
        
        # ----------------------------------------------------
        # INICIALIZACIÓN Y CARGA DE DATOS (CRÍTICO)
        # ----------------------------------------------------
        self.data = self._parse_argv()
        initial_file_path = self.data.get('file_path')
        self.log_data = self.data.get('log_data', "No hay log de extracción disponible.")
        self.extractor_name = self.data.get('extractor_name', 'NuevoExtractor')

        # Lógica de carga de datos inicial y navegación (MOVIDA AQUÍ)
        if self.invoice_file_paths and initial_file_path:
            try:
                normalized_initial_path = initial_file_path.replace('\\', '/')
                self.current_invoice_index = self.invoice_file_paths.index(normalized_initial_path)
                self.data = self._load_invoice_data_from_db(normalized_initial_path)
            except ValueError:
                self.data = self._load_invoice_data_from_db(self.invoice_file_paths[0])
                self.file_path = self.invoice_file_paths[0]
                self.current_invoice_index = 0
        elif self.invoice_file_paths:
            self.data = self._load_invoice_data_from_db(self.invoice_file_paths[0])
            self.file_path = self.invoice_file_paths[0]
            self.current_invoice_index = 0
        
        self.file_path = self.data.get('file_path', initial_file_path)
        
        self.extractor_name, self.log_data = self._determine_extractor_and_add_trace(
            self.data.get('log_data', self.log_data), 
            self.data.get('extractor_name', self.extractor_name)
        )
        
        # Cargar las reglas del extractor activo
        self.current_extractor_mapping = self._load_current_extractor_rules()
        
        # ----------------------------------------------------
        # CONSTRUCCIÓN DE LA GUI (DELEGA A LOS PANELES)
        # ----------------------------------------------------
        master.state('zoomed')
        self._create_widgets()
        
        # 2. Cargar datos al formulario (Llamada al método del panel)
        self.form_panel.load_data_to_form()

        # 3. Carga inicial del documento
        self.master.after_idle(lambda: self.viewer_panel.initial_load()) 

    # ----------------------------------------------------
    # MÉTODOS DE LA CLASE PRINCIPAL (LOGIC/NAVEGACIÓN/PARSING)
    # ----------------------------------------------------

    def _determine_extractor_and_add_trace(self, log_data: str, current_extractor_name: str) -> Tuple[str, str]:
        # *********** Mover lógica completa de _determine_extractor_and_add_trace aquí ***********
        # (El código es largo y queda en la clase principal)
        new_extractor_name = None
        extractor_match = re.search(r'extractors\.(\w+)(?:\.|\s|$)', log_data)
        
        if extractor_match:
            new_extractor_name = extractor_match.group(1) 
            if new_extractor_name.endswith('_extractor'):
                cleaned_name = new_extractor_name.rsplit('_extractor', 1)[0]
                new_extractor_name = cleaned_name
            return new_extractor_name, log_data
        
        final_name = DEFAULT_EXTRACTOR_NAME 
        return final_name, log_data

    def _parse_argv(self) -> Dict[str, Any]:
        # *********** Mover lógica completa de _parse_argv aquí ***********
        data = {}
        for _, key, index in self.FORM_FIELDS:
            if index < len(sys.argv) and sys.argv[index].strip() != "":
                val = sys.argv[index].strip()
                data[key] = None if val.upper() in ('NONE', 'NULL') else val
            else:
                data[key] = None
        return data

    def _load_invoice_paths(self) -> List[str]:
        # *********** Mover lógica completa de _load_invoice_paths aquí ***********
        try:
            # Se asume que database.fetch_all_invoices() está disponible
            all_invoices = database.fetch_all_invoices() 
            return [inv['path'] for inv in all_invoices if inv.get('path')]
        except Exception:
            return []
    
    def _load_invoice_data_from_db(self, file_path: str) -> Dict[str, Any]:
        # *********** Mover lógica completa de _load_invoice_data_from_db aquí ***********
        try:
            data = database.get_invoice_data(file_path)
            if data: return data
        except Exception:
            pass
            
        # Placeholder si el registro no se encuentra o hay error
        placeholder_data = { 
            'file_path': file_path, 
            'extractor_name': 'placeholder_extractor', 
            'log_data': f"ADVERTENCIA: Factura no encontrada en la BBDD con ruta: {file_path}", 
            **{k: "" for _, k, _ in self.FORM_FIELDS} 
        }
        return placeholder_data

    def load_invoice(self, index_delta: int = 0):
        # *********** Mover lógica completa de load_invoice aquí ***********
        if not self.invoice_file_paths:
            messagebox.showinfo("Navegación", "No hay facturas cargadas en la BBDD para navegar.")
            return 
        
        new_index = self.current_invoice_index + index_delta
        
        if not (0 <= new_index < len(self.invoice_file_paths)):
            messagebox.showinfo("Navegación", "Has llegado al límite de facturas en esta dirección.")
            return

        self.current_invoice_index = new_index
        new_file_path = self.invoice_file_paths[self.current_invoice_index]

        # 1. Cargar datos desde BBDD para el nuevo path
        self.data = self._load_invoice_data_from_db(new_file_path)
        self.file_path = new_file_path
        
        # 2. Re-determinar extractor y log
        self.extractor_name, self.log_data = self._determine_extractor_and_add_trace(
            self.data.get('log_data', self.log_data), 
            self.data.get('extractor_name', self.extractor_name)
        )
        
        # 3. Recargar reglas y actualizar GUI
        self.current_extractor_mapping = self._load_current_extractor_rules()
        self.form_panel.load_data_to_form()
        self.viewer_panel._open_document(self.file_path)
        self.rule_editor_panel.update_rule_editor_after_load()

    def _load_current_extractor_rules(self) -> Dict[str, List[Dict[str, Any]]]:
        # *********** Mover lógica completa de _load_current_extractor_rules aquí ***********
        # (Se llama desde __init__ y load_invoice. Es mejor que esté aquí)
        result = {}
        try:
            if hasattr(database, 'get_extractor_configurations_by_name'):
                result = database.get_extractor_configurations_by_name(self.extractor_name)
        except Exception:
            pass
        return result

    def _create_widgets(self):
        # 1. Paneles (Dividido Horizontalmente)
        self.paned_window = ttk.PanedWindow(self.master, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True)

        # 2. Panel Izquierdo: Visor
        self.left_frame = ttk.Frame(self.paned_window, padding="10")
        self.paned_window.add(self.left_frame, weight=3)
        
        # DELEGAR la creación al panel
        self.viewer_panel = DocumentViewer(self.left_frame, self)

        # 3. Panel Derecho: Notebook (Formulario, Log, Editor de Reglas)
        self.right_frame = ttk.Frame(self.paned_window, padding="10")
        self.paned_window.add(self.right_frame, weight=2)
        
        self.notebook = ttk.Notebook(self.right_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.tab_form_log = ttk.Frame(self.notebook)
        self.tab_rule_editor = ttk.Frame(self.notebook)
        
        self.notebook.add(self.tab_form_log, text='Datos / Log') 
        self.notebook.add(self.tab_rule_editor, text='Editor de Reglas de Extracción')
        
        self.extractor_name_label_var = tk.StringVar(value=f"{self.extractor_name}.py") 

        # DELEGAR la creación de contenido
        self.form_panel = DataFormPanel(self.tab_form_log, self) 
        self.rule_editor_panel = RuleEditorPanel(self.tab_rule_editor, self)
        
    def open_extractor_editor(self):
        # *********** Mover lógica completa de open_extractor_editor aquí ***********
        extractor_path = os.path.join(EXTRACTORS_DIR, f"{self.extractor_name}.py")
        
        # 1. Si el fichero existe, abrirlo
        if os.path.exists(extractor_path):
            try:
                subprocess.Popen(['notepad', extractor_path]) # Usar un editor simple
            except FileNotFoundError:
                messagebox.showerror("Error", "No se pudo encontrar el editor 'notepad'. Abre el archivo manualmente.")
        
        # 2. Si no existe, crear una plantilla (Lógica de _create_extractor_template)
        else:
            # Aquí iría toda la lógica para crear la plantilla.
            # Se ha mantenido en main.py para acceder fácilmente a self.data
            template = """
from extractors.base_invoice_extractor import BaseInvoiceExtractor

class {class_name}(BaseInvoiceExtractor):
    # Nombre del extractor (opcional, si es diferente al nombre del fichero)
    extractor_name = '{class_name}'

    # Definir el mapeo de extracción específico
    SPECIFIC_EXTRACTION_MAPPING = {{
        # 'CAMPO': [
        #     {{'type': 'VARIABLE', 'ref_text': 'Número de factura', 'offset': 0, 'segment': 2}},
        # ],
    }}

    def extract_data(self, lines: List[str]) -> Dict[str, Optional[str]]:
        # 1. Intentar extraer con las reglas específicas de este extractor
        extracted_data = super().extract_data(lines)
        
        # 2. AGREGAR LÓGICA DE EXTRACCIÓN ESPECÍFICA AQUÍ (si es necesario un post-proceso):
        # Ejemplo: Si se extrajo 'IMPORTE', recalcular 'BASE' y 'IVA'.

        return extracted_data
"""
            # Nombre de clase (CamelCase)
            class_name = self.extractor_name.replace('_', ' ').title().replace(' ', '') + 'Extractor'
            
            # Comentar las líneas del documento para el ejemplo
            lines = get_document_lines(self.file_path)
            lines_commented = "\n# ".join(lines)
            
            new_content = template.format(
                class_name=class_name
            ) + f"\n\n# --- LÍNEAS DE EJEMPLO DEL DOCUMENTO (Para depuración) ---\n# {lines_commented}"
            
            try:
                with open(extractor_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                messagebox.showinfo("Extractor Creado", f"Se ha creado el archivo plantilla en:\n{extractor_path}\nAhora se abrirá en su editor.")
                subprocess.Popen(['notepad', extractor_path])
            except Exception as e:
                messagebox.showerror("Error de Creación", f"No se pudo crear el archivo del extractor '{extractor_path}'. Error: {e}")


if __name__ == '__main__':
    # ----------------------------------------------------
    # LÓGICA DE ARGUMENTOS (MANTENIDA AQUÍ)
    # ----------------------------------------------------
    EXPECTED_ARGS = 17 
    if len(sys.argv) < EXPECTED_ARGS:
         while len(sys.argv) < EXPECTED_ARGS:
             sys.argv.append("")
         
         if not sys.argv[1]:
              sys.argv[1] = "placeholder_factura.pdf" 
         if not sys.argv[2]:
              sys.argv[2] = "placeholder_extractor" 
         if not sys.argv[3]:
              sys.argv[3] = "ADVERTENCIA: Usando datos de prueba (Mockup)."
    
    # ----------------------------------------------------
    # INICIO DE LA APLICACIÓN
    # ----------------------------------------------------
    root = tk.Tk()
    app = InvoiceApp(root)
    root.mainloop()