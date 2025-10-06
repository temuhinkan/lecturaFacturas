import os
import csv
import PyPDF2
import argparse
import fitz # PyMuPDF
import tempfile # Para manejar directorios temporales de forma segura
import shutil # Para mover archivos

# Importar las funciones de utilidad
from utils import extract_and_format_date, _extract_amount, _extract_nif_cif, _calculate_base_from_total, _extract_from_line, _extract_from_lines_with_keyword, VAT_RATE # VAT_RATE añadido aquí para acceso global

# Importar las clases de extractor
from extractors.base_invoice_extractor import BaseInvoiceExtractor
from extractors.autodoc_extractor import AutodocExtractor
from extractors.stellantis_extractor import StellantisExtractor
from extractors.brildor_extractor import BrildorExtractor
from extractors.hermanas_extractor import HermanasExtractor
from extractors.kiauto_extractor import KiautoExtractor
from extractors.sumauto_extractor import SumautoExtractor
from extractors.pinchete_extractor import PincheteExtractor
from extractors.refialias_extractor import RefialiasExtractor
from extractors.leroy_extractor import LeroyExtractor
from extractors.poyo_extractor import PoyoExtractor
from extractors.lacaravana_extractor import LacaravanaExtractor
from extractors.malaga_extractor import MalagaExtractor
from extractors.beroil_extractor import BeroilExtractor
from extractors.autocasher_extractor import AutocasherExtractor
from extractors.cesvimap_extractor import CesvimapExtractor
from extractors.fiel_extractor import FielExtractor
from extractors.pradilla_extractor import PradillaExtractor
from extractors.boxes_extractor import BoxesExtractor
from extractors.hergar_extractor import HergarExtractor
from extractors.musas_extractor import MusasExtractor
from extractors.aema_extractor import AemaExtractor
from extractors.autodescuento_extractor import AutodescuentoExtractor
from extractors.northgate_extractor import NorthgateExtractor
from extractors.recoautos_extractor import RecoautosExtractor
from extractors.colomer_extractor import ColomerExtractor
from extractors.wurth_extractor import WurthExtractor
from extractors.cantelar_extractor import CantelarExtractor
from extractors.volkswagen_extractor import VolkswagenExtractor
from extractors.berolkemi_extractor import BerolkemiExtractor
from extractors.oscaro_extractor import OscaroExtractor
from extractors.adevinta_extractor import AdevintaExtractor
from extractors.amazon_extractor import AmazonExtractor
from extractors.coslauto_extractor import CoslautoExtractor
from converterImgPDF import convert_image_to_searchable_pdf

# Importar la función para dividir PDFs
from split_pdf import split_pdf_into_single_page_files

try:
    from PIL import Image
    import pytesseract
    # Configura la ruta a tu ejecutable de Tesseract si no está en el PATH del sistema
    # DESCOMENTA LA SIGUIENTE LÍNEA Y AJUSTA LA RUTA SI ES NECESARIO
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe' # <--- ¡AJUSTA ESTA RUTA!
except ImportError as e:
    print(f"Advertencia: No se pudieron importar las librerías de OCR (Pillow o pytesseract). La conversión de imagen a PDF no funcionará. Error: {e}")
    Image = None
    pytesseract = None

# --- Mapeo de Clases de Extracción ---
EXTRACTION_CLASSES = {
    "autodoc": AutodocExtractor,
    "stellantis": StellantisExtractor,
    "brildor": BrildorExtractor,
    "hermanas": HermanasExtractor,
    "kiauto": KiautoExtractor,
    "sumauto": SumautoExtractor,
    "amor": HermanasExtractor,
    "pinchete": PincheteExtractor,
    "refialias": RefialiasExtractor,
    "leroy": LeroyExtractor,
    "poyo": PoyoExtractor,
    "caravana": LacaravanaExtractor,
    "malaga": MalagaExtractor,
    "beroil": BeroilExtractor,
    "berolkemi": BerolkemiExtractor,
    "autocasher": AutocasherExtractor,
    "cesvimap": CesvimapExtractor,
    "fiel": FielExtractor,
    "pradilla": PradillaExtractor, # Pradilla needs splitting if multi-page
    "boxes": BoxesExtractor,
    "hergar": HergarExtractor,
    "musas": MusasExtractor,
    "muas": MusasExtractor,
    "aema": AemaExtractor,
    "autodescuento": AutodescuentoExtractor,
    "northgate": NorthgateExtractor,
    "recoautos": RecoautosExtractor,
    "colomer": ColomerExtractor,
    "wurth": WurthExtractor,
    "candelar": CantelarExtractor,
    "cantelar": CantelarExtractor,
    "volkswagen": VolkswagenExtractor,
    "oscaro": OscaroExtractor,
    "adevinta": AdevintaExtractor,
    "amazon": AmazonExtractor,
    "coslauto": CoslautoExtractor
}

