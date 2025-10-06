import os
import re
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from typing import Dict, List, Tuple, Any
import PyPDF2              # NECESARIO PARA LEER PDFS
import importlib.util      # NECESARIO PARA IMPORTACIÓN DINÁMICA

# --- CONFIGURACIÓN DE RUTAS ---
MAIN_FILE = 'main_extractor_gui.py'
EXTRACTORS_DIR = 'extractors'

# Asumimos que utils y BaseInvoiceExtractor existen en el PATH
# NOTA: Para que esto funcione, la carpeta 'extractors' debe contener 
# el archivo 'base_invoice_extractor.py' y los módulos 'utils' deben estar accesibles.

# --- LÓGICA DE LECTURA DE PDF SIMPLIFICADA ---
def _get_pdf_lines(pdf_path: str) -> List[str]:
    """Lee un PDF y devuelve una lista de líneas de texto."""
    lines: List[str] = []
    try:
        with open(pdf_path, 'rb') as archivo:
            pdf = PyPDF2.PdfReader(archivo)
            texto = ''
            for pagina in pdf.pages:
                texto += pagina.extract_text() or ''
            lines = texto.splitlines()
        return lines
    except Exception as e:
        messagebox.showerror("Error de Lectura PDF", f"No se pudo leer el archivo PDF: {e}")
        return []


# --- PLANTILLA DEL NUEVO EXTRACTOR (.py) (IDÉNTICA A LA ANTERIOR) ---
EXTRACTOR_TEMPLATE = """\
import re
import os
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from utils import _extract_amount, _extract_nif_cif, _calculate_base_from_total, VAT_RATE

class {extractor_class_name}(BaseInvoiceExtractor):
    # CIF del emisor: {emisor_cif}
    EMISOR_CIF = "{emisor_cif}"
    EMISOR_NAME = "{emisor_name}"

    def __init__(self, lines, pdf_path):
        super().__init__(lines, pdf_path)
        self.cif = self.EMISOR_CIF
        self.emisor = self.EMISOR_NAME
        self.vat_rate = VAT_RATE

    # --- Métodos de Extracción --
    
    def _extract_emisor(self):
        # El emisor está fijo
        self.emisor = self.EMISOR_NAME

    def _extract_cif(self):
        # El CIF ya está fijado
        pass

    def _extract_cliente(self):
        # Sugerencia automática: Cliente en la Línea {client_line_num}
        # Línea: {client_line_content}
        if len(self.lines) > {client_line_num}:
            self.cliente = self.lines[{client_line_num}].strip()

    def _extract_nif_cif_cliente(self):
        # Sugerencia automática: CIF/NIF del Cliente en la Línea {client_cif_line_num}
        # Línea: {client_cif_line_content}
        if len(self.lines) > {client_cif_line_num}:
            line = self.lines[{client_cif_line_num}]
            match = re.search(r'\b[A-Z0-9]{8,10}\b', line)
            if match:
                self.nif_cif = match.group(0).strip()

    def _extract_numero_factura(self):
        # Sugerencia automática: Número de Factura en la Línea {invoice_line_num}
        # Línea: {invoice_line_content}
        if len(self.lines) > {invoice_line_num}:
            line = self.lines[{invoice_line_num}]
            # Patrón genérico de número de factura (Ajustar si es necesario)
            match = re.search(r'([A-Z0-9./-]+)', line) 
            if match:
                self.numero_factura = match.group(1).strip()
        
    def _extract_fecha(self):
        # Sugerencia automática: Fecha en la Línea {date_line_num}
        # Línea: {date_line_content}
        if len(self.lines) > {date_line_num}:
            line = self.lines[{date_line_num}]
            # Patrón genérico de fecha DD/MM/YYYY o DD-MM-YYYY
            match = re.search(r'(\d{2}[/\-]\d{2}[/\-]\d{4})', line)
            if match:
                self.fecha = match.group(1).replace('-', '/').strip()

    def _extract_modelo(self):
        # Extracción genérica de modelo.
        pass

    def _extract_matricula(self):
        # Extracción de matrícula.
        pass

    def _extract_importe_and_base(self):
        # Sugerencia automática: Base en Línea {base_line_num} y Total en Línea {total_line_num}
        # Línea Base: {base_line_content}
        # Línea Total: {total_line_content}
        
        # Extracción del TOTAL
        if len(self.lines) > {total_line_num}:
            total_line = self.lines[{total_line_num}]
            self.importe = _extract_amount(total_line)
            
        # Extracción de la Base Imponible
        if len(self.lines) > {base_line_num}:
             base_line = self.lines[{base_line_num}]
             self.base_imponible = _extract_amount(base_line)
             
        # Fallback de cálculo
        if self.importe and not self.base_imponible:
            self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)

"""

