import os
import re
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from typing import Dict, List, Tuple, Any, Optional
import PyPDF2              # NECESARIO PARA LEER PDFS
import importlib.util      # NECESARIO PARA IMPORTACIÓN DINÁMICA

# --- CONFIGURACIÓN DE RUTAS ---
MAIN_FILE = 'main_extractor_gui.py'
EXTRACTORS_DIR = 'extractors'
MANUAL_MAPPING_FILE = 'añadir_a_EXTRACTION_MAPPING.txt'


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


# --- PLANTILLA DEL NUEVO EXTRACTOR (.py) ---
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
        line_num = {client_line_num}
        if line_num is not None and len(self.lines) > line_num:
            self.cliente = self.lines[line_num].strip()

    def _extract_nif_cif_cliente(self):
        # Sugerencia automática: CIF/NIF del Cliente en la Línea {client_cif_line_num}
        # Línea: {client_cif_line_content}
        line_num = {client_cif_line_num}
        if line_num is not None and len(self.lines) > line_num:
            line = self.lines[line_num]
            # Patrón genérico de CIF/NIF 
            match = re.search(r'\\b[A-Z0-9]{{8,10}}\\b', line) 
            if match:
                self.nif_cif = match.group(0).strip()

    def _extract_numero_factura(self):
        # Sugerencia automática: Número de Factura en la Línea {invoice_line_num}
        # Línea: {invoice_line_content}
        line_num = {invoice_line_num}
        if line_num is not None and len(self.lines) > line_num:
            line = self.lines[line_num]
            # Patrón genérico de número de factura (Ajustar si es necesario)
            match = re.search(r'([A-Z0-9./-]+)', line) 
            if match:
                self.numero_factura = match.group(1).strip()
        
    def _extract_fecha(self):
        # Sugerencia automática: Fecha en la Línea {date_line_num}
        # Línea: {date_line_content}
        line_num = {date_line_num}
        if line_num is not None and len(self.lines) > line_num:
            line = self.lines[line_num]
            # Patrón genérico de fecha
            match = re.search(r'(\\d{{2}}[/\\-]\\d{{2}}[/\\-]\\d{{4}})', line)
            if match:
                self.fecha = match.group(1).replace('-', '/').strip()

    def _extract_modelo(self):
        # Sugerencia automática (Opcional): Modelo en la Línea {modelo_line_num}
        # Línea: {modelo_line_content}
        line_num = {modelo_line_num}
        if line_num is not None and len(self.lines) > line_num:
            line = self.lines[line_num]
            # Patrón genérico para buscar el modelo (Ajustar si es necesario)
            match = re.search(r'\\b[A-Z0-9\\s]{{3,20}}\\b', line) 
            if match:
                self.modelo = match.group(0).strip()
        pass

    def _extract_matricula(self):
        # Sugerencia automática (Opcional): Matrícula en la Línea {matricula_line_num}
        # Línea: {matricula_line_content}
        line_num = {matricula_line_num}
        if line_num is not None and len(self.lines) > line_num:
            line = self.lines[line_num]
            # Patrón genérico de matrícula española
            match = re.search(r'\\b\\d{{4}}[BCDFGHJKLMNPRSTVWXYZ]{{3}}\\b', line) 
            if match:
                self.matricula = match.group(0).strip()
        pass
        
    def _extract_iva(self):
        # Sugerencia automática (Opcional): IVA (Monto) en la Línea {iva_line_num}
        # Línea: {iva_line_content}
        line_num = {iva_line_num}
        if line_num is not None and len(self.lines) > line_num:
            line = self.lines[line_num]
            # Lógica de extracción de IVA (opcional, si el campo se va a usar en BaseInvoiceExtractor)
            # self.iva = _extract_amount(line)
            pass

    def _extract_tasas(self):
        # Sugerencia automática (Opcional): Tasas/Cargos Adicionales en la Línea {tasas_line_num}
        # Línea: {tasas_line_content}
        line_num = {tasas_line_num}
        if line_num is not None and len(self.lines) > line_num:
            line = self.lines[line_num]
            # Lógica de extracción de Tasas (opcional)
            # self.tasas = _extract_amount(line)
            pass

    def _extract_importe_and_base(self):
        # Sugerencia automática: Base en Línea {base_line_num} y Total en Línea {total_line_num}
        # Línea Base: {base_line_content}
        # Línea Total: {total_line_content}
        
        # Extracción del TOTAL
        total_line_num = {total_line_num}
        if total_line_num is not None and len(self.lines) > total_line_num:
            total_line = self.lines[total_line_num]
            self.importe = _extract_amount(total_line)
            
        # Extracción de la Base Imponible
        base_line_num = {base_line_num}
        if base_line_num is not None and len(self.lines) > base_line_num:
             base_line = self.lines[base_line_num]
             self.base_imponible = _extract_amount(base_line)
             
        # Fallback de cálculo
        if self.importe and not self.base_imponible:
            self.base_imponible = _calculate_base_from_total(self.importe, self.vat_rate)

