import os
import csv
import PyPDF2
import argparse
import shutil
import fitz # PyMuPDF
import tempfile 
import sys 
import importlib # ¡NUEVO! Necesario para la importación dinámica
from typing import Tuple, List, Optional, Any 

# Importar las funciones de utilidad y constantes
from utils import (
    extract_and_format_date, _extract_amount, _extract_nif_cif, 
    _calculate_base_from_total, _extract_from_line, 
    _extract_from_lines_with_keyword, VAT_RATE
) 

# Importar la clase base (esta SÍ es necesaria)
from extractors.base_invoice_extractor import BaseInvoiceExtractor

# Importar la función para dividir PDFs
from split_pdf import split_pdf_into_single_page_files
from converterImgPDF import convert_image_to_searchable_pdf

# --- Configuración de OCR (Tesseract) ---
Image = None
pytesseract = None
try:
    from PIL import Image
    import pytesseract
    
    if sys.platform == "win32":
        # ¡AJUSTA ESTA RUTA!
        pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe' 
    
except ImportError:
    print("Advertencia: No se pudieron importar las librerías de OCR (Pillow o pytesseract). La conversión de imagen a PDF no funcionará.")
except AttributeError as e:
    print(f"❌ ERROR: La ruta de Tesseract-OCR parece ser incorrecta o el binario no se encuentra. Verifica 'tesseract_cmd'. Error: {e}")
    Image = None
    pytesseract = None

# --- Mapeo de Clases de Extracción (¡AHORA DINÁMICO!) ---
# Ya no contiene las clases, sino la RUTA COMPLETA de la clase como una cadena de texto.
# Formato: "nombre_extractor": "ruta.del.modulo.NombreClase"
EXTRACTION_MAPPING = {
    "autodoc": "extractors.autodoc_extractor.AutodocExtractor",
    "stellantis": "extractors.stellantis_extractor.StellantisExtractor",
    "brildor": "extractors.brildor_extractor.BrildorExtractor",
    "hermanas": "extractors.hermanas_extractor.HermanasExtractor",
    "kiauto": "extractors.kiauto_extractor.KiautoExtractor",
    "sumauto": "extractors.sumauto_extractor.SumautoExtractor",
    "amor": "extractors.hermanas_extractor.HermanasExtractor", # Alias
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
    "muas": "extractors.musas_extractor.MusasExtractor", # Alias
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
    "coslauto": "extractors.coslauto_extractor.CoslautoExtractor"
}


# --- Constante de Error Estandarizada ---
# 12 valores: Tipo, Fecha, Num_Factura, Emisor, Cliente, CIF, Modelo, Matricula, Importe, Base, Tasas, Generated_PDF_Filename
ERROR_DATA: Tuple[str, None, None, None, None, None, None, None, None, None, None, None] = (
    "ERROR_EXTRACCION", None, None, None, None, None, None, None, None, None, None, None
)

# --- Lógica Principal de Procesamiento de PDF ---