# --- Lógica Principal de Procesamiento de PDF ---

# Modificamos extraer_datos para que devuelva también el nombre del archivo PDF generado si es una imagen
def extraer_datos(pdf_path, debug_mode=False):
    original_pdf_path = pdf_path # Guardamos la ruta original
    generated_pdf_filename = None # Inicializamos el nombre del PDF generado

    file_extension = os.path.splitext(pdf_path)[1].lower()
    
    if file_extension in ['.jpg', '.jpeg', '.png', '.tiff', '.tif']:
        print(f"Detectado archivo de imagen: '{pdf_path}'. Convirtiendo a PDF searchable...")
        
        base_name = os.path.basename(pdf_path)
        name_without_ext = os.path.splitext(base_name)[0]
        
        # Definir la ruta del PDF generado en la misma ubicación que la imagen original
        generated_pdf_path = os.path.join(os.path.dirname(pdf_path), f"{name_without_ext}_ocr.pdf")
        
        if convert_image_to_searchable_pdf(pdf_path, generated_pdf_path):
            print(f"Conversión exitosa. Procesando PDF generado: '{generated_pdf_path}'")
            pdf_path = generated_pdf_path # Actualizar la ruta del PDF para el procesamiento posterior
            generated_pdf_filename = os.path.basename(generated_pdf_path) # Guardar el nombre del archivo generado
        else:
            print(f"ERROR: No se pudo convertir la imagen '{original_pdf_path}' a PDF. Abortando extracción.")
            # Asegurarse de que se devuelven 12 valores (11 + generated_pdf_filename)
            return "Error", "Error", "Error", "Error", "Error", "Error", "Error", "Error", "Error", "Error", "Error", None 

    if not os.path.exists(pdf_path):
        print(f"Error: El archivo '{pdf_path}' no existe.")
        # Asegurarse de que se devuelven 12 valores
        return "Error", "Error", "Error", "Error", "Error", "Error", "Error", "Error", "Error", "Error", "Error", None 

    lines = []
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            lines.extend(page.get_text("text").splitlines())
        doc.close()
    except Exception as e:
        print(f"Error al leer el PDF '{pdf_path}': {e}")
        # Asegurarse de que se devuelven 12 valores
        return "Error", "Error", "Error", "Error", "Error", "Error", "Error", "Error", "Error", "Error", "Error", None 

   
    print(f"✅ Entering extraer_datos() with file: {pdf_path} and debug_mode: {debug_mode}")
    
    try:
        with open(pdf_path, 'rb') as archivo:
            pdf = PyPDF2.PdfReader(archivo)
            texto = ''
            for pagina in pdf.pages:
                texto += pagina.extract_text() or ''
            lines = texto.splitlines()
    except Exception as e:
        print(f"❌ Error reading PDF {pdf_path}: {e}")
        # En caso de error, devuelve una tupla con 10 Nones y dos Nones adicionales para 'tasas' y 'generated_pdf_filename'
        return "COMPRA", None, None, None, None, None, None, None, None, None, None, None

    if debug_mode:
        print("\n🔍 DEBUG MODE ACTIVATED: Showing all lines in file\n")
        for i, linea in enumerate(lines):
            print(f"Line {i}: {linea}")

    nombre_archivo = os.path.basename(pdf_path).lower()

    for keyword, ExtractorClass in EXTRACTION_CLASSES.items():
        if keyword in nombre_archivo:
            print(f"➡️ Detected '{keyword}' in filename. Using specific extraction function.")
            extractor = ExtractorClass(lines, pdf_path) 
            extracted_data = extractor.extract_all()
            if len(extracted_data) == 10:
                return (*extracted_data, None, generated_pdf_filename) # Añade None para tasas y el nombre del PDF generado
            return (*extracted_data, generated_pdf_filename) # Añade el nombre del PDF generado
    
    print("➡️ No specific invoice type detected. Using generic extraction function.")
    generic_extractor = BaseInvoiceExtractor(lines)
    extracted_data = generic_extractor.extract_all()
    return (*extracted_data, None, generated_pdf_filename) # Añade None para tasas y el nombre del PDF generado