# --- PARSEAR Y MODIFICAR EL CÓDIGO PRINCIPAL (IDÉNTICO A LA ANTERIOR) ---
def update_main_mapping(keyword: str, class_path: str) -> bool:
    # ... (La implementación de update_main_mapping es la misma) ...
    try:
        with open(MAIN_FILE, 'r') as f:
            content = f.read()
        
        start_pattern = re.compile(r'EXTRACTION_MAPPING\s*=\s*{', re.IGNORECASE)
        match_start = start_pattern.search(content)
        
        if not match_start:
            return False

        end_pattern = re.compile(r'}\s*\n', re.IGNORECASE)
        content_after_start = content[match_start.end():]
        match_end = end_pattern.search(content_after_start)
        
        if not match_end:
            return False

        insert_index = match_start.end() + match_end.start() - 1 
        new_entry = f'\n    "{keyword}": "{class_path}",'
        
        new_content = content[:insert_index] + new_entry + content[insert_index:]

        with open(MAIN_FILE, 'w') as f:
            f.write(new_content)
            
        return True

    except Exception:
        return False


# --- CLASE DE LA INTERFAZ GRÁFICA ---

class ExtractorGeneratorApp:
    def __init__(self, master):
        self.master = master
        master.title("Generador y Debugger de Extractores (v2.0)")
        # 🚨 SOLUCIÓN #1: Inicializar la variable de control
        self.ruta_input_var = tk.StringVar()
        # 🚨 NUEVAS VARIABLES PARA PRECARGA DE DATOS
        self.num_factura_var = tk.StringVar()
        self.emisor_var = tk.StringVar()
        self.base_var = tk.StringVar() # Opcional, si tienes un campo para la base
        self.importe_var = tk.StringVar() # Opcional, si tienes un campo para el importe
        # 🚨 NUEVAS VARIABLES PARA CIF Y NOMBRE DE PLANTILLA
        self.cif_var = tk.StringVar() # Nuevo
        self.template_name_var = tk.StringVar() # Nuevo (para el nombre del archivo del extractor)
        
        # Variables de entrada
        self.emisor_name_var = tk.StringVar()
        self.emisor_cif_var = tk.StringVar()
        self.keyword_var = tk.StringVar()
        self.file_name_var = tk.StringVar()
        self.class_name_var = tk.StringVar()

        # Variables para los números de línea
        self.l_invoice_var = tk.StringVar()
        self.l_date_var = tk.StringVar()
        self.l_total_var = tk.StringVar()
        self.l_base_var = tk.StringVar()
        self.l_client_var = tk.StringVar()
        self.l_client_cif_var = tk.StringVar()
        
        # Variables de Debug
        self.test_pdf_path_var = tk.StringVar()
        self.test_results_var = tk.StringVar(value="[Aún no se ha ejecutado el extractor]")


        self.create_widgets()
        
    def create_widgets(self):
        main_frame = tk.Frame(self.master, padx=10, pady=10)
        main_frame.pack(fill='both', expand=True)

        # --- SECCIÓN 1, 2, 3: GENERACIÓN (Idéntico a la versión anterior) ---
        
        # 1. Metadatos
        meta_frame = tk.LabelFrame(main_frame, text="1. Metadatos del Nuevo Extractor", padx=10, pady=10)
        meta_frame.pack(fill='x', pady=(0, 10))
        self._create_labeled_entry(meta_frame, "Nombre Emisor:", self.emisor_name_var, 0, self._update_keyword)
        self._create_labeled_entry(meta_frame, "CIF Emisor:", self.emisor_cif_var, 1)
        tk.Label(meta_frame, text="Clave/Fichero/Clase:").grid(row=2, column=0, sticky='w', pady=2)
        tk.Entry(meta_frame, textvariable=self.keyword_var, state='readonly', width=15).grid(row=2, column=1, sticky='w', padx=5)
        tk.Entry(meta_frame, textvariable=self.file_name_var, state='readonly', width=20).grid(row=2, column=2, sticky='w', padx=5)
        tk.Entry(meta_frame, textvariable=self.class_name_var, state='readonly', width=20).grid(row=2, column=3, sticky='w', padx=5)

        # 2. Líneas de Salida
        tk.Label(main_frame, text="2. Salida de Líneas del PDF (Line 0: ...):").pack(anchor='w', pady=(5, 2))
        self.lines_text_area = scrolledtext.ScrolledText(main_frame, height=8, wrap=tk.WORD)
        self.lines_text_area.pack(fill='x', pady=(0, 10))

        # 3. Índices de Línea
        index_frame = tk.LabelFrame(main_frame, text="3. Números de Línea (Índice)", padx=10, pady=10)
        index_frame.pack(fill='x', pady=(0, 10))
        self._create_labeled_entry(index_frame, "Línea Factura:", self.l_invoice_var, 0, column=0)
        self._create_labeled_entry(index_frame, "Línea Fecha:", self.l_date_var, 0, column=2)
        self._create_labeled_entry(index_frame, "Línea TOTAL:", self.l_total_var, 1, column=0)
        self._create_labeled_entry(index_frame, "Línea BASE:", self.l_base_var, 1, column=2)
        self._create_labeled_entry(index_frame, "Línea Cliente:", self.l_client_var, 2, column=0)
        self._create_labeled_entry(index_frame, "Línea CIF Cliente:", self.l_client_cif_var, 2, column=2)
        
        # Botón de Generación
        tk.Button(main_frame, text="GENERAR EXTRACTOR", command=self.generate_and_update, bg="darkgreen", fg="white", font=('Arial', 10, 'bold')).pack(pady=5, fill='x')
        
        # --- SECCIÓN 4: DEBUG Y TESTEO (NUEVO) ---
        test_frame = tk.LabelFrame(main_frame, text="4. Probar Extractor Generado (DEBUG)", padx=10, pady=10)
        test_frame.pack(fill='x', pady=(10, 0))

        # Selector de PDF
        ruta_frame = tk.Frame(test_frame)
        ruta_frame.pack(fill='x')
        tk.Entry(ruta_frame, textvariable=self.test_pdf_path_var, width=50).pack(side='left', fill='x', expand=True, padx=(0, 5))
        tk.Button(ruta_frame, text="Seleccionar PDF", command=self._select_test_pdf).pack(side='left')

        # Botón de Prueba
        tk.Button(test_frame, text="EJECUTAR PRUEBA", command=self._test_extraction, bg="orange", fg="black", font=('Arial', 10, 'bold')).pack(pady=(10, 5), fill='x')

        # Resultados
        tk.Label(test_frame, text="Resultados de la Extracción:").pack(anchor='w')
        self.results_label = tk.Label(test_frame, textvariable=self.test_results_var, justify=tk.LEFT, anchor='w', relief=tk.SUNKEN, bd=1, padx=5, pady=5)
        self.results_label.pack(fill='x')


    def _create_labeled_entry(self, parent, label_text, var, row, command=None, column=0):
        # ... (Función auxiliar es la misma) ...
        tk.Label(parent, text=label_text).grid(row=row, column=column, sticky='w', padx=5, pady=2)
        entry = tk.Entry(parent, textvariable=var, width=15)
        entry.grid(row=row, column=column + 1, sticky='w', padx=5, pady=2)
        if command:
            var.trace_add("write", lambda *args: command())
        return entry


    def _update_keyword(self):
        # ... (Función de keyword es la misma) ...
        emisor = self.emisor_name_var.get().strip()
        if emisor:
            keyword = emisor.lower().replace(" ", "_").split("_")[0]
            class_name = f"{keyword.capitalize()}Extractor"
            file_name = f"{keyword}_extractor.py"
            self.keyword_var.set(keyword)
            self.file_name_var.set(file_name)
            self.class_name_var.set(class_name)
        else:
            self.keyword_var.set("")
            self.file_name_var.set("")
            self.class_name_var.set("")


    def _parse_lines(self) -> List[str]:
        # ... (Función de parseo de líneas es la misma) ...
        raw_lines = self.lines_text_area.get("1.0", tk.END).strip()
        parsed_lines: List[str] = []
        for line in raw_lines.splitlines():
            match = re.search(r'Line\s*\d+:\s*(.*)', line)
            if match:
                parsed_lines.append(match.group(1).strip())
        return parsed_lines

    def generate_and_update(self):
        # ... (Función de generación es la misma) ...
        # [Se mantiene el código de validación y generación]
        try:
            emisor_name = self.emisor_name_var.get().strip()
            emisor_cif = self.emisor_cif_var.get().strip()
            keyword = self.keyword_var.get()
            
            parsed_lines = self._parse_lines()
            num_lines = len(parsed_lines)

            if not emisor_name or not emisor_cif or not keyword or not parsed_lines:
                messagebox.showerror("Error de Validación", "Por favor, complete los campos de Emisor y pegue las líneas de salida del PDF.")
                return

            line_data = {
                'invoice': int(self.l_invoice_var.get()),
                'date': int(self.l_date_var.get()),
                'total': int(self.l_total_var.get()),
                'base': int(self.l_base_var.get()),
                'client': int(self.l_client_var.get()),
                'client_cif': int(self.l_client_cif_var.get()),
            }
            
            for key, val in line_data.items():
                if val < 0 or val >= num_lines:
                    messagebox.showerror("Error de Línea", f"El índice para '{key}' ({val}) está fuera de rango (0 a {num_lines-1}).")
                    return

        except ValueError:
            messagebox.showerror("Error de Formato", "Asegúrese de que todos los campos de 'Número de Línea' contengan solo números enteros.")
            return
        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un error inesperado al leer los datos: {e}")
            return
        
        # Generar contenido
        try:
            extractor_filename = self.file_name_var.get()
            extractor_class_name = self.class_name_var.get()
            extractor_path = os.path.join(EXTRACTORS_DIR, extractor_filename)
            class_path_mapping = f"extractors.{keyword}_extractor.{extractor_class_name}"

            new_extractor_content = EXTRACTOR_TEMPLATE.format(
                extractor_class_name=extractor_class_name,
                emisor_cif=emisor_cif,
                emisor_name=emisor_name,
                invoice_line_num=line_data['invoice'], invoice_line_content=parsed_lines[line_data['invoice']],
                date_line_num=line_data['date'], date_line_content=parsed_lines[line_data['date']],
                total_line_num=line_data['total'], total_line_content=parsed_lines[line_data['total']],
                base_line_num=line_data['base'], base_line_content=parsed_lines[line_data['base']],
                client_line_num=line_data['client'], client_line_content=parsed_lines[line_data['client']],
                client_cif_line_num=line_data['client_cif'], client_cif_line_content=parsed_lines[line_data['client_cif']]
            )
        except Exception as e:
            messagebox.showerror("Error de Plantilla", f"Error al formatear la plantilla: {e}")
            return

        # 3. Escribir el nuevo archivo extractor
        try:
            if not os.path.exists(EXTRACTORS_DIR):
                os.makedirs(EXTRACTORS_DIR)
                
            with open(extractor_path, 'w') as f:
                f.write(new_extractor_content)
            
        except Exception as e:
            messagebox.showerror("Error de Escritura", f"Error al escribir el archivo extractor: {e}")
            return

        # 4. Modificar el código principal
        if update_main_mapping(keyword, class_path_mapping):
            messagebox.showinfo("¡Éxito!", f"✅ Extractor '{extractor_filename}' creado y {MAIN_FILE} actualizado.\n\n"
                                "💡 ¡Continúa con la Sección 4 para probarlo!")
        else:
            messagebox.showwarning("Advertencia", f"El extractor se creó, pero falló la actualización de {MAIN_FILE}. ¡Hazlo manualmente!")
            
    # --- FUNCIONES DE DEBUGGING (NUEVO) ---

    def _select_test_pdf(self):
        """Abre un diálogo para seleccionar el PDF de prueba."""
        file_path = filedialog.askopenfilename(
            title="Seleccionar PDF de Prueba",
            filetypes=[("Archivos PDF", "*.pdf")]
        )
        if file_path:
            self.test_pdf_path_var.set(file_path)

    def _test_extraction(self):
        """Carga el extractor generado dinámicamente y lo ejecuta sobre el PDF seleccionado."""
        keyword = self.keyword_var.get()
        class_name = self.class_name_var.get()
        pdf_path = self.test_pdf_path_var.get()
        
        if not keyword or not class_name:
            messagebox.showerror("Error", "Primero debe generar un extractor (Secciones 1-3).")
            return
            
        if not pdf_path or not os.path.exists(pdf_path):
            messagebox.showerror("Error", "Seleccione un archivo PDF de prueba válido.")
            return

        module_path = f"extractors.{keyword}_extractor"
        extractor_file_path = os.path.join(EXTRACTORS_DIR, f"{keyword}_extractor.py")
        
        if not os.path.exists(extractor_file_path):
            messagebox.showerror("Error", f"No se encontró el archivo del extractor: {extractor_file_path}. Asegúrese de haber generado el extractor.")
            return

        self.test_results_var.set("[Ejecutando...]")
        
        try:
            # 1. Lectura del PDF
            lines = _get_pdf_lines(pdf_path)
            if not lines:
                return # El error ya fue manejado en _get_pdf_lines

            # 2. Carga Dinámica del Extractor
            spec = importlib.util.spec_from_file_location(module_path, extractor_file_path)
            if spec is None:
                raise ImportError(f"No se pudo crear la especificación para el módulo {module_path}")
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            ExtractorClass = getattr(module, class_name)
            
            # 3. Ejecución del Extractor
            extractor_instance: Any = ExtractorClass(lines, pdf_path)
            
            # BaseInvoiceExtractor.extract_all() devuelve 10 campos + 2 extras, pero para la revisión
            # solo necesitamos los 10 campos principales
            tipo, fecha, numero_factura, emisor, cliente, cif, modelo, matricula, importe, base_imponible = extractor_instance.extract_all()[:10]
            
            # 4. Mostrar Resultados
            results_text = (
                f"✅ Extracción Exitosa\n"
                f"Emisor: {emisor or 'N/A'}\n"
                f"CIF Emisor: {cif or 'N/A'}\n"
                f"Cliente: {cliente or 'N/A'}\n"
                f"Nº Factura: {numero_factura or 'N/A'}\n"
                f"Fecha: {fecha or 'N/A'}\n"
                f"Importe: {importe or 'N/A'}\n"
                f"Base Imponible: {base_imponible or 'N/A'}\n"
                f"Modelo: {modelo or 'N/A'}\n"
                f"Matrícula: {matricula or 'N/A'}\n"
            )
            self.test_results_var.set(results_text)
            
        except Exception as e:
            self.test_results_var.set(f"❌ ERROR DE EJECUCIÓN:\n{type(e).__name__}: {str(e)}")
            messagebox.showerror("Error de Prueba", f"Error al ejecutar el extractor: {e}")


