import os
import csv
import PyPDF2
import shutil
import fitz # Motor principal para lectura de PDF y rasterización para OCR
import tempfile 
import sys 
import importlib 
import tkinter as tk
from tkinter import filedialog, messagebox, ttk 
from tkinter.scrolledtext import ScrolledText 
from typing import Tuple, List, Optional, Any, Dict 
import subprocess 
import re 
from PIL import Image
import pytesseract


# --- Configuración de OCR (Tesseract) ---
try:
    from PIL import Image
    import pytesseract
    
    if sys.platform == "win32":
        # ¡AJUSTA ESTA RUTA SI ES NECESARIO!
        pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe' 
    
except ImportError:
    Image = None
    pytesseract = None
except AttributeError:
    Image = None
    pytesseract = None


# --- Importaciones de Extractor y Utilidades (STUBS/MOCKUPS) ---
try:
    # Intenta importar el extractor base
    from extractors.base_invoice_extractor import BaseInvoiceExtractor
    # Intenta importar utilidades
    from split_pdf import split_pdf_into_single_page_files
    # converterImgPDF YA NO SE USA
except ImportError:
    # Stubs si BaseInvoiceExtractor o utilidades no existen
    class BaseInvoiceExtractor:
        def __init__(self, lines, pdf_path=None): 
            self.lines = lines
            self.pdf_path = pdf_path
            self.cif = 'B00000000'
        def extract_all(self): 
            return ("Tipo_BASE", "Fecha_BASE", "NºFactura_BASE", "Emisor_BASE", "Cliente_BASE", "CIF_BASE", "Modelo_BASE", "Matricula_BASE", 100.0, 82.64, 17.36, 0.0)
        def is_valid(self): return True
    
    def split_pdf_into_single_page_files(a, b): return [a]
    print("ADVERTENCIA: Usando stubs para BaseInvoiceExtractor y utilidades.")


# --- Mapeo de Clases de Extracción ---
EXTRACTION_MAPPING = {
    "autodoc": "extractors.autodoc_extractor.AutodocExtractor",
    "stellantis": "extractors.stellantis_extractor.StellantisExtractor",
    "brildor": "extractors.brildor_extractor.BrildorExtractor",
    "hermanas": "extractors.hermanas_extractor.HermanasExtractor",
    "kiauto": "extractors.kiauto_extractor.KiautoExtractor",
    "sumauto": "extractors.sumauto_extractor.SumautoExtractor",
    "amor": "extractors.hermanas_extractor.HermanasExtractor", 
    "pinchete": "extractors.pinchete_extractor.PincheteExtractor",
    "refialias": "extractors.refialias_extractor.RefialiasExtractor",
    "leroy": "extractors.leroy_extractor.LeroyExtractor",
    "poyo": "extractors.poyo_extractor.PoyoExtractor",
    "caravana": "extractors.lacaravana_extractor.LacaravanaExtractor",
    "malaga": "extractors.malaga_extractor.MalagaExtractor",
    "beroil": "extractors.beroil_extractor.BeroilExtractor",
    "berolkemi": "extractors.berolkemi_extractor.BerolkemiExtractor",
    "autocasher": "extractors.autocasher_extractor.AutocasherExtractor",
    "cesvimap": "extractors.cesvimap_extractor.CesvimapExtractor",
    "fiel": "extractors.fiel_extractor.FielExtractor",
    "pradilla": "extractors.pradilla_extractor.PradillaExtractor", 
    "boxes": "extractors.boxes_extractor.BoxesExtractor",
    "hergar": "extractors.hergar_extractor.HergarExtractor",
    "musas": "extractors.musas_extractor.MusasExtractor",
    "muas": "extractors.musas_extractor.MusasExtractor", 
    "aema": "extractors.aema_extractor.AemaExtractor",
    "autodescuento": "extractors.autodescuento_extractor.AutodescuentoExtractor",
    "northgate": "extractors.northgate_extractor.NorthgateExtractor",
    "recoautos": "extractors.recoautos_extractor.RecoautosExtractor",
    "colomer": "extractors.colomer_extractor.ColomerExtractor",
    "wurth": "extractors.wurth_extractor.WurthExtractor",
    "candelar": "extractors.cantelar_extractor.CantelarExtractor",
    "cantelar": "extractors.cantelar_extractor.CantelarExtractor",
    "volkswagen": "extractors.volkswagen_extractor.VolkswagenExtractor",
    "oscaro": "extractors.oscaro_extractor.OscaroExtractor",
    "adevinta": "extractors.adevinta_extractor.AdevintaExtractor",
    "amazon": "extractors.amazon_extractor.AmazonExtractor",
    "coslauto": "extractors.coslauto_extractor.CoslautoExtractor",
    "autolux": "extractors.autolux_extractor.GeneratedExtractor",
    "eduardo": "extractors.desguaceseduardo_extractor.DesguaceseduardoExtractor"
}