def extraer_datos(pdf_path: str, debug_mode: bool = False) -> Tuple[Any, ...]:
    """
    Extrae datos de una factura en formato PDF o imagen.
    Devuelve 12 valores: 10 datos de factura + Tasas + Generated_PDF_Filename.
    """
    original_pdf_path = pdf_path
    generated_pdf_filename = None
    
    file_extension = os.path.splitext(pdf_path)[1].lower()
    
    # 1. Manejo de IMÁGENES y Conversión a PDF Searchable
    if file_extension in ['.jpg', '.jpeg', '.png', '.tiff', '.tif']:
        if not Image or not pytesseract:
             print("ERROR: El OCR no está disponible. No se pueden procesar imágenes.")
             return ERROR_DATA

        print(f"Detectado archivo de imagen: '{pdf_path}'. Convirtiendo a PDF searchable...")
        
        base_name = os.path.basename(pdf_path)
        name_without_ext = os.path.splitext(base_name)[0]
        generated_pdf_path = os.path.join(os.path.dirname(pdf_path), f"{name_without_ext}_ocr.pdf")
        
        if convert_image_to_searchable_pdf(pdf_path, generated_pdf_path):
            print(f"Conversión exitosa. Procesando PDF generado: '{generated_pdf_path}'")
            pdf_path = generated_pdf_path
            generated_pdf_filename = os.path.basename(generated_pdf_path)
        else:
            print(f"ERROR: No se pudo convertir la imagen '{original_pdf_path}' a PDF. Abortando extracción.")
            return ERROR_DATA 
    
    if not os.path.exists(pdf_path):
        print(f"Error: El archivo '{pdf_path}' no existe.")
        return ERROR_DATA 

    # 2. Lectura y Extracción de Texto del PDF
    lines: List[str] = []
    try:
        with open(pdf_path, 'rb') as archivo:
            pdf = PyPDF2.PdfReader(archivo)
            texto = ''
            for pagina in pdf.pages:
                texto += pagina.extract_text() or ''
            lines = texto.splitlines()
    except Exception as e:
        print(f"❌ Error al leer el PDF {pdf_path}: {e}")
        return ERROR_DATA

    if debug_mode:
        print("\n🔍 DEBUG MODE ACTIVATED: Showing all lines in file\n")
        for i, linea in enumerate(lines):
            print(f"Line {i}: {linea}")

    # 3. Mapeo e Importación Dinámica del Extractor
    nombre_archivo = os.path.basename(pdf_path).lower()
    ExtractorClass = None
    full_class_path = None
    keyword_detected = None

    # Buscar la palabra clave y obtener la ruta de la clase
    for keyword, path in EXTRACTION_MAPPING.items():
        if keyword in nombre_archivo:
            keyword_detected = keyword
            full_class_path = path
            break
    
    if full_class_path:
        print(f"➡️ Detected '{keyword_detected}' in filename. Attempting dynamic import...")
        try:
            # Separar la ruta del módulo y el nombre de la clase
            module_path, class_name = full_class_path.rsplit('.', 1)
            
            # Cargar el módulo y obtener la clase
            module = importlib.import_module(module_path)
            ExtractorClass = getattr(module, class_name)
            
            # Ejecutar la extracción con la clase importada
            extractor = ExtractorClass(lines, pdf_path) 
            extracted_data = extractor.extract_all()
            
            if isinstance(extracted_data, tuple) and len(extracted_data) == 10:
                return (*extracted_data, None, generated_pdf_filename)
            
            print(f"Advertencia: Extractor específico ('{keyword_detected}') falló o no devolvió 10 elementos. Usando genérico.")
            
        except Exception as e:
            print(f"❌ ERROR: Falló la importación dinámica o la ejecución del extractor para '{keyword_detected}'. Error: {e}")
            # Si la importación o el extractor fallan, pasamos al genérico
            pass 
    
    # 4. Extractor Genérico (Fallback)
    print("➡️ No specific invoice type detected or specific extractor failed. Using generic extraction function.")
    generic_extractor = BaseInvoiceExtractor(lines)
    extracted_data = generic_extractor.extract_all()
    
    # Retorna los 10 datos + Tasas (None) + Generated_PDF_Filename
    return (*extracted_data, None, generated_pdf_filename)