# --- PUNTO DE ENTRADA ---

if __name__ == "__main__":
    
    ruta_inicial_archivo = None
    datos_precarga = {}
    nombre_base_archivo = None

    # 🚨 LÓGICA PARA CAPTURAR LOS 7 ARGUMENTOS
    if len(sys.argv) > 1:
        
        # Argumento 1: Ruta del archivo
        ruta_candidata = sys.argv[1]
        if os.path.exists(ruta_candidata):
            ruta_inicial_archivo = ruta_candidata
            
        # Argumentos 2-7: Datos de precarga (si se pasaron todos)
        if len(sys.argv) >= 8:
            datos_precarga = {
                'num_factura': sys.argv[2],
                'emisor': sys.argv[3],
                'cif': sys.argv[4], # 🚨 Nuevo
                'base': sys.argv[5],
                'importe': sys.argv[6],
            }
            nombre_base_archivo = sys.argv[7] # 🚨 Nuevo
            
    # Inicializar la GUI
    root = tk.Tk()
    app = ExtractorGeneratorApp(root) 
    
    # Función auxiliar para rellenar solo si el valor no es vacío o 'No encontrado'
    def set_if_valid(tk_var, value):
        # Maneja None, cadena vacía y el valor de error de la extracción
        if value and value not in ('', 'None', 'No encontrado', 'No encontrada', 'No encontrado €'): 
            tk_var.set(value)
    
    # 🚨 1. Cargar la ruta del archivo (Mandatorio)
    if ruta_inicial_archivo:
        app.ruta_input_var.set(ruta_inicial_archivo) 
        
    # 🚨 2. Cargar los datos de precarga
    if datos_precarga:
        
        # Rellenar datos numéricos/factura
        set_if_valid(app.num_factura_var, datos_precarga.get('num_factura'))
        set_if_valid(app.base_var, datos_precarga.get('base'))
        set_if_valid(app.importe_var, datos_precarga.get('importe'))

        # 🚨 Lógica para EMISOR y CIF
        cif = datos_precarga.get('cif')
        emisor = datos_precarga.get('emisor')

        # 🚨 CIF: Prioritario
        if cif and cif not in ('', 'None', 'No encontrado'):
            app.cif_var.set(cif) # Rellenar campo CIF

        # 🚨 EMISOR: Si el emisor extraído no es válido, usar el nombre del archivo
        if emisor and emisor not in ('', 'None', 'No encontrado'):
            app.emisor_var.set(emisor) # Rellenar con el nombre extraído
        elif nombre_base_archivo:
            # Rellenar con el nombre del fichero si el emisor extraído es malo
            app.emisor_var.set(nombre_base_archivo) 
        
    # 🚨 3. Cargar el nombre de plantilla (si existe)
    if nombre_base_archivo:
        app.template_name_var.set(nombre_base_archivo.lower()) # Usar el nombre del archivo sin extensión como plantilla por defecto
        
    root.mainloop()