VAT_RATE = "21%" 
ERROR_DATA: Tuple[Any, ...] = (
    "ERROR_EXTRACCION", None, None, None, None, None, None, None, None, None, None, None, "Error de lectura o formato." 
)

# ----------------------------------------------------------------------
# FUNCIONES AUXILIARES 
# ----------------------------------------------------------------------

def _get_pdf_lines(pdf_path: str) -> List[str]:
    """
    Lee un PDF usando fitz/PyMuPDF, que es más robusto que PyPDF2, 
    y devuelve una lista de líneas de texto.
    """
    lines: List[str] = []
    try:
        doc = fitz.open(pdf_path)
        texto = ''
        for page in doc:
            texto += page.get_text() or ''
        doc.close()
        # Filtrar líneas vacías
        lines = [line for line in texto.splitlines() if line.strip()] 
        return lines
    except Exception as e:
        print(f"❌ Error de Lectura PDF con fitz: {e}") 
        return []

def find_extractor_for_file(file_path: str) -> Optional[str]:
    """Busca la clase de extractor adecuada para un archivo. (Sin cambios)"""
    
    nombre_archivo = os.path.basename(file_path).lower()
    for keyword, class_path in EXTRACTION_MAPPING.items():
        if keyword in nombre_archivo:
            return class_path
            
    try:
        lines = _get_pdf_lines(file_path)
        if not lines:
            return None
            
        temp_extractor = BaseInvoiceExtractor(lines, file_path) 
        extracted_data = temp_extractor.extract_all()
        
        cif_extraido_base = str(extracted_data[5]).replace('-', '').replace('.', '').strip().upper() if len(extracted_data) > 5 else None
        
        if cif_extraido_base:
            for keyword, class_path in EXTRACTION_MAPPING.items():
                try:
                    module_path, class_name = class_path.rsplit('.', 1)
                    module = importlib.import_module(module_path)
                    ExtractorClass = getattr(module, class_name)
                        
                    if hasattr(ExtractorClass, 'EMISOR_CIF') and ExtractorClass.EMISOR_CIF.upper() == cif_extraido_base:
                        return class_path
                except Exception:
                    continue 
            
    except Exception:
        pass

    return None

# ----------------------------------------------------------------------
# FUNCIÓN PRINCIPAL DE EXTRACCIÓN 
# ----------------------------------------------------------------------

