import os
import re
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, Menu, ttk
from typing import Dict, List, Tuple, Any, Optional
import fitz # PyMuPDF
from PIL import Image    # <-- AÑADIR
import pytesseract       # <-- AÑADIR
import importlib.util
import importlib
import subprocess
import json
import traceback


# --- Configuración de OCR (Tesseract) ---
# Colocar esto después de todas las instrucciones 'import'
try:
    # Aseguramos que los módulos existen antes de usarlos
    if 'pytesseract' in sys.modules and sys.platform == "win32":
        # ¡AJUSTA ESTA RUTA SI ES NECESARIO!
        # Si Tesseract no está en el PATH, debe especificarse aquí
        pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe' 
    
except Exception as e:
    print(f"Advertencia: No se pudo configurar pytesseract. El OCR podría no funcionar. Error: {e}")


# --- CONFIGURACIÓN DE RUTAS ---
EXTRACTORS_DIR = 'extractors'

# --- LÓGICA DE LECTURA DE PDF UNIFICADA CORREGIDA (CON FALLBACK OCR) ---
def _get_pdf_lines(pdf_path: str) -> List[str]:
    """
    Lee un PDF usando fitz (PyMuPDF). Si no encuentra texto, intenta OCR (Tesseract).
    """
    lines: List[str] = []
    file_extension = os.path.splitext(pdf_path)[1].lower()

    # --- Intento 1: Extracción directa de texto (capa de texto) ---
    try:
        doc = fitz.open(pdf_path)
        texto = ''
        for page in doc:
            texto += page.get_text() or ''
        doc.close()
        
        lines = [line.rstrip() for line in texto.splitlines() if line.strip()]
        
        # Si encuentra texto, retorna inmediatamente.
        if lines:
            print("✅ Texto extraído correctamente de la capa de texto del PDF.")
            return lines

    except Exception as e:
        print(f"❌ Error al intentar extracción directa de texto con fitz: {e}")
        pass # Continúa al intento de OCR

    # --- Intento 2: OCR si la extensión es PDF y no se encontró texto ---
    if file_extension == ".pdf" and not lines:
        print("⚠️ No se encontró capa de texto. Intentando OCR...")
        try:
            # Comprobamos que los módulos de OCR estén disponibles
            if 'pytesseract' in sys.modules and hasattr(sys.modules['pytesseract'], 'image_to_string') and Image is not None:
                
                # Reabrimos el documento para la rasterización
                doc = fitz.open(pdf_path)
                full_ocr_text = ""
                
                # Solo procesamos la primera página para optimizar
                if len(doc) > 0:
                    page = doc[0]
                    # Renderizar la página como imagen (pixmap) a una resolución alta (Matrix(2, 2))
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    
                    # Convertir a imagen de PIL
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    
                    # Aplicar Tesseract OCR con idioma español
                    full_ocr_text = pytesseract.image_to_string(img, lang='spa')
                    
                    doc.close()
                    
                    if full_ocr_text.strip():
                        lines = [line.rstrip() for line in full_ocr_text.splitlines() if line.strip()]
                        print("✅ Texto extraído correctamente mediante OCR.")
                        return lines
                    else:
                        print("❌ OCR no pudo extraer ningún texto.")
            else:
                print("❌ Módulos PIL/pytesseract no disponibles o Tesseract no configurado. El OCR no se ejecutará.")

        except Exception as e:
            print(f"❌ Error durante el proceso de OCR: {e}")
    
    # Si todo falla o no es un PDF
    return []
