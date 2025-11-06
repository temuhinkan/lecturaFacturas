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
import database 
import utils 

# --- Importación de Constantes ---
try:
    from config import DEFAULT_VAT_RATE, EXTRACTORS_DIR 
    if not os.path.isdir(EXTRACTORS_DIR):
        os.makedirs(EXTRACTORS_DIR, exist_ok=True)
except ImportError:
    DEFAULT_VAT_RATE = 0.21
    EXTRACTORS_DIR = 'extractors'
    os.makedirs(EXTRACTORS_DIR, exist_ok=True)


# --- MOCKUP DE REGLAS PARA LA GUI ---
MOCK_EXTRACTION_FIELDS = [
    'TIPO', 'FECHA', 'NUM_FACTURA', 'EMISOR', 'CIF_EMISOR', 'CLIENTE', 
    'CIF', 'MODELO', 'MATRICULA', 'IMPORTE', 'BASE', 'IVA', 'TASAS'
]
MOCK_RULE_TEMPLATE = {
    'type': 'VARIABLE',
    'ref_text': 'FACTURA NÚMERO',
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
        
        self.rule_target_var: Optional[tk.StringVar] = None
        self.rule_vars: Dict[str, tk.StringVar] = {}
        self.extractor_name_label_var: Optional[tk.StringVar] = None 
        
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

        # Construir contenido
        self.extractor_name_label_var = tk.StringVar(value=f"{self.extractor_name}.py") # Inicializar aquí
        self._create_form_log_panel(self.tab_form_log) 
        self._create_rule_editor_panel(self.tab_rule_editor)


    def _create_form_log_panel(self, parent):
        
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
        form_frame = ttk.LabelFrame(parent, text="Datos de Factura (Edición)", padding=10)
        form_frame.pack(fill=tk.X, pady=10)
        
        self.form_entries: Dict[str, tk.StringVar] = {} 
        i = 0
        for label_text, key, _ in self.FORM_FIELDS:
            if key in ['file_path', 'extractor_name', 'log_data']:
                continue
            
            ttk.Label(form_frame, text=f"{label_text}:").grid(row=i, column=0, sticky=tk.W, padx=5, pady=2)
            
            var = tk.StringVar(value=self.data.get(key, ""))
            self.form_entries[key] = var
            
            entry = ttk.Entry(form_frame, textvariable=var, width=40)
            entry.grid(row=i, column=1, sticky=tk.EW, padx=5, pady=2)
            
            entry.bind('<Return>', lambda event, k=key: self.save_field_and_recalculate(k, event.widget.get()))
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

    def _create_rule_editor_panel(self, parent):
        """Panel para editar las reglas de extracción."""
        
        parent.config(padding="10")

        # 1. INFO y Selección del Campo
        info_frame = ttk.Frame(parent)
        info_frame.pack(fill=tk.X, pady=5)
        ttk.Label(info_frame, text="Define una regla de mapeo para el extractor activo:").pack(fill=tk.X)
        ttk.Label(info_frame, textvariable=self.extractor_name_label_var, font=('TkDefaultFont', 10, 'bold'), foreground='blue').pack(fill=tk.X)


        field_selection_frame = ttk.LabelFrame(parent, text="1. Seleccionar Campo (Key)", padding=10)
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


        # 2. Definición de la Regla (Formulario)
        rule_definition_frame = ttk.LabelFrame(parent, text="2. Definir Parámetros de la Regla", padding=10)
        rule_definition_frame.pack(fill=tk.X, pady=10)
        
        self.rule_vars = {
            'type': tk.StringVar(value=MOCK_RULE_TEMPLATE['type']),
            'ref_text': tk.StringVar(value=MOCK_RULE_TEMPLATE['ref_text']),
            'offset': tk.StringVar(value=str(MOCK_RULE_TEMPLATE['offset'])),
            'segment': tk.StringVar(value=str(MOCK_RULE_TEMPLATE['segment'])),
            'value': tk.StringVar(value=MOCK_RULE_TEMPLATE['value']),
        }
        
        # Type
        ttk.Label(rule_definition_frame, text="Tipo de Regla ('type'):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        type_combobox = ttk.Combobox(
            rule_definition_frame, 
            textvariable=self.rule_vars['type'], 
            values=['FIXED_VALUE', 'FIXED', 'VARIABLE'], 
            state='readonly'
        )
        type_combobox.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=2)
        
        # Ref Text
        ttk.Label(rule_definition_frame, text="Texto Referencia ('ref_text'):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(rule_definition_frame, textvariable=self.rule_vars['ref_text']).grid(row=1, column=1, sticky=tk.EW, padx=5, pady=2)

        # Offset
        ttk.Label(rule_definition_frame, text="Línea Offset ('offset'):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(rule_definition_frame, textvariable=self.rule_vars['offset']).grid(row=2, column=1, sticky=tk.EW, padx=5, pady=2)

        # Segment
        ttk.Label(rule_definition_frame, text="Segmento ('segment'):").grid(row=3, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(rule_definition_frame, textvariable=self.rule_vars['segment']).grid(row=3, column=1, sticky=tk.EW, padx=5, pady=2)
        
        # Value (for FIXED_VALUE)
        ttk.Label(rule_definition_frame, text="Valor Fijo ('value'):").grid(row=4, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(rule_definition_frame, textvariable=self.rule_vars['value']).grid(row=4, column=1, sticky=tk.EW, padx=5, pady=2)

        rule_definition_frame.columnconfigure(1, weight=1)

        # 3. Generación de Código
        code_output_frame = ttk.LabelFrame(parent, text="3. Regla Generada (Para Copiar en el Extractor)", padding=10)
        code_output_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        self.generated_rule_text = ScrolledText(code_output_frame, wrap=tk.WORD, height=8, font=('Consolas', 9))
        self.generated_rule_text.pack(fill=tk.BOTH, expand=True)
        
        # Botón para generar la regla
        ttk.Button(code_output_frame, 
                   text="📝 Generar Código de Regla", 
                   command=self._generate_rule_code
                   ).pack(fill=tk.X, pady=5)
        
        # Bindings para regenerar el código al cambiar los campos
        self.rule_target_var.trace_add("write", lambda *args: self._generate_rule_code())
        for var in self.rule_vars.values():
             var.trace_add("write", lambda *args: self._generate_rule_code())
        
        # Inicializar el código de la regla
        self._generate_rule_code() 
    
    def _generate_rule_code(self):
        """Genera el código Python de la regla de mapeo actual."""
        
        rule_type = self.rule_vars['type'].get()
        rule_data = {'type': f"'{rule_type}'"}
        
        if rule_type == 'FIXED_VALUE':
            # Solo necesita 'value'
            rule_data['value'] = f"'{self.rule_vars['value'].get().replace("'", "\\'")}'"
        elif rule_type == 'FIXED':
            # Necesita 'line' (offset+1 si offset es un número) y 'segment'
            try:
                # FIXED trabaja con líneas 1-based, el offset en la GUI es más intuitivo
                line_val = int(self.rule_vars['offset'].get()) + 1 
            except ValueError:
                line_val = 1 # Fallback
                
            rule_data['line'] = line_val
            segment_val = self.rule_vars['segment'].get()
            rule_data['segment'] = f"'{segment_val}'" if segment_val.replace('-', '').isalnum() else segment_val

        elif rule_type == 'VARIABLE':
            # Necesita 'ref_text', 'offset', 'segment'
            rule_data['ref_text'] = f"'{self.rule_vars['ref_text'].get().replace("'", "\\'")}'"
            try:
                rule_data['offset'] = int(self.rule_vars['offset'].get())
            except ValueError:
                rule_data['offset'] = 0 
                
            segment_val = self.rule_vars['segment'].get()
            rule_data['segment'] = f"'{segment_val}'" if segment_val.replace('-', '').isalnum() else segment_val
            
        
        # Formatear el diccionario como cadena de Python
        rule_parts = [f"{k}: {v}" for k, v in rule_data.items()]
        
        field_key = self.rule_target_var.get()
        
        # Añadir las reglas a la lista del campo
        generated_code = f"# Regla generada para '{field_key}'\n"
        generated_code += f"# Copie la línea de abajo y péguela en la lista de reglas de '{field_key}' en su extractor.\n"
        generated_code += f"{{ {', '.join(rule_parts)} }}"
        
        self.generated_rule_text.config(state=tk.NORMAL)
        self.generated_rule_text.delete(1.0, tk.END)
        self.generated_rule_text.insert(tk.END, generated_code)
        self.generated_rule_text.config(state=tk.DISABLED)


    def load_data_to_form(self):
        """Carga los datos iniciales de self.data al formulario."""
        for key, var in self.form_entries.items():
            value = self.data.get(key)
            if value is None:
                value = ""
            
            if key in ['base', 'iva', 'importe', 'tasas'] and str(value).strip() != "":
                try:
                    formatted_value = f"{float(value):.2f}".replace('.', ',')
                    var.set(formatted_value)
                except (ValueError, TypeError):
                    var.set(str(value))
            else:
                 var.set(str(value))


    def save_field_and_recalculate(self, edited_column: str, edited_value: str):
        """Guarda el valor editado en la BBDD y recalcula Base/IVA/Importe."""
        if not self.file_path:
            messagebox.showerror("Error", "No se ha cargado una ruta de archivo.")
            return

        # 1. Limpiar el valor y validar
        cleaned_edited_value = database._clean_numeric_value(edited_value)
        is_numeric_field = edited_column in ['base', 'iva', 'importe', 'tasas']
        
        if is_numeric_field and edited_value.strip() != "" and cleaned_edited_value is None:
            messagebox.showerror("Error de Formato", f"El valor introducido para '{edited_column}' no es un número válido.")
            return

        conn = sqlite3.connect(database.DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Obtener valores actuales
        cursor.execute("SELECT base, iva, importe FROM processed_invoices WHERE path = ?", (self.file_path,))
        row = cursor.fetchone()
        
        base = row['base'] if row and row['base'] is not None else 0.0
        iva = row['iva'] if row and row['iva'] is not None else 0.0
        importe = row['importe'] if row and row['importe'] is not None else 0.0
        
        # Sobreescribir el valor editado
        if edited_column == 'base':
            base = cleaned_edited_value if cleaned_edited_value is not None else 0.0
        elif edited_column == 'iva':
            iva = cleaned_edited_value if cleaned_edited_value is not None else 0.0
        elif edited_column == 'importe':
            importe = cleaned_edited_value if cleaned_edited_value is not None else 0.0
        
        try:
            # 2. Recalcular y actualizar
            if edited_column == 'base':
                # Asumiendo que utils.calculate_total_and_vat está disponible
                total_str, vat_str = utils.calculate_total_and_vat(str(base).replace('.', ','), vat_rate=DEFAULT_VAT_RATE)
                importe = database._clean_numeric_value(total_str) 
                iva = database._clean_numeric_value(vat_str)       

            elif edited_column == 'importe':
                _importe = importe if importe is not None else 0.0
                base = _importe / (1 + DEFAULT_VAT_RATE)
                iva = _importe - base
            
            elif edited_column == 'iva':
                _iva = iva if iva is not None else 0.0
                if DEFAULT_VAT_RATE == 0:
                    base = _iva 
                    importe = _iva
                else:
                    base = _iva / DEFAULT_VAT_RATE
                    importe = base + _iva
            
            # 3. Actualizar la BBDD
            value_to_save = cleaned_edited_value if is_numeric_field else edited_value
            
            cursor.execute(f"UPDATE processed_invoices SET {edited_column} = ? WHERE path = ?",
                           (value_to_save, self.file_path))
            
            if edited_column in ['base', 'iva', 'importe']:
                 cursor.execute("UPDATE processed_invoices SET base = ?, iva = ?, importe = ? WHERE path = ?",
                               (base, iva, importe, self.file_path))

            conn.commit()
            
            # 4. Actualizar la GUI
            if edited_column in ['base', 'iva', 'importe']:
                self.form_entries['base'].set(f"{(base or 0.0):.2f}".replace('.', ','))
                self.form_entries['iva'].set(f"{(iva or 0.0):.2f}".replace('.', ','))
                self.form_entries['importe'].set(f"{(importe or 0.0):.2f}".replace('.', ','))
                messagebox.showinfo("Guardado", f"Valores recalculados y guardados: Base, IVA, Importe Total.")
            else:
                 messagebox.showinfo("Guardado", f"Campo '{edited_column}' guardado.")

        except Exception as e:
            messagebox.showerror("Error de Guardado/BBDD", f"Error al actualizar la base de datos o al recalcular: {e}\n{traceback.format_exc()}")
            conn.rollback()
        finally:
            conn.close()
        
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
    # Por defecto, usa el mapeo de la clase BaseInvoiceExtractor
    
    # Ejemplo de Mapeo para IMPORTE (descomente y edite):
    # SPECIFIC_EXTRACTION_MAPPING = {{
    #     'IMPORTE': [
    #         # Copie y pegue aquí la regla generada en la pestaña 'Editor de Reglas'
    #         # Ejemplo:
    #         # {{ 'type': 'VARIABLE', 'ref_text': 'Total:', 'offset': 0, 'segment': 2 }}
    #     ]
    # }}
    
    def extract_data(self, lines: List[str]) -> Dict[str, Any]:
        
        # Si SPECIFIC_EXTRACTION_MAPPING está definido, debería usar una lógica 
        # para combinar el mapeo genérico (super().extract_data) con el específico.
        # Por simplicidad, aquí sólo llama al base por defecto:
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
        self.canvas = tk.Canvas(parent, bg="lightgray", borderwidth=2, relief="sunken")
        self.canvas.pack(fill=tk.BOTH, expand=True, pady=10)
        self.canvas.bind('<Configure>', self._on_canvas_resize)
        
        control_frame = ttk.Frame(parent)
        control_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(control_frame, text="Zoom In (+)", command=lambda: self.change_zoom(0.1)).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Zoom Out (-)", command=lambda: self.change_zoom(-0.1)).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(control_frame, text="< Página", command=lambda: self.change_page(-1)).pack(side=tk.RIGHT, padx=5)
        self.page_label = ttk.Label(control_frame, text="Página 0 de 0", width=15, anchor='center')
        self.page_label.pack(side=tk.RIGHT, padx=5)
        ttk.Button(control_frame, text="Página >", command=lambda: self.change_page(1)).pack(side=tk.RIGHT, padx=5)

    def _open_document(self, path: str):
        if not VIEWER_AVAILABLE:
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
        if self.doc:
            self.render_page()

    def render_page(self):
        if not self.doc or not VIEWER_AVAILABLE or not self.doc.page_count > self.page_num:
            self.canvas.delete("all")
            return

        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        if canvas_width <= 1 or canvas_height <= 1:
            return

        try:
            page = self.doc.load_page(self.page_num)
            
            matrix = fitz.Matrix(self.zoom, self.zoom)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            img_data = pix.tobytes("ppm")
            image = Image.open(io.BytesIO(img_data))

            img_width, img_height = image.size
            
            if img_width > canvas_width or img_height > canvas_height:
                ratio = min(canvas_width / img_width, canvas_height / img_height)
                new_width = int(img_width * ratio)
                new_height = int(img_height * ratio)
                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
            self.photo_image = ImageTk.PhotoImage(image)
            
            self.canvas.delete("all")
            self.image_display = self.canvas.create_image(
                canvas_width // 2, canvas_height // 2, 
                image=self.photo_image, 
                anchor="center"
            )

        except Exception as e:
            self.canvas.delete("all")
            self.canvas.create_text(canvas_width // 2, canvas_height // 2, 
                                    text=f"Error al renderizar página {self.page_num + 1}: {e}", 
                                    fill="red", anchor="center")
            
    def change_zoom(self, delta: float):
        if self.doc:
            self.zoom = max(0.1, self.zoom + delta)
            self.render_page()
            
    def change_page(self, delta: int):
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
    app = InvoiceApp(root)
    root.mainloop()