def extraer_datos(pdf_path: str, debug_mode: bool = False) -> Tuple[Any, ...]:
    """ 
    Extrae datos. Ahora usa PyMuPDF y OCR directo por rasterización (más robusto).
    """
    
    def _pad_data(data: Tuple) -> Tuple:
        REQUIRED_FIELDS = 12
        if len(data) >= REQUIRED_FIELDS:
            return data[:REQUIRED_FIELDS]
        return data + (None,) * (REQUIRED_FIELDS - len(data))

    debug_output: str = "" 
    extracted_data_raw: Tuple = tuple() 
    file_extension = os.path.splitext(pdf_path)[1].lower()
    temp_img_to_delete: Optional[str] = None # Para la limpieza de imágenes temporales

    try:
        # 1. Manejo de IMÁGENES (Archivos .jpg, .png, etc.)
        if file_extension in ['.jpg', '.jpeg', '.png', '.tiff', '.tif']:
            if not Image or not pytesseract:
                 debug_output = "ERROR: OCR (Tesseract/PIL) no disponible para imágenes."
                 return (*_pad_data(extracted_data_raw), debug_output)

            try:
                 # Ejecutar Tesseract directamente sobre la imagen (pdf_path es la ruta de la imagen)
                 ocr_text = pytesseract.image_to_string(Image.open(pdf_path), lang='spa')
                 lines = [line for line in ocr_text.splitlines() if line.strip()]
                 
                 if not lines:
                    debug_output = "❌ Fallo: OCR directo sobre la imagen no produjo texto."
                    return (*_pad_data(extracted_data_raw), debug_output)

                 debug_output += "✅ Éxito: OCR directo sobre imagen inicial.\n"
                 
            except Exception as e:
                 debug_output = f"❌ ERROR: Falló el procesamiento OCR de la imagen: {e}"
                 return (*_pad_data(extracted_data_raw), debug_output)
        
        else: # Es un PDF (o extensión no soportada que intentaremos leer)
            if not os.path.exists(pdf_path):
                debug_output = f"Error: El archivo '{pdf_path}' no existe."
                return (*_pad_data(extracted_data_raw), debug_output)
            
            # 2. Lectura Inicial del PDF con fitz (más robusto)
            lines = _get_pdf_lines(pdf_path)

            # 🚨 NUEVA LÓGICA: Manejo de PDF basados en imagen (Sin texto)
            if not lines and file_extension == ".pdf":
                debug_output += "⚠️ ADVERTENCIA: PDF sin capa de texto legible. Intentando con OCR (Rasterización)... \n"
                
                if Image and pytesseract:
                    try:
                        # 1. Rasterizar (Convertir la primera página a Imagen PNG de alta resolución)
                        doc = fitz.open(pdf_path)
                        page = doc.load_page(0)
                        
                        # Matriz para 300 DPI (alta resolución)
                        zoom = 300 / 72  
                        mat = fitz.Matrix(zoom, zoom)
                        pix = page.get_pixmap(matrix=mat, alpha=False)
                        doc.close()
                        
                        # Guardar la imagen temporalmente
                        temp_img_name = f"ocr_temp_{os.path.splitext(os.path.basename(pdf_path))[0]}.png"
                        temp_img_to_delete = os.path.join(tempfile.gettempdir(), temp_img_name)
                        pix.save(temp_img_to_delete)

                        # 2. Ejecutar Tesseract sobre la imagen
                        ocr_text = pytesseract.image_to_string(Image.open(temp_img_to_delete), lang='spa')
                        
                        lines = [line for line in ocr_text.splitlines() if line.strip()]

                        if lines:
                            debug_output += "✅ Éxito: OCR directo sobre imagen rasterizada. Texto encontrado.\n"
                        else:
                            debug_output += "❌ Fallo: OCR directo no produjo texto.\n"
                            return (*_pad_data(extracted_data_raw), debug_output)

                    except Exception as e:
                        debug_output += f"❌ ERROR: Falló la rasterización/OCR directo: {e}\n"
                        return (*_pad_data(extracted_data_raw), debug_output)
                else:
                    debug_output += "❌ ERROR: OCR (Tesseract/PIL) no disponible.\n"
                    return (*_pad_data(extracted_data_raw), debug_output)


        # Si todavía no hay líneas (fallo total), salimos
        if not lines:
            debug_output += "Error: No se pudo leer texto del documento (después de todos los intentos)."
            return (*_pad_data(extracted_data_raw), debug_output)

        # Captura de debug
        if debug_mode:
            debug_output += "🔍 DEBUG MODE ACTIVATED: Showing all lines in file\n\n"
            for i, linea in enumerate(lines):
                debug_output += f"Line {i:02d}: {linea}\n" 
            debug_output += "\n"


        # 3. Mapeo e Importación Dinámica del Extractor
        full_class_path = find_extractor_for_file(pdf_path) 

        doc_path_for_extractor = pdf_path 
        
        if full_class_path:
            debug_output += f"➡️ Extractor encontrado en mapeo: {full_class_path}\n"
            try:
                module_path, class_name = full_class_path.rsplit('.', 1)
                module = importlib.import_module(module_path)
                ExtractorClass = getattr(module, class_name)
                
                extractor = ExtractorClass(lines, doc_path_for_extractor) 
                extracted_data_raw = extractor.extract_all()
                
                return (*_pad_data(extracted_data_raw), debug_output)
                
            except Exception as e:
                debug_output += f"❌ ERROR: Falló la ejecución del extractor para '{full_class_path}'. Error: {e}\n"
                pass 
        
        # 4. Extractor Genérico (Fallback)
        debug_output += "➡️ No specific invoice type detected or specific extractor failed. Using generic extraction function.\n"
        generic_extractor = BaseInvoiceExtractor(lines, doc_path_for_extractor)
        extracted_data_raw = generic_extractor.extract_all()
        
        return (*_pad_data(extracted_data_raw), debug_output)
        
    finally:
        # 🚨 LIMPIEZA FINAL: Eliminamos la imagen temporal de la rasterización
        if temp_img_to_delete and os.path.exists(temp_img_to_delete):
            try:
                os.remove(temp_img_to_delete)
            except Exception as e:
                print(f"Advertencia: No se pudo eliminar la imagen temporal OCR: {temp_img_to_delete}. Error: {e}")