# --- Análisis de Argumentos de Línea de Comandos y Salida CSV ---

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process a PDF file or all PDFs in a folder.')
    parser.add_argument('ruta', help='Path to a PDF file or a folder with PDF files')
    parser.add_argument('--debug', action='store_true', help='Activate debug mode (True/False)')
    args = parser.parse_args()

    ruta_input = args.ruta
    debug_mode = args.debug
    
    all_pdfs_to_process = [] 
    temp_folders_created = set()
    processed_images_info = [] # Para almacenar información de las imágenes procesadas

    supported_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.tif']

    if os.path.isfile(ruta_input):
        file_extension = os.path.splitext(ruta_input)[1].lower()
        if file_extension in supported_extensions:
            pdfs_from_input = [ruta_input]
        else:
            print(f"❌ El archivo '{ruta_input}' no es un tipo de archivo soportado ({', '.join(supported_extensions)}).")
            exit()
    elif os.path.isdir(ruta_input):
        pdfs_from_input = []
        for f in os.listdir(ruta_input):
            file_path = os.path.join(ruta_input, f)
            file_extension = os.path.splitext(file_path)[1].lower()
            if os.path.isfile(file_path) and file_extension in supported_extensions:
                pdfs_from_input.append(file_path)
    else:
        print("❌ La ruta proporcionada no es un archivo válido ni una carpeta existente.")
        exit()

    if not pdfs_from_input:
        print("❌ No se encontraron archivos para procesar.")
        exit()

    for pdf_path in pdfs_from_input:
        filename_lower = os.path.basename(pdf_path).lower()
        file_extension = os.path.splitext(pdf_path)[1].lower()

        # Las imágenes se procesan directamente en extraer_datos
        if file_extension in ['.jpg', '.jpeg', '.png', '.tiff', '.tif']:
            print(f"Detectado archivo de imagen: '{pdf_path}'. Se procesará directamente en extraer_datos.")
            all_pdfs_to_process.append(pdf_path)
            continue
        
        try:
            with open(pdf_path, 'rb') as infile:
                reader = PyPDF2.PdfReader(infile)
                if len(reader.pages) > 1 and "pradilla" in filename_lower:
                    with tempfile.TemporaryDirectory() as temp_split_invoices_dir_for_split:
                        temp_folders_created.add(temp_split_invoices_dir_for_split)
                        
                        split_files = split_pdf_into_single_page_files(pdf_path, temp_split_invoices_dir_for_split)
                        if split_files:
                            all_pdfs_to_process.extend(split_files)
                            print(f"✅ PDF '{os.path.basename(pdf_path)}' dividido en {len(split_files)} páginas.")
                        else:
                            print(f"❌ No se pudieron dividir las páginas del PDF '{os.path.basename(pdf_path)}'. Se procesará el archivo original completo.")
                            all_pdfs_to_process.append(pdf_path)
                else:
                    all_pdfs_to_process.append(pdf_path)
        except Exception as e:
            print(f"❌ Error al verificar o dividir PDF '{os.path.basename(pdf_path)}': {e}. Se intentará procesar el archivo original.")
            all_pdfs_to_process.append(pdf_path)

    if not all_pdfs_to_process:
        print("❌ No hay archivos válidos para procesar después de la fase de división/preparación.")
        exit()

    all_extracted_rows = []

    for archivo_a_procesar in all_pdfs_to_process:
        print(f"\n--- Procesando archivo: {os.path.basename(archivo_a_procesar)} ---")
        # Ahora esperamos 12 valores: los 10 originales + tasas + generated_pdf_filename
        tipo, fecha, numero_factura, emisor, cliente, cif, modelo, matricula, importe, base_imponible, tasas, generated_pdf_filename = extraer_datos(archivo_a_procesar, debug_mode)
        
        # Si generated_pdf_filename no es None, significa que se procesó una imagen y se generó un PDF
        if generated_pdf_filename:
            original_image_path = archivo_a_procesar
            image_dir = os.path.dirname(original_image_path)
            img_procesada_dir = os.path.join(image_dir, "imgProcesada")
            os.makedirs(img_procesada_dir, exist_ok=True)
            
            # Mover la imagen original a imgProcesada
            shutil.move(original_image_path, os.path.join(img_procesada_dir, os.path.basename(original_image_path)))
            print(f"Imagen original '{os.path.basename(original_image_path)}' movida a '{img_procesada_dir}'.")
            
            # Actualizar el nombre del archivo en el CSV al PDF generado
            display_filename_in_csv = generated_pdf_filename
        else:
            display_filename_in_csv = os.path.basename(archivo_a_procesar)


        formatted_importe = 'No encontrado'
        if importe is not None:
            try:
                numeric_importe = float(str(importe).replace(',', '.')) 
                formatted_importe = f"{numeric_importe:.2f} €".replace('.', ',')
            except ValueError:
                formatted_importe = str(importe)

        formatted_tasas = 'No encontrado'
        if tasas is not None:
            try:
                numeric_tasas = float(str(tasas).replace(',', '.'))
                formatted_tasas = f"{numeric_tasas:.2f}".replace('.', ',')
            except ValueError:
                formatted_tasas = str(tasas)

        current_row = {
            'Archivo': display_filename_in_csv.replace(',', '')    ,
            'Tipo': tipo or 'No encontrado',
            'Fecha': fecha or 'No encontrada',
            'Número de Factura': numero_factura or 'No encontrado',
            'Emisor': emisor or 'No encontrado',
            'Cliente': cliente or 'No encontrado',
            'CIF': cif or 'No encontrado',
            'Modelo': modelo or 'No encontrado',
            'Matricula': matricula or 'No encontrado',
            "Base": base_imponible or 'No encontrado',
            "IVA": VAT_RATE,
            'Importe': formatted_importe,
            'Tasas': formatted_tasas
        }
        all_extracted_rows.append(current_row)

    unique_rows = []
    seen_combinations = set()

    for row in all_extracted_rows:
        row_tuple = tuple(sorted((k, v) for k, v in row.items() if k != 'Archivo'))
        
        if row_tuple not in seen_combinations:
            seen_combinations.add(row_tuple)
            unique_rows.append(row)

    csv_output_path = os.path.join(os.path.dirname(ruta_input) if os.path.isfile(ruta_input) else ruta_input, 'facturas_resultado.csv')
    
    with open(csv_output_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
        fieldnames = ['Archivo', 'Tipo', 'Fecha', 'Número de Factura', 'Emisor', 'Cliente', 'CIF', 'Modelo', 'Matricula', "Base", "IVA", 'Importe', 'Tasas']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        writer.writerows(unique_rows)

    print(f"\n✅ Proceso completado. Resultados escritos en: {csv_output_path}")
    print(f"Se encontraron {len(all_extracted_rows)} filas (incluyendo duplicados) y se escribieron {len(unique_rows)} filas únicas.")

    if temp_folders_created:
        print("\nLimpiando archivos temporales...")
        for folder in temp_folders_created:
            try:
                for f in os.listdir(folder):
                    os.remove(os.path.join(folder, f))
                os.rmdir(folder)
                print(f"Limpiada carpeta temporal: '{folder}'")
            except Exception as e:
                print(f"❌ Error durante la limpieza de archivos temporales en '{folder}': {e}")
    else:
        print("\nNo se crearon carpetas temporales para limpiar.")