# --- Lógica de Procesamiento y Salida CSV ---
# El resto del bloque __main__ permanece IGUAL. 
# Si el código que sigue es idéntico a la versión anterior, no es necesario pegarlo de nuevo.
# Asumo que el resto de tu código __main__ (manejo de argumentos, bucles, CSV, limpieza)
# es el que te proporcioné en la revisión anterior y por lo tanto, es correcto.

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process a PDF file or all PDFs in a folder.')
    parser.add_argument('ruta', help='Path to a PDF file or a folder with PDF files')
    parser.add_argument('--debug', action='store_true', help='Activate debug mode (True/False)')
    args = parser.parse_args()

    ruta_input = args.ruta
    debug_mode = args.debug
    
    all_pdfs_to_process: List[str] = [] 
    temp_dir_manager = tempfile.TemporaryDirectory()
    temp_split_invoices_dir = temp_dir_manager.name

    supported_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.tif']

    # Lógica de escaneo de archivos
    if os.path.isfile(ruta_input):
        pdfs_from_input = [ruta_input] if os.path.splitext(ruta_input)[1].lower() in supported_extensions else []
    elif os.path.isdir(ruta_input):
        pdfs_from_input = [
            os.path.join(ruta_input, f) for f in os.listdir(ruta_input)
            if os.path.isfile(os.path.join(ruta_input, f)) and os.path.splitext(f)[1].lower() in supported_extensions
        ]
    else:
        print("❌ La ruta proporcionada no es un archivo válido ni una carpeta existente.")
        temp_dir_manager.cleanup()
        sys.exit()

    if not pdfs_from_input:
        print("❌ No se encontraron archivos para procesar.")
        temp_dir_manager.cleanup()
        sys.exit()

    # Preparación: División de PDFs y recolección de archivos a procesar
    for pdf_path in pdfs_from_input:
        filename_lower = os.path.basename(pdf_path).lower()
        file_extension = os.path.splitext(pdf_path)[1].lower()

        if file_extension in supported_extensions and file_extension != '.pdf':
            all_pdfs_to_process.append(pdf_path)
            continue
        
        try:
            with open(pdf_path, 'rb') as infile:
                reader = PyPDF2.PdfReader(infile)
                # Lógica de división: solo si es Pradilla y tiene más de una página
                if len(reader.pages) > 1 and "pradilla" in filename_lower:
                    split_files = split_pdf_into_single_page_files(pdf_path, temp_split_invoices_dir)
                    if split_files:
                        all_pdfs_to_process.extend(split_files)
                        print(f"✅ PDF '{os.path.basename(pdf_path)}' dividido en {len(split_files)} páginas.")
                    else:
                        print(f"❌ No se pudieron dividir las páginas. Se procesará el archivo original.")
                        all_pdfs_to_process.append(pdf_path)
                else:
                    all_pdfs_to_process.append(pdf_path)
        except Exception as e:
            print(f"❌ Error al verificar o dividir PDF '{os.path.basename(pdf_path)}': {e}. Se intentará procesar el archivo original.")
            all_pdfs_to_process.append(pdf_path)

    if not all_pdfs_to_process:
        print("❌ No hay archivos válidos para procesar después de la fase de división/preparación.")
        temp_dir_manager.cleanup()
        sys.exit()

    all_extracted_rows = []

    def format_numeric_value(value, is_currency: bool = True) -> str:
        if value is None:
            return 'No encontrado'
        try:
            numeric_val = float(str(value).replace(',', '.')) 
            formatted = f"{numeric_val:.2f}"
            if is_currency:
                return f"{formatted} €".replace('.', ',')
            return formatted.replace('.', ',')
        except ValueError:
            return str(value)


    for archivo_a_procesar in all_pdfs_to_process:
        print(f"\n--- Procesando archivo: {os.path.basename(archivo_a_procesar)} ---")
        
        tipo, fecha, numero_factura, emisor, cliente, cif, modelo, matricula, importe, base_imponible, tasas, generated_pdf_filename = extraer_datos(archivo_a_procesar, debug_mode)
        
        # --- Manejo y Movimiento de Imágenes ---
        display_filename_in_csv = os.path.basename(archivo_a_procesar)
        if generated_pdf_filename:
            original_image_path = archivo_a_procesar
            image_dir = os.path.dirname(original_image_path)
            img_procesada_dir = os.path.join(image_dir, "imgProcesada")
            os.makedirs(img_procesada_dir, exist_ok=True)
            
            try:
                shutil.move(original_image_path, os.path.join(img_procesada_dir, os.path.basename(original_image_path)))
                print(f"Imagen original '{os.path.basename(original_image_path)}' movida a '{img_procesada_dir}'.")
                display_filename_in_csv = generated_pdf_filename 
            except shutil.Error as e:
                print(f"Advertencia: No se pudo mover la imagen original. Posiblemente ya exista en el destino. Error: {e}")


        current_row = {
            'Archivo': display_filename_in_csv.replace(',', '') ,
            'Tipo': tipo or 'No encontrado',
            'Fecha': fecha or 'No encontrada',
            'Número de Factura': numero_factura or 'No encontrado',
            'Emisor': emisor or 'No encontrado',
            'Cliente': cliente or 'No encontrado',
            'CIF': cif or 'No encontrado',
            'Modelo': modelo or 'No encontrado',
            'Matricula': matricula or 'No encontrado',
            "Base": format_numeric_value(base_imponible, is_currency=False),
            "IVA": VAT_RATE,
            'Importe': format_numeric_value(importe, is_currency=True),
            'Tasas': format_numeric_value(tasas, is_currency=False)
        }
        all_extracted_rows.append(current_row)

    # --- Desduplicación de Filas y Escritura CSV ---
    unique_rows = []
    seen_combinations = set()

    for row in all_extracted_rows:
        row_tuple = tuple(sorted((k, v) for k, v in row.items() if k != 'Archivo'))
        
        if row_tuple not in seen_combinations:
            seen_combinations.add(row_tuple)
            unique_rows.append(row)

    output_dir = os.path.dirname(ruta_input) if os.path.isfile(ruta_input) else ruta_input
    csv_output_path = os.path.join(output_dir, 'facturas_resultado.csv')
    
    with open(csv_output_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
        fieldnames = ['Archivo', 'Tipo', 'Fecha', 'Número de Factura', 'Emisor', 'Cliente', 'CIF', 'Modelo', 'Matricula', "Base", "IVA", 'Importe', 'Tasas']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        writer.writerows(unique_rows)

    print(f"\n✅ Proceso completado. Resultados escritos en: {csv_output_path}")
    print(f"Se encontraron {len(all_extracted_rows)} filas y se escribieron {len(unique_rows)} filas únicas.")

    print("\nLimpiando archivos temporales...")
    temp_dir_manager.cleanup()
    print(f"Limpiada carpeta temporal de división: '{temp_split_invoices_dir}'")