# ----------------------------------------------------------------------
# FUNCIÓN DE EJECUCIÓN (run_extraction)
# ----------------------------------------------------------------------

def run_extraction(ruta_input: str, debug_mode: bool) -> Tuple[List[Dict[str, Any]], str]:
    """ Procesa archivos, incluyendo la división condicional de PDFs. """
    
    if not ruta_input:
        messagebox.showerror("Error", "Debe seleccionar un archivo o directorio para procesar.")
        return [], "" 

    all_pdfs_to_process: List[str] = [] 
    SUPPORTED_EXTENSIONS = ('.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.tif')

    if os.path.isdir(ruta_input):
        
        for root, dirs, files in os.walk(ruta_input):
            if "facturas_Procesadas" in dirs:
                dirs.remove("facturas_Procesadas")
            
            for file in files:
                file_path = os.path.join(root, file)
                if file.lower().endswith(SUPPORTED_EXTENSIONS):
                    if file.lower().endswith('.pdf'):
                        try:
                            # Se usa PyPDF2 aquí solo para contar páginas, NO para extraer texto
                            with open(file_path, 'rb') as f:
                                pdf_reader = PyPDF2.PdfReader(f)
                                num_pages = len(pdf_reader.pages)

                            # 🚨 LÓGICA DE DIVISIÓN CONDICIONAL 🚨
                            is_pradilla = "pradilla" in file.lower()
                            
                            if num_pages > 1 and is_pradilla: # Solo dividir Pradilla si es multi-página
                                original_dir = os.path.dirname(file_path)
                                processed_dir = os.path.join(original_dir, "facturas_Procesadas")
                                os.makedirs(processed_dir, exist_ok=True)
                                
                                pages_paths = split_pdf_into_single_page_files(file_path, original_dir)
                                all_pdfs_to_process.extend(pages_paths)
                                
                                try:
                                    shutil.move(file_path, processed_dir)
                                except Exception as move_error:
                                     print(f"Advertencia: No se pudo mover '{file}' a facturas_Procesadas. Error: {move_error}")
                                continue
                            else:
                                all_pdfs_to_process.append(file_path) # Archivos que no se dividen
                        except Exception:
                            all_pdfs_to_process.append(file_path)
                    else:
                        all_pdfs_to_process.append(file_path) # Imágenes
    
    elif os.path.isfile(ruta_input):
        if ruta_input.lower().endswith(SUPPORTED_EXTENSIONS):
            if ruta_input.lower().endswith('.pdf'):
                try:
                    with open(ruta_input, 'rb') as f:
                        pdf_reader = PyPDF2.PdfReader(f)
                        num_pages = len(pdf_reader.pages)

                    # 🚨 LÓGICA DE DIVISIÓN CONDICIONAL 🚨
                    is_pradilla = "pradilla" in os.path.basename(ruta_input).lower()
                    
                    if num_pages > 1 and is_pradilla: # Solo dividir Pradilla si es multi-página
                        original_dir = os.path.dirname(ruta_input)
                        processed_dir = os.path.join(original_dir, "facturas_Procesadas")
                        os.makedirs(processed_dir, exist_ok=True)
                        pages_paths = split_pdf_into_single_page_files(ruta_input, original_dir)
                        all_pdfs_to_process.extend(pages_paths)
                        
                        try:
                            shutil.move(ruta_input, processed_dir)
                        except Exception as move_error:
                             print(f"Advertencia: No se pudo mover '{os.path.basename(ruta_input)}' a facturas_Procesadas. Error: {move_error}")
                    else:
                        all_pdfs_to_process.append(ruta_input)
                except Exception:
                    all_pdfs_to_process.append(ruta_input)
            else:
                all_pdfs_to_process.append(ruta_input)
    
    if not all_pdfs_to_process:
        messagebox.showwarning("Advertencia", "No se encontraron archivos PDF o de imagen válidos para procesar en la ruta seleccionada.")
        return [], ""

    all_extracted_rows_with_debug: List[Dict[str, Any]] = []

    def format_numeric_value(value, is_currency: bool = True) -> str:
        if value is None:
            return 'No encontrado'
        try:
            numeric_val = float(str(value).replace(',', '.').replace('€', '').strip()) 
            formatted = f"{numeric_val:.2f}"
            if is_currency:
                return f"{formatted} €".replace('.', ',')
            return formatted.replace('.', ',')
        except ValueError:
            return str(value)

    # PROCESAMIENTO PRINCIPAL
    for archivo_a_procesar in all_pdfs_to_process:
        
        initial_file_to_process = archivo_a_procesar 
        tipo, fecha, numero_factura, emisor, cliente, cif, modelo, matricula, importe, base_imponible, iva, tasas, debug_output = extraer_datos(initial_file_to_process, debug_mode)
        
        
        final_path_on_disk = initial_file_to_process
        display_filename_in_csv = os.path.basename(initial_file_to_process)
        
        if tipo == "ERROR_EXTRACCION":
             print(f"❌ Error: Falló la extracción para {os.path.basename(initial_file_to_process)}")
             continue

        file_extension = os.path.splitext(initial_file_to_process)[1].lower()
        if file_extension in ['.jpg', '.jpeg', '.png', '.tiff', '.tif']:
            original_image_path = initial_file_to_process
            image_dir = os.path.dirname(original_image_path)
            img_procesada_dir = os.path.join(image_dir, "imgProcesada")
            os.makedirs(img_procesada_dir, exist_ok=True)
             
            try:
                # Mueve la imagen original
                shutil.move(original_image_path, os.path.join(img_procesada_dir, os.path.basename(original_image_path)))
            except shutil.Error:
                pass


        current_row = {
            'Archivo': display_filename_in_csv.replace(',', '') ,
            '__OriginalPath__': final_path_on_disk,
            'Tipo': tipo or 'No encontrado',
            'Fecha': fecha or 'No encontrada',
            'Número de Factura': numero_factura or 'No encontrado',
            'Emisor': emisor or 'No encontrado',
            'Cliente': cliente or 'No encontrado',
            'CIF': cif or 'No encontrado',
            'Modelo': modelo or 'No encontrado',
            'Matricula': matricula or 'No encontrado',
            "Base": format_numeric_value(base_imponible, is_currency=False),
            "IVA": format_numeric_value(iva, is_currency=False),
            'Importe': format_numeric_value(importe, is_currency=True),
            'Tasas': format_numeric_value(tasas, is_currency=False),
            'DebugLines': debug_output 
        }
        all_extracted_rows_with_debug.append(current_row)

    unique_rows_csv = []
    seen_combinations = set()

    for row_with_debug in all_extracted_rows_with_debug:
        row_csv = row_with_debug.copy()
        row_csv.pop('DebugLines', None) 
        row_csv.pop('__OriginalPath__', None)

        row_tuple = tuple(sorted((k, v) for k, v in row_csv.items() if k != 'Archivo'))
        if row_tuple not in seen_combinations:
            seen_combinations.add(row_tuple)
            unique_rows_csv.append(row_csv)

    output_dir = os.path.dirname(ruta_input) if os.path.isfile(ruta_input) else ruta_input
    csv_output_path = os.path.join(output_dir, 'facturas_resultado.csv')
    
    try:
        with open(csv_output_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
            fieldnames = ['Archivo', 'Tipo', 'Fecha', 'Número de Factura', 'Emisor', 'Cliente', 'CIF', 'Modelo', 'Matricula', "Base", "IVA", 'Importe', 'Tasas']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=';')
            writer.writeheader()
            writer.writerows(unique_rows_csv)

    except Exception as e:
        messagebox.showerror("Error al escribir CSV", f"No se pudo escribir el archivo CSV: {e}")
        return [], ""
    
    return all_extracted_rows_with_debug, csv_output_path