# --- PLANTILLA DEL EXTRACTOR BASE (SIN IMPORTACIÓN, CON COMENTARIO DE REGISTRO) ---
BASE_EXTRACTOR_TEMPLATE = r"""
# 🚨 MAPPING SUGERIDO PARA main_extractor_gui.py
# Copie la siguiente línea y péguela en el diccionario EXTRACTION_MAPPING en main_extractor_gui.py:
#
# "nueva_clave": "extractors.nombre_archivo_extractor.GeneratedExtractor", 
#
# Ejemplo (si el archivo generado es 'autolux_extractor.py'):
# "autolux": "extractors.autolux_extractor.GeneratedExtractor",

from typing import Dict, Any, List, Optional
import re
# La clase BaseInvoiceExtractor será INYECTADA en tiempo de ejecución (soluciona ImportError en main_extractor_gui.py).

# 🚨 EXTRACTION_MAPPING: Define la lógica de extracción.
# 'type': 'FIXED' (Fila Fija, línea absoluta 1-based), 'VARIABLE' (Variable, relativa a un texto), o 'FIXED_VALUE' (Valor Fijo, valor constante).
# 'segment': Posición de la palabra en la línea (1-based), o un rango (ej. "3-5").

EXTRACTION_MAPPING: Dict[str, Dict[str, Any]] = {
# MAPPINGS_GO_HERE
}
r
class GeneratedExtractor(BaseInvoiceExtractor):
    
    # 🚨 CORRECCIÓN: ACEPTAR explícitamente lines y pdf_path.
    # Usamos *args y **kwargs para máxima compatibilidad con el __init__ de BaseInvoiceExtractor.
    def __init__(self, lines: List[str] = None, pdf_path: str = None, *args, **kwargs):
        # El constructor GeneratedExtractor no necesita llamar a super().__init__ 
        # si BaseInvoiceExtractor maneja su propia inicialización o si el extractor 
        # generado solo necesita la función extract_data. 
        # Si BaseInvoiceExtractor TIENE lógica en __init__, DEBERÍAMOS LLAMARLA.
        try:
             # Intentamos llamar al padre con los argumentos necesarios
             super().__init__(lines=lines, pdf_path=pdf_path, *args, **kwargs)
        except TypeError:
             # Si el padre tiene un constructor simple, lo llamamos sin argumentos 
             # (o simplemente no hacemos nada si el padre es un stub vacío)
             try:
                 super().__init__()
             except:
                 pass
        
        # En el extractor generado, toda la lógica de extracción se realiza en extract_data, 
        # por lo que no necesitamos almacenar lines aquí.

    def extract_data(self, lines: List[str]) -> Dict[str, Any]:
        
        extracted_data = {}
        
        # Función auxiliar para buscar línea de referencia (primera coincidencia)
        def find_reference_line(ref_text: str) -> Optional[int]:
            ref_text_lower = ref_text.lower()
            for i, line in enumerate(lines):
                if ref_text_lower in line.lower():
                    return i
            return None

        # Función auxiliar para obtener el valor
        def get_value(mapping: Dict[str, Any]) -> Optional[str]:
            
            # 1. Caso FIXED_VALUE (valor constante, ej. Emisor, Tipo)
            if mapping['type'] == 'FIXED_VALUE':
                return mapping.get('value')
                
            line_index = None
            
            # 2. Determinar el índice de la línea final (0-based)
            if mapping['type'] == 'FIXED':
                abs_line_1based = mapping.get('line')
                if abs_line_1based is not None and abs_line_1based > 0:
                    line_index = abs_line_1based - 1 
                
            elif mapping['type'] == 'VARIABLE':
                ref_text = mapping.get('ref_text', '')
                offset = mapping.get('offset', 0)
                
                ref_index = find_reference_line(ref_text)
                
                if ref_index is not None:
                    line_index = ref_index + offset
            
            if line_index is None or not (0 <= line_index < len(lines)):
                return None
                
            # 3. Obtener el segmento
            segment_input = mapping['segment'] # Puede ser int o str de rango ("3-5")
            
            try:
                line_segments = re.split(r'\s+', lines[line_index].strip())
                line_segments = [seg for seg in line_segments if seg]
                
                # Check for range support
                if isinstance(segment_input, str) and re.match(r'^\d+-\d+$', segment_input):
                    start_s, end_s = segment_input.split('-')
                    start_idx = int(start_s) - 1 # 0-based start
                    end_idx = int(end_s) # 0-based exclusive end
                    
                    if 0 <= start_idx < end_idx and end_idx <= len(line_segments):
                        return ' '.join(line_segments[start_idx:end_idx]).strip()
                
                # Simple segment index (assuming it's an integer)
                segment_index_0based = int(segment_input) - 1
                
                if segment_index_0based < len(line_segments):
                    return line_segments[segment_index_0based].strip()
            except Exception:
                return None
                
            return None

        # 4. Aplicar el mapeo
        for key, mapping in EXTRACTION_MAPPING.items():
            value = get_value(mapping)
            if value is not None:
                extracted_data[key.lower()] = value
            else:
                extracted_data[key.lower()] = None

        return extracted_data
"""