"""

# --- CLASE DE LA INTERFAZ GRÁFICA ---

class ExtractorGeneratorApp:
    def __init__(self, master):
        self.master = master
        master.title("Generador y Debugger de Extractores (v2.0)")
        
        # Variables de control se mantienen
        self.ruta_input_var = tk.StringVar()
        self.num_factura_var = tk.StringVar()
        self.emisor_var = tk.StringVar() 
        self.base_var = tk.StringVar() 
        self.importe_var = tk.StringVar()
        self.cif_var = tk.StringVar() 
        self.template_name_var = tk.StringVar() 
        
        # Variables de entrada
        self.emisor_name_var = tk.StringVar()
        self.emisor_cif_var = tk.StringVar()
        self.keyword_var = tk.StringVar()
        self.file_name_var = tk.StringVar()
        self.class_name_var = tk.StringVar()

        # Variables para los números de línea (Existentes)
        self.l_invoice_var = tk.StringVar()
        self.l_date_var = tk.StringVar()
        self.l_total_var = tk.StringVar()
        self.l_base_var = tk.StringVar()
        self.l_client_var = tk.StringVar()
        self.l_client_cif_var = tk.StringVar()
        
        # NUEVAS Variables para los números de línea (Opcionales)
        self.l_modelo_var = tk.StringVar()
        self.l_matricula_var = tk.StringVar()
        self.l_iva_var = tk.StringVar()
        self.l_tasas_var = tk.StringVar()
        
        # Variables de Debug
        self.test_pdf_path_var = tk.StringVar()
        self.test_results_var = tk.StringVar(value="[Aún no se ha ejecutado el extractor]")


        self.create_widgets()
        
    def create_widgets(self):
        main_frame = tk.Frame(self.master, padx=10, pady=10)
        main_frame.pack(fill='both', expand=True)

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

        # 3. Índices de Línea (Expandido para incluir opcionales)
        index_frame = tk.LabelFrame(main_frame, text="3. Números de Línea (Índice - Dejar vacío si es opcional)", padx=10, pady=10)
        index_frame.pack(fill='x', pady=(0, 10))
        
        # Fila 0
        self._create_labeled_entry(index_frame, "Línea Factura:", self.l_invoice_var, 0, column=0)
        self._create_labeled_entry(index_frame, "Línea Fecha:", self.l_date_var, 0, column=2)
        
        # Fila 1 (Importes)
        self._create_labeled_entry(index_frame, "Línea TOTAL:", self.l_total_var, 1, column=0)
        self._create_labeled_entry(index_frame, "Línea BASE:", self.l_base_var, 1, column=2)
        
        # Fila 2 (Cliente)
        self._create_labeled_entry(index_frame, "Línea Cliente:", self.l_client_var, 2, column=0)
        self._create_labeled_entry(index_frame, "Línea CIF Cliente:", self.l_client_cif_var, 2, column=2)

        # Fila 3 (Vehículo Opcional)
        self._create_labeled_entry(index_frame, "Línea Modelo (Opc.):", self.l_modelo_var, 3, column=0)
        self._create_labeled_entry(index_frame, "Línea Matrícula (Opc.):", self.l_matricula_var, 3, column=2)

        # Fila 4 (Otros Importes Opcional)
        self._create_labeled_entry(index_frame, "Línea IVA (Monto Opc.):", self.l_iva_var, 4, column=0)
        self._create_labeled_entry(index_frame, "Línea Tasas (Opc.):", self.l_tasas_var, 4, column=2)
        
        # Botón de Generación
        tk.Button(main_frame, text="GENERAR EXTRACTOR", command=self.generate_and_update, bg="darkgreen", fg="white", font=('Arial', 10, 'bold')).pack(pady=5, fill='x')
        
        # --- SECCIÓN 4: DEBUG Y TESTEO ---
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
        # ... (Función auxiliar se mantiene) ...
        tk.Label(parent, text=label_text).grid(row=row, column=column, sticky='w', padx=5, pady=2)
        entry = tk.Entry(parent, textvariable=var, width=15)
        entry.grid(row=row, column=column + 1, sticky='w', padx=5, pady=2)
        if command:
            var.trace_add("write", lambda *args: command())
        return entry


    def _update_keyword(self):
        # ... (Función de keyword se mantiene) ...
        emisor = self.emisor_name_var.get().strip()
        if emisor:
            clean_emisor = re.sub(r'[\s,\.-]+', '_', emisor.lower())
            keyword = clean_emisor.split('_')[0] if clean_emisor else ""
            class_name = f"{keyword.capitalize()}Extractor" if keyword else ""
            file_name = f"{keyword}_extractor.py" if keyword else ""
            self.keyword_var.set(keyword)
            self.file_name_var.set(file_name)
            self.class_name_var.set(class_name)
        else:
            self.keyword_var.set("")
            self.file_name_var.set("")
            self.class_name_var.set("")


    def _parse_lines(self) -> List[str]:
        # ... (Función de parseo de líneas se mantiene) ...
        raw_lines = self.lines_text_area.get("1.0", tk.END).strip()
        parsed_lines: List[str] = []
        for line in raw_lines.splitlines():
            match = re.search(r'Line\s*\d+:\s*(.*)', line)
            if match:
                parsed_lines.append(match.group(1).strip())
        return parsed_lines
        
    def _get_line_num(self, tk_var: tk.StringVar) -> Optional[int]:
        """Convierte el contenido de StringVar a int o None si está vacío. Lanza ValueError si no es número."""
        val = tk_var.get().strip()
        if not val:
            return None
        try:
            return int(val)
        except ValueError:
            # Lanza ValueError para que sea atrapado por la excepción principal
            raise ValueError(f"El campo '{val}' no es un número entero válido.")


    def generate_and_update(self):
        # --- 1. Obtener y Validar Datos ---
        try:
            emisor_name = self.emisor_name_var.get().strip()
            emisor_cif = self.emisor_cif_var.get().strip()
            keyword = self.keyword_var.get()
            
            parsed_lines = self._parse_lines()
            num_lines = len(parsed_lines)

            if not emisor_name or not emisor_cif or not keyword or not parsed_lines:
                messagebox.showerror("Error de Validación", "Por favor, complete los campos de Emisor y pegue las líneas de salida del PDF.")
                return

            # Obtener y convertir a enteros o None (para campos opcionales)
            line_data = {
                # Campos principales
                'invoice': self._get_line_num(self.l_invoice_var),
                'date': self._get_line_num(self.l_date_var),
                'total': self._get_line_num(self.l_total_var),
                'base': self._get_line_num(self