# --- Interfaz Gráfica (Tkinter) (InvoiceApp) ---
class InvoiceApp:
    def __init__(self, master):
        self.master = master
        master.title("Extractor de Facturas v2.1 (con Acciones)")
        
        self.ruta_input_var = tk.StringVar(value="")
        self.debug_mode_var = tk.BooleanVar(value=False)
        self.debug_mode_var.trace_add("write", self._on_debug_mode_change)
        
        self.tree: Optional[ttk.Treeview] = None
        self.debug_text_area: Optional[ScrolledText] = None
        self.button_call_generator: Optional[tk.Button] = None 
        self.button_launch_file: Optional[tk.Button] = None    
        # 🚨 CAMBIO 1: Incluir todos los campos en la tabla
        self.columns = ['Archivo', 'Tipo', 'Fecha', 'Número de Factura', 'Emisor', 'Cliente', 'CIF', 'Modelo', 'Matricula', 'Base', 'IVA', 'Importe', 'Tasas'] 

        self.results_data: List[Dict[str, Any]] = []

        self.create_widgets()
        
    def _on_debug_mode_change(self, *args):
        if self.tree and self.button_call_generator and self.tree.get_children():
            if self.debug_mode_var.get() == False:
                self.button_call_generator['state'] = tk.DISABLED
            else:
                self.button_call_generator['state'] = tk.NORMAL

    def create_widgets(self):
        frame_ruta = tk.Frame(self.master, padx=10, pady=10); frame_ruta.pack(fill='x')
        tk.Label(frame_ruta, text="Ruta a Fichero o Directorio:").pack(side='left', padx=(0, 10))
        self.entry_ruta = tk.Entry(frame_ruta, textvariable=self.ruta_input_var, width=50); self.entry_ruta.pack(side='left', fill='x', expand=True, padx=(0, 10))
        tk.Button(frame_ruta, text="Seleccionar...", command=self.select_path).pack(side='left')

        frame_controls = tk.Frame(self.master, padx=10, pady=5); frame_controls.pack(fill='x')
        tk.Checkbutton(frame_controls, text="Modo Debug (capturar líneas de texto)", variable=self.debug_mode_var).pack(side='left', anchor='w')
        tk.Button(frame_controls, text="INICIAR EXTRACCIÓN", command=self.execute_extraction, bg="green", fg="white", font=('Arial', 12, 'bold')).pack(side='right')

        results_frame = tk.LabelFrame(self.master, text="Resultados de la Extracción (facturas_resultado.csv)", padx=5, pady=5); results_frame.pack(fill='both', expand=True, padx=10, pady=(10, 5))
        self.tree = ttk.Treeview(results_frame, columns=self.columns, show='headings', selectmode='browse')
        for col in self.columns:
            self.tree.heading(col, text=col); 
            # 🚨 CAMBIO 2: Ajustar anchos para más columnas
            width = 150 if col == 'Archivo' else (60 if col in ['Tipo', 'IVA', 'Tasas'] else (80 if col in ['Base', 'Importe', 'Fecha'] else 100))
            self.tree.column(col, anchor='w', width=width)
        
        vsb = ttk.Scrollbar(results_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side='right', fill='y')
        self.tree.pack(side='top', fill='both', expand=True)
        self.tree.bind('<<TreeviewSelect>>', self.show_debug_info)

        debug_frame = tk.LabelFrame(self.master, text="Detalle de Líneas Procesadas y Acciones", padx=5, pady=5); debug_frame.pack(fill='x', padx=10, pady=(5, 10))
        self.debug_text_area = ScrolledText(debug_frame, height=8, wrap=tk.WORD, state=tk.DISABLED, font=('Consolas', 9)); self.debug_text_area.pack(side='top', fill='both', expand=True)
        
        action_frame = tk.Frame(debug_frame)
        action_frame.pack(side='bottom', fill='x', pady=(5, 0))

        self.button_launch_file = tk.Button(action_frame, text="➡️ Abrir Archivo Asociado (PDF/Imagen)", command=self.launch_associated_file, bg='#ADD8E6', state=tk.DISABLED)
        self.button_launch_file.pack(side='left', fill='x', expand=True, padx=(0, 5))
        
        self.button_call_generator = tk.Button(action_frame, text="Llamar al Generador de Extractores", command=self.call_external_program_template, bg='#F08080', state=tk.DISABLED)
        self.button_call_generator.pack(side='right', fill='x', expand=True, padx=(5, 0))


    def select_path(self):
        dir_path = filedialog.askdirectory(title="Seleccionar Directorio con Facturas")
        if dir_path:
            self.ruta_input_var.set(dir_path)
            return
        
        file_path = filedialog.askopenfilename(
            title="Seleccionar Archivo de Factura (PDF/Imagen)",
            filetypes=[
                ("Archivos Soportados", "*.pdf *.jpg *.jpeg *.png *.tiff *.tif"),
                ("Archivos PDF", "*.pdf"),
                ("Archivos de Imagen", "*.jpg *.jpeg *.png *.tiff *.tif"),
                ("Todos los Archivos", "*.*")
            ]
        )
        if file_path:
            self.ruta_input_var.set(file_path)

    def _update_action_buttons_state(self):
        has_results = bool(self.results_data)
        is_debug_on = self.debug_mode_var.get()
        
        self.button_launch_file['state'] = tk.NORMAL if has_results and self.tree.selection() else tk.DISABLED
        
        if has_results and is_debug_on:
            self.button_call_generator['state'] = tk.NORMAL
        else:
            self.button_call_generator['state'] = tk.DISABLED

    def execute_extraction(self):
        ruta = self.ruta_input_var.get()
        debug = self.debug_mode_var.get()
        
        if not ruta:
            messagebox.showerror("Error", "Debe seleccionar un archivo o directorio.")
            return

        self.results_data = []
        self.tree.delete(*self.tree.get_children())
        
        if self.debug_text_area:
             self.debug_text_area.config(state=tk.NORMAL)
             self.debug_text_area.delete('1.0', tk.END)
             self.debug_text_area.insert(tk.END, "Ejecutando la extracción...")
             self.debug_text_area.config(state=tk.DISABLED)
        
        self.master.config(cursor="wait")
        self.entry_ruta.config(state='disabled')
        
        try:
            all_extracted_rows_with_debug, csv_output_path = run_extraction(ruta, debug)
            self.results_data = all_extracted_rows_with_debug 
            
            for i, row in enumerate(self.results_data):
                # Usar todas las columnas definidas
                display_values = [row.get(col, 'N/A') for col in self.columns]
                self.tree.insert('', tk.END, iid=i, values=display_values)

            if all_extracted_rows_with_debug:
                 messagebox.showinfo("¡Éxito!", f"Proceso completado. Resultados visibles y escritos en: {csv_output_path}")
            else:
                 messagebox.showwarning("Advertencia", "Extracción finalizada, pero no se procesaron archivos o no se encontraron datos válidos.")

        except Exception as e:
            messagebox.showerror("Error de Ejecución", f"Ha ocurrido un error durante la extracción: {e}")
            
        finally:
            self.master.config(cursor="")
            self.entry_ruta.config(state='normal')
            self._update_action_buttons_state() 
            if self.debug_text_area:
                 self.debug_text_area.config(state=tk.NORMAL)
                 self.debug_text_area.delete('1.0', tk.END)
                 self.debug_text_area.insert(tk.END, "Extracción finalizada. Seleccione una fila para ver el detalle de las líneas.")
                 self.debug_text_area.config(state=tk.DISABLED)

    def show_debug_info(self, event):
        selected_items = self.tree.selection()
        
        self.debug_text_area.config(state=tk.NORMAL)
        self.debug_text_area.delete('1.0', tk.END)
        
        if not selected_items:
            self.debug_text_area.insert(tk.END, "Seleccione una fila para ver el detalle de las líneas procesadas.")
        else:
            item_id = selected_items[0] 
            data_index = int(item_id)
            
            if 0 <= data_index < len(self.results_data):
                row = self.results_data[data_index]
                debug_lines = row.get('DebugLines', 'No hay información de debug disponible.')
                
                summary = (
                    f"--- RESUMEN DE EXTRACCIÓN ---\n"
                    f"Archivo: {row.get('Archivo')}\n"
                    f"Nº Factura: {row.get('Número de Factura')}\n"
                    f"Emisor: {row.get('Emisor')}\n"
                    f"Importe: {row.get('Importe')}\n"
                    f"---------------------------\n\n"
                )
                
                self.debug_text_area.insert(tk.END, summary)
                
                if self.debug_mode_var.get():
                     self.debug_text_area.insert(tk.END, debug_lines)
                else:
                    self.debug_text_area.insert(tk.END, "El Modo Debug no estaba activado. Las líneas de texto del PDF no fueron capturadas durante la extracción.\n\nActive el checkbox 'Modo Debug' y ejecute de nuevo para ver este detalle.")

        self.debug_text_area.config(state=tk.DISABLED)
        self._update_action_buttons_state()

    def launch_associated_file(self):
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("Advertencia", "Seleccione primero una factura en la tabla de resultados.")
            return

        item_id = selected_items[0] 
        data_index = int(item_id)
        
        if 0 <= data_index < len(self.results_data):
            row = self.results_data[data_index]
            file_path = row.get('__OriginalPath__')
            
            if not file_path or not os.path.exists(file_path):
                messagebox.showerror("Error", f"Ruta de archivo no encontrada o archivo inexistente: {file_path}")
                return

            try:
                if sys.platform == "win32":
                    os.startfile(file_path)
                elif sys.platform == "darwin":
                    subprocess.run(['open', file_path], check=True)
                else:
                    subprocess.run(['xdg-open', file_path], check=True)

            except Exception as e:
                messagebox.showerror("Error al abrir", f"No se pudo abrir el archivo:\n{file_path}\nError: {e}")
        else:
            messagebox.showerror("Error", "Error interno al recuperar la información del archivo.")

    
    def call_external_program_template(self):
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("Advertencia", "Seleccione primero una factura en la tabla de resultados.")
            return
            
        item_id = selected_items[0] 
        data_index = int(item_id)
        
        if 0 <= data_index < len(self.results_data):
            row = self.results_data[data_index]
            
            ruta_archivo = row.get('__OriginalPath__', None)
            
            if not ruta_archivo or not os.path.exists(ruta_archivo):
                messagebox.showerror("Error", f"Ruta de archivo no válida o inexistente: {ruta_archivo}")
                return
            
            # 🚨 CAMBIO 3: Recuperar todos los campos y DebugLines
            tipo = str(row.get('Tipo', ''))
            fecha = str(row.get('Fecha', ''))
            num_factura = str(row.get('Número de Factura', ''))
            emisor = str(row.get('Emisor', ''))
            cliente = str(row.get('Cliente', ''))
            cif = str(row.get('CIF', '')) 
            modelo = str(row.get('Modelo', ''))
            matricula = str(row.get('Matricula', ''))
            base = str(row.get('Base', ''))
            iva = str(row.get('IVA', ''))
            importe = str(row.get('Importe', ''))
            tasas = str(row.get('Tasas', ''))
            debug_lines = str(row.get('DebugLines', '')) # AHORA PASAMOS EL TEXTO COMPLETO
            nombre_base_archivo = os.path.splitext(os.path.basename(ruta_archivo))[0]
            
            
            confirmar = messagebox.askyesno(
                "Confirmar llamada al Generador",
                f"Se va a lanzar el Generador de Extractores con el archivo:\n\n{os.path.basename(ruta_archivo)}\n\n¿Desea continuar y precargar los datos?"
            )
            
            if not confirmar:
                return 
            
            try:
                # 🚨 ARGUMENTOS ACTUALIZADOS (15 TOTALES)
                comando = [
                    sys.executable, 
                    'extractor_generator_gui.py', 
                    ruta_archivo,              # 1
                    nombre_base_archivo,       # 2 (Extractor Name Suggestion)
                    debug_lines,               # 3 (Debug Lines)
                    tipo,                      # 4
                    fecha,                     # 5
                    num_factura,               # 6
                    emisor,                    # 7
                    cliente,                   # 8
                    cif,                       # 9
                    modelo,                    # 10
                    matricula,                 # 11
                    base,                      # 12
                    iva,                       # 13
                    importe,                   # 14
                    tasas                      # 15
                ]
                
                subprocess.Popen(comando)
                messagebox.showinfo("Llamada Exitosa", "Se ha lanzado el programa 'extractor_generator_gui.py'.")

            except Exception as e:
                messagebox.showerror("Error de Ejecución", f"No se pudo ejecutar 'extractor_generator_gui.py'.\nError: {e}")


# --- PUNTO DE ENTRADA ---
if __name__ == "__main__":
    if len(sys.argv) > 1:
        print("Ejecutando en modo CLI (Command Line Interface)...")
        
    root = tk.Tk()
    app = InvoiceApp(root)
    root.mainloop()