class ExtractorGeneratorApp:
    def __init__(self, master: tk.Tk, initial_data: Dict[str, Any] = None):
        self.master = master
        master.title("Generador de Extractores de Facturas")
        
        self.data_fields = [
            ("Tipo", "tipo", ["Compra", "Venta"]), 
            ("Fecha", "fecha", None),
            ("Nº Factura", "num_factura", None),
            ("Emisor", "emisor", None),
            ("Cliente", "cliente", None),
            ("CIF Emisor", "cif", None),
            ("Modelo", "modelo", None),
            ("Matrícula", "matricula", None),
            ("Base", "base", None),
            ("IVA", "iva", None),
            ("Importe", "importe", None),
            ("Tasas", "tasas", None)
        ]
        
        self.pdf_lines: List[str] = []
        self.pdf_path_var = tk.StringVar()
        self.extractor_name_var = tk.StringVar()
        self.mapping_controls: Dict[str, Dict[str, Any]] = {}
        self.extracted_data_vars: Dict[str, tk.StringVar] = {} 
        self.active_mapping_field: tk.StringVar = tk.StringVar(value="num_factura") 

        self.setup_gui()

        if initial_data:
            self.load_initial_data(initial_data)

    def load_pdf_dialog(self):
        ruta_archivo = filedialog.askopenfilename(
            defaultextension=".pdf",
            filetypes=[("Archivos PDF", "*.pdf")]
        )
        if ruta_archivo:
            self.load_pdf(ruta_archivo)

    def load_pdf(self, path: str):
        self.pdf_lines = _get_pdf_lines(path)
        self.pdf_path_var.set(path)
        self.update_pdf_lines_display(self.pdf_lines)
        self.update_mapping_display()


    def load_initial_data(self, data: Dict[str, Any]):
        
        self.pdf_path_var.set(data.get('ruta_archivo', ''))
        self.extractor_name_var.set(data.get('extractor_name', 'NuevoExtractor'))

        extractor_path = os.path.join(EXTRACTORS_DIR, f"{self.extractor_name_var.get()}.py")
        current_mapping = self._get_existing_mapping(extractor_path)

        for _, field_name, _ in self.data_fields:
            self.extracted_data_vars[field_name].set(data.get(field_name) or "")
            
            mapping_data = current_mapping.get(field_name.upper())
            
            if field_name == 'tipo':
                continue 

            if mapping_data and mapping_data.get('type') != 'FIXED_VALUE':
                controls = self.mapping_controls.get(field_name)
                if controls:
                    # Mapear de vuelta el tipo interno a la visualización
                    internal_type = mapping_data.get('type', 'FIXED')
                    display_type = 'Fila Fija' if internal_type == 'FIXED' else 'Variable'
                    
                    controls['type_var'].set(display_type)
                    controls['segment_var'].set(str(mapping_data.get('segment', '')))
                    
                    if internal_type == 'FIXED':
                        controls['ref_var'].set(str(mapping_data.get('line', '')))
                        controls['offset_var'].set('0') 
                    elif internal_type == 'VARIABLE':
                        controls['ref_var'].set(mapping_data.get('ref_text', ''))
                        controls['offset_var'].set(str(mapping_data.get('offset', '0')))
            elif mapping_data and mapping_data.get('type') == 'FIXED_VALUE':
                # Sobreescribir con el valor fijo si existía en el mapeo
                self.extracted_data_vars[field_name].set(mapping_data.get('value') or "")
                # Establecer el tipo de mapeo a 'Valor Fijo'
                controls = self.mapping_controls.get(field_name)
                if controls:
                    controls['type_var'].set('Valor Fijo')


    def _get_existing_mapping(self, path: str) -> Dict[str, Any]:
        """Intenta importar el archivo .py y recuperar el diccionario EXTRACTION_MAPPING."""
        try:
            if not os.path.exists(path):
                return {}
                
            module_name = os.path.basename(path).replace('.py', '')
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                
                # Para evitar el ImportError al cargar extractores no generados que SÍ tienen la importación
                if BaseInvoiceExtractor_Class := globals().get('BaseInvoiceExtractor'):
                    module.__dict__['BaseInvoiceExtractor'] = BaseInvoiceExtractor_Class
                    
                spec.loader.exec_module(module)
                return getattr(module, 'EXTRACTION_MAPPING', {})
        except Exception:
            # Ignorar errores de importación si la sintaxis del archivo es inválida
            return {}
        return {}


    def setup_gui(self):
        main_frame = ttk.Frame(self.master, padding="10")
        main_frame.pack(fill="both", expand=True)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_columnconfigure(1, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)

        pdf_frame = ttk.LabelFrame(main_frame, text="Contenido del PDF (Click para mapear)", padding="10")
        pdf_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        pdf_frame.grid_rowconfigure(0, weight=1)
        pdf_frame.grid_columnconfigure(0, weight=1)

        self.pdf_lines_text = scrolledtext.ScrolledText(pdf_frame, wrap=tk.WORD, height=30, width=50, font=('Courier', 10))
        self.pdf_lines_text.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.pdf_lines_text.insert(tk.END, "Cargue un archivo PDF para ver sus líneas aquí.")

        self.pdf_lines_text.bind('<Button-1>', self.on_pdf_click)
        self.pdf_lines_text.bind('<ButtonRelease-1>', self.on_pdf_release)

        file_control_frame = ttk.Frame(pdf_frame)
        file_control_frame.grid(row=1, column=0, sticky="ew", pady=(5,0))
        ttk.Label(file_control_frame, textvariable=self.pdf_path_var, wraplength=400).pack(side="left", fill="x", expand=True, padx=5)
        ttk.Button(file_control_frame, text="Cargar Nuevo PDF", command=self.load_pdf_dialog).pack(side="right", padx=5)

        self.mapping_frame = ttk.LabelFrame(main_frame, text="Mapeo de Campos del Extractor (Líneas 1-Based)", padding="10")
        self.mapping_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        
        mapping_canvas = tk.Canvas(self.mapping_frame)
        mapping_canvas.pack(side="left", fill="both", expand=True)

        mapping_scrollbar = ttk.Scrollbar(self.mapping_frame, orient="vertical", command=mapping_canvas.yview)
        mapping_scrollbar.pack(side="right", fill="y")

        mapping_canvas.configure(yscrollcommand=mapping_scrollbar.set)
        mapping_canvas.bind('<Configure>', lambda e: mapping_canvas.configure(scrollregion = mapping_canvas.bbox("all")))

        inner_frame = ttk.Frame(mapping_canvas)
        mapping_canvas.create_window((0, 0), window=inner_frame, anchor="nw")
        inner_frame.bind("<Configure>", lambda e: mapping_canvas.configure(scrollregion=mapping_canvas.bbox("all")))
        
        headers = ["Campo", "Valor Fijo/Extraído", "Tipo", "Ref.", "Off.", "Seg.", "Línea Mapeada"]
        col_weights = [2, 4, 3, 3, 1, 1, 6] 
        
        for col, header in enumerate(headers):
            lbl = ttk.Label(inner_frame, text=header, font=("Arial", 9, "bold"))
            lbl.grid(row=0, column=col, padx=5, pady=5)
            inner_frame.grid_columnconfigure(col, weight=col_weights[col])


        for i, (label, field_name, fixed_options) in enumerate(self.data_fields):
            row = i + 1
            
            ttk.Label(inner_frame, text=label).grid(row=row, column=0, sticky="w", padx=5, pady=2)
            
            extracted_var = tk.StringVar()
            self.extracted_data_vars[field_name] = extracted_var
            
            if fixed_options:
                value_control = ttk.Combobox(inner_frame, textvariable=extracted_var, values=fixed_options, width=10, state='readonly')
                value_control.grid(row=row, column=1, padx=5, pady=2, sticky="ew")
                mappable = False
            else:
                value_control = ttk.Entry(inner_frame, textvariable=extracted_var, width=15)
                value_control.grid(row=row, column=1, padx=5, pady=2, sticky="ew")
                mappable = True
            
            
            if mappable:
                # Nuevos nombres y nueva opción 'Valor Fijo'
                type_var = tk.StringVar(value='Fila Fija')
                type_combo = ttk.Combobox(inner_frame, textvariable=type_var, values=['Fila Fija', 'Variable', 'Valor Fijo'], width=10, state='readonly')
                type_combo.grid(row=row, column=2, padx=5, pady=2)
                type_combo.bind("<<ComboboxSelected>>", lambda *args, f=field_name: self.update_mapping_display(f))
                
                ref_var = tk.StringVar(value='')
                ref_entry = ttk.Entry(inner_frame, textvariable=ref_var, width=12)
                ref_entry.grid(row=row, column=3, padx=5, pady=2)
                
                offset_var = tk.StringVar(value='0')
                offset_entry = ttk.Entry(inner_frame, textvariable=offset_var, width=5)
                offset_entry.grid(row=row, column=4, padx=5, pady=2)
                
                segment_var = tk.StringVar(value='')
                segment_entry = ttk.Entry(inner_frame, textvariable=segment_var, width=5)
                segment_entry.grid(row=row, column=5, padx=5, pady=2)
                
                mapped_line_var = tk.StringVar(value='(Sin Mapeo)')
                mapped_line_label = ttk.Label(inner_frame, textvariable=mapped_line_var, width=35, anchor="w", relief=tk.FLAT)
                mapped_line_label.grid(row=row, column=6, sticky="w", padx=5, pady=2)
                
                self.mapping_controls[field_name] = {
                    'type_var': type_var, 'ref_var': ref_var, 'offset_var': offset_var, 'segment_var': segment_var, 
                    'mapped_line_var': mapped_line_var, 
                    'ref_entry': ref_entry, 'segment_entry': segment_entry, 'offset_entry': offset_entry,
                    'value_control': value_control, # Referencia al campo de entrada central
                }
                
                # Las trazas se mantienen para la actualización dinámica del mapeo en la línea
                ref_var.trace_add('write', lambda *args, f=field_name: self.update_mapping_display(f))
                offset_var.trace_add('write', lambda *args, f=field_name: self.update_mapping_display(f))
                segment_var.trace_add('write', lambda *args, f=field_name: self.update_mapping_display(f))
                
                ref_entry.bind('<FocusIn>', lambda *args, f=field_name: self.active_mapping_field.set(f))
                segment_entry.bind('<FocusIn>', lambda *args, f=field_name: self.active_mapping_field.set(f))
                offset_entry.bind('<FocusIn>', lambda *args, f=field_name: self.active_mapping_field.set(f))

                # Establecer el estado inicial (Fila Fija por defecto)
                self._toggle_controls_state(field_name) 

            else:
                for col in range(2, 7):
                    ttk.Label(inner_frame, text="---").grid(row=row, column=col, padx=5, pady=2)

        control_frame = ttk.Frame(main_frame, padding="5")
        control_frame.grid(row=1, column=0, columnspan=2, sticky="ew")

        ttk.Label(control_frame, text="Nombre del Extractor:").pack(side="left", padx=5)
        ttk.Entry(control_frame, textvariable=self.extractor_name_var, width=20).pack(side="left", padx=5)
        
        ttk.Button(control_frame, text="Probar Extractor Generado", command=self.test_generated_extractor).pack(side="right", padx=5)
        ttk.Button(control_frame, text="Generar Extractor (.py)", command=self.generate_extractor).pack(side="right", padx=5)

    def _toggle_controls_state(self, field_name: str):
        """Habilita/deshabilita los campos de referencia (Ref/Off/Seg) y el campo central (Value) 
        basándose en el tipo de mapeo seleccionado."""
        
        controls = self.mapping_controls.get(field_name)
        if not controls: return

        current_type = controls['type_var'].get()
        
        # 'Valor Fijo' (FIXED_VALUE) desactiva Ref/Off/Seg, activa Value
        if current_type == 'Valor Fijo':
            controls['ref_entry']['state'] = 'disabled'
            controls['offset_entry']['state'] = 'disabled'
            controls['segment_entry']['state'] = 'disabled'
            controls['value_control']['state'] = 'normal'
        # 'Fila Fija' (FIXED) / 'Variable' (VARIABLE) activan Ref/Off/Seg, desactiva Value
        else:
            controls['ref_entry']['state'] = 'normal'
            controls['offset_entry']['state'] = 'normal' 
            controls['segment_entry']['state'] = 'normal'
            controls['value_control']['state'] = 'readonly' 
            
    def on_pdf_click(self, event):
        if not self.pdf_lines: return

        index = self.pdf_lines_text.index(f"@{event.x},{event.y}")
        line_num = int(index.split('.')[0])
        pdf_line_1based = line_num

        active_field = self.active_mapping_field.get()
        controls = self.mapping_controls.get(active_field)
        
        # Si no es 'Fila Fija', ignorar el click en el PDF
        if controls and controls['type_var'].get() == 'Fila Fija':
            controls['ref_var'].set(str(pdf_line_1based))
            controls['segment_var'].set('1') 
            controls['segment_entry'].focus_set()
            self.update_mapping_display(active_field)


    def on_pdf_release(self, event):
        active_field = self.active_mapping_field.get()
        controls = self.mapping_controls.get(active_field)

        if not controls or not self.pdf_lines: return
        
        try:
            selected_text = self.pdf_lines_text.get(tk.SEL_FIRST, tk.SEL_LAST).strip()
        except tk.TclError:
            return

        if not selected_text:
            return

        current_type = controls['type_var'].get()
        
        # 'Variable' se mantiene, el foco se pone en Segmento
        if current_type == 'Variable':
            controls['ref_var'].set(selected_text)
            controls['offset_var'].set('0')
            controls['segment_var'].set('1')
            controls['segment_entry'].focus_set()
            self.update_mapping_display(active_field)
            self.pdf_lines_text.tag_remove(tk.SEL, "1.0", tk.END) 
            
        # 'Fila Fija' se mantiene, el valor se pone en el campo central si es una selección
        elif current_type == 'Fila Fija':
            if var := self.extracted_data_vars.get(active_field):
                var.set(selected_text)
                self.pdf_lines_text.tag_remove(tk.SEL, "1.0", tk.END)

    def update_pdf_lines_display(self, lines: List[str]):
        self.pdf_lines_text.delete('1.0', tk.END)
        if lines:
            numbered_lines = [f"L{i+1:03d}: {line}" for i, line in enumerate(lines)]
            self.pdf_lines_text.insert(tk.END, "\n".join(numbered_lines))
        else:
            self.pdf_lines_text.insert(tk.END, "(No se pudieron extraer líneas del PDF)")
            
    def update_mapping_display(self, field_name: Optional[str] = None, *args):
        if not self.pdf_lines:
            return

        fields_to_update = [field_name] if field_name else [name for _, name, _ in self.data_fields if name != 'tipo']

        for f_name in fields_to_update:
            controls = self.mapping_controls.get(f_name)
            if not controls: continue
            
            # Llamada a toggle para activar/desactivar controles al cambiar el tipo
            self._toggle_controls_state(f_name) 

            type_display_name = controls['type_var'].get()
            
            if type_display_name == 'Valor Fijo':
                 controls['mapped_line_var'].set("(Valor Fijo en Campo Central)")
                 continue
                 
            # Mapear display name a internal keyword
            type_val = 'FIXED' if type_display_name == 'Fila Fija' else 'VARIABLE'

            ref_val = controls['ref_var'].get().strip()
            offset_val_str = controls['offset_var'].get().strip()
            mapped_line_var = controls['mapped_line_var']
            mapped_line_var.set("...")

            try:
                target_line_index = -1
                offset = int(offset_val_str) if offset_val_str else 0
                
                if type_val == 'FIXED' and ref_val.isdigit():
                    abs_line_1based = int(ref_val)
                    if abs_line_1based > 0:
                        target_line_index = (abs_line_1based - 1) + offset
                        
                elif type_val == 'VARIABLE' and ref_val:
                    ref_index = -1 
                    ref_val_lower = ref_val.lower()
                    for i, line in enumerate(self.pdf_lines):
                        if ref_val_lower in line.lower():
                            ref_index = i
                            break
                            
                    if ref_index != -1:
                        target_line_index = ref_index + offset

                if 0 <= target_line_index < len(self.pdf_lines):
                    line_content = self.pdf_lines[target_line_index]
                    display_text = f"L{target_line_index + 1} (Off {offset}): {line_content[:30]}..."
                    mapped_line_var.set(display_text)
                    
                else:
                    mapped_line_var.set("(Línea fuera de rango)")

            except ValueError:
                mapped_line_var.set("(Valor numérico inválido)")
            except Exception as e:
                mapped_line_var.set(f"(Error: {e})")
            
    # --- FUNCIÓN DE PRUEBA CORREGIDA ---
    def test_generated_extractor(self):
        if not self.pdf_lines:
            messagebox.showerror("Error de Prueba", "Debe cargar un PDF primero.")
            return

        extractor_code = self._generate_extractor_template()
        
        try:
            module_name = "temp_generated_extractor"
            spec = importlib.util.spec_from_loader(module_name, loader=None)
            module = importlib.util.module_from_spec(spec)
            
            # 🚨 FIX: INYECTAR LA CLASE BASE EN EL MÓDULO TEMPORAL
            # Esto resuelve el ImportError al ejecutar el código generado en memoria.
            base_class = globals().get('BaseInvoiceExtractor')
            if base_class:
                module.__dict__['BaseInvoiceExtractor'] = base_class
                
            # Ejecutar el código generado dinámicamente
            exec(extractor_code, module.__dict__)
            
            ExtractorClass = getattr(module, 'GeneratedExtractor')
            
            # Instanciar el extractor (pasando argumentos None para compatibilidad con el __init__ de BaseInvoiceExtractor)
            extractor_instance = ExtractorClass(lines=None, pdf_path=None) 
            
            test_results = extractor_instance.extract_data(self.pdf_lines)
            
            final_results = {}
            for _, field_name, _ in self.data_fields:
                extracted_value = test_results.get(field_name.lower())
                current_entry_value = self.extracted_data_vars.get(field_name).get().strip()

                if extracted_value is None and current_entry_value:
                    # Si no hay extracción (y es un valor fijo no mapeado, o un valor por defecto)
                    # Lo dejo aquí para preservar el valor si el usuario lo introdujo manualmente
                    final_results[field_name] = current_entry_value
                else:
                    final_results[field_name] = extracted_value
                
                # Actualizar la interfaz con el resultado final
                self.extracted_data_vars.get(field_name).set(final_results[field_name] or "")

            # Mostrar los resultados en la nueva ventana tabular
            self._show_test_results_table(final_results)

        except Exception as e:
            error_details = traceback.format_exc()
            messagebox.showerror("Error en la Prueba", f"El extractor generado falló durante la prueba.\nError: {e}\n\nDetalles:\n{error_details}")

    def _show_test_results_table(self, results: Dict[str, str]):
        """Muestra los resultados de la extracción en una ventana tabular."""
        result_window = tk.Toplevel(self.master)
        result_window.title("Resultados de la Extracción de Prueba")
        result_window.transient(self.master)
        result_window.grab_set()

        tree_frame = ttk.Frame(result_window, padding="10")
        tree_frame.pack(fill="both", expand=True)

        tree = ttk.Treeview(tree_frame, columns=("Field", "Value"), show="headings", height=15)
        tree.heading("Field", text="Campo", anchor=tk.W)
        tree.heading("Value", text="Valor Extraído", anchor=tk.W)
        
        tree.column("Field", width=150, stretch=tk.NO)
        tree.column("Value", width=300, stretch=tk.YES)

        for _, field_name, _ in self.data_fields:
            label = [l for l, n, o in self.data_fields if n == field_name][0]
            value = results.get(field_name)
            display_value = str(value) if value is not None and value != "" else "N/A"
            tree.insert("", tk.END, values=(label, display_value))

        tree_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=tree_scrollbar.set)

        tree.pack(side="left", fill="both", expand=True)
        tree_scrollbar.pack(side="right", fill="y")
        
        result_window.update_idletasks()
        width = result_window.winfo_width()
        height = result_window.winfo_height()
        x = self.master.winfo_x() + (self.master.winfo_width() // 2) - (width // 2)
        y = self.master.winfo_y() + (self.master.winfo_height() // 2) - (height // 2)
        result_window.geometry('+%d+%d' % (x, y))

    def generate_extractor(self):
        extractor_name = self.extractor_name_var.get().strip()
        if not extractor_name:
            messagebox.showerror("Error", "Por favor, ingrese un nombre válido para el extractor.")
            return

        if not os.path.exists(EXTRACTORS_DIR):
            os.makedirs(EXTRACTORS_DIR)

        file_content = self._generate_extractor_template()
        # Convertir a snake_case para el nombre del archivo si es necesario
        snake_case_name = re.sub(r'(?<!^)(?=[A-Z])', '_', extractor_name).lower()
        file_path = os.path.join(EXTRACTORS_DIR, f"{snake_case_name}.py")
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(file_content)
            
            messagebox.showinfo("Éxito", f"Extractor '{snake_case_name}.py' generado correctamente en la carpeta '{EXTRACTORS_DIR}'.")
            
        except Exception as e:
            messagebox.showerror("Error al Guardar", f"No se pudo guardar el archivo en {file_path}. Error: {e}")


    def _generate_extractor_template(self) -> str:
        
        mapping_content_list = []
        
        for _, field_name, fixed_options in self.data_fields:
            # Obtener el valor del campo central (que puede ser fijo o temporalmente extraído)
            fixed_value = self.extracted_data_vars.get(field_name, tk.StringVar()).get().strip()

            if not fixed_options: 
                controls = self.mapping_controls.get(field_name)
                
                if controls:
                    type_display_name = controls['type_var'].get()
                    
                    # 🚨 CAMBIO CLAVE: Priorizar Valor Fijo si está seleccionado
                    if type_display_name == 'Valor Fijo':
                        if fixed_value:
                            mapping_data: Dict[str, Any] = {'type': 'FIXED_VALUE', 'value': fixed_value}
                            mapping_str = "    '{}': {},\n".format(field_name.upper(), repr(mapping_data))
                            mapping_content_list.append(mapping_str)
                        continue 
                    
                    # Si no es Valor Fijo, procesar mapping de línea (Fila Fija o Variable)
                    type_val = 'FIXED' if type_display_name == 'Fila Fija' else 'VARIABLE'
                    
                    try:
                        ref_val = controls['ref_var'].get().strip()
                        offset_val_str = controls['offset_var'].get().strip()
                        segment_val_str = controls['segment_var'].get().strip()
                        
                        # Manejo de segmento (puede ser int o string de rango)
                        if segment_val_str.isdigit():
                            segment_value = int(segment_val_str)
                        elif re.match(r'^\d+-\d+$', segment_val_str):
                            segment_value = segment_val_str # Dejarlo como string para el rango
                        else:
                            segment_value = 0 # Valor no válido

                        offset = int(offset_val_str) if offset_val_str else 0
                        
                        # Chequear validez del mapping de línea
                        is_valid_segment = (isinstance(segment_value, int) and segment_value >= 1) or \
                                           (isinstance(segment_value, str) and re.match(r'^\d+-\d+$', segment_value))


                        if is_valid_segment and ((type_val == 'FIXED' and ref_val.isdigit() and int(ref_val) > 0) or (type_val == 'VARIABLE' and ref_val)):
                            
                            mapping_data: Dict[str, Any] = {'type': type_val, 'segment': segment_value}
                            
                            if type_val == 'FIXED':
                                mapping_data['line'] = int(ref_val)
                            elif type_val == 'VARIABLE':
                                mapping_data['ref_text'] = ref_val
                                mapping_data['offset'] = offset
                            
                            mapping_str = "    '{}': {},\n".format(field_name.upper(), repr(mapping_data))
                            mapping_content_list.append(mapping_str)
                            continue 

                    except ValueError:
                        pass # Ignorar mapping de línea inválido
                
                # Fallback: Si no hay mapping válido (de línea o Valor Fijo explícito), pero hay un valor escrito a mano
                elif fixed_value:
                    # Consideramos que si el usuario escribió un valor y no lo mapeó, es un valor fijo manual
                    mapping_data: Dict[str, Any] = {'type': 'FIXED_VALUE', 'value': fixed_value}
                    mapping_str = "    '{}': {},\n".format(field_name.upper(), repr(mapping_data))
                    mapping_content_list.append(mapping_str)

            elif field_name == 'tipo':
                # Caso especial para el combo 'Tipo' (no usa los controles de mapping, siempre es Valor Fijo)
                if fixed_value:
                    mapping_data: Dict[str, Any] = {'type': 'FIXED_VALUE', 'value': fixed_value}
                    mapping_str = "    '{}': {},\n".format(field_name.upper(), repr(mapping_data))
                    mapping_content_list.append(mapping_str)


        mappings_str = "".join(mapping_content_list)
        final_template = BASE_EXTRACTOR_TEMPLATE.replace("# MAPPINGS_GO_HERE", mappings_str)
        
        return final_template

def load_initial_data_from_cli():
    
    if len(sys.argv) < 16:
        return None

    try:
        data = {
            'ruta_archivo': sys.argv[1],
            'extractor_name': sys.argv[2],
            'debug_lines': sys.argv[3], 
            'tipo': sys.argv[4],
            'fecha': sys.argv[5],
            'num_factura': sys.argv[6],
            'emisor': sys.argv[7],
            'cliente': sys.argv[8],
            'cif': sys.argv[9],
            'modelo': sys.argv[10],
            'matricula': sys.argv[11],
            'base': sys.argv[12],
            'iva': sys.argv[13],
            'importe': sys.argv[14],
            'tasas': sys.argv[15],
        }
        return data
    except IndexError as e:
        print(f"Error al parsear argumentos CLI: {e}")
        return None

if __name__ == "__main__":
    initial_data = load_initial_data_from_cli()
    root = tk.Tk()
    app = ExtractorGeneratorApp(root, initial_data)
    
    if initial_data and initial_data.get('ruta_archivo'):
        app.load_pdf(initial_data['ruta_archivo'])
        
    root.mainloop()