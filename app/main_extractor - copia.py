import os
import csv
import PyPDF2
import argparse

# Importar las funciones de utilidad
from utils import extract_and_format_date, _extract_amount, _extract_nif_cif, _calculate_base_from_total, _extract_from_line, _extract_from_lines_with_keyword

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

# Importar la función para dividir PDFs
from split_pdf import split_pdf_into_single_page_files


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
    "cantelar": CantelarExtractor
}

# --- Lógica Principal de Procesamiento de PDF ---

def extraer_datos(pdf_path, debug_mode=False):
    """ Detecta el tipo de factura y aplica la clase de extracción correcta. """
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
        return "COMPRA", None, None, None, None, None, None, None, None, None

    if debug_mode:
        print("\n🔍 DEBUG MODE ACTIVATED: Showing all lines in file\n")
        for i, linea in enumerate(lines):
            print(f"Line {i}: {linea}")

    nombre_archivo = os.path.basename(pdf_path).lower()

    for keyword, ExtractorClass in EXTRACTION_CLASSES.items():
        if keyword in nombre_archivo:
            print(f"➡️ Detected '{keyword}' in filename. Using specific extraction function.")
            # Pass pdf_path to all classes, even if not all use it.
            extractor = ExtractorClass(lines, pdf_path) 
            return extractor.extract_all()
    
    print("➡️ No specific invoice type detected. Using generic extraction function.")
    generic_extractor = BaseInvoiceExtractor(lines)
    return generic_extractor.extract_all()

# --- Análisis de Argumentos de Línea de Comandos y Salida CSV ---

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process a PDF file or all PDFs in a folder.')
    parser.add_argument('ruta', help='Path to a PDF file or a folder with PDF files')
    parser.add_argument('--debug', action='store_true', help='Activate debug mode (True/False)')
    args = parser.parse_args()

    ruta = args.ruta
    debug_mode = args.debug
    archivos_pdf_a_procesar = [] # Renamed to avoid confusion with original 'archivos_pdf'

    # Determinar si la ruta es un archivo o una carpeta
    if os.path.isfile(ruta) and ruta.lower().endswith('.pdf'):
        # Check if it's a 'pradilla' invoice and if it has multiple pages
        filename_lower = os.path.basename(ruta).lower()
        needs_splitting = False
        
        try:
            with open(ruta, 'rb') as infile:
                reader = PyPDF2.PdfReader(infile)
                if len(reader.pages) > 1 and "pradilla" in filename_lower:
                    needs_splitting = True
        except Exception as e:
            print(f"❌ Error checking PDF pages for splitting: {e}")
            # If there's an error reading pages, assume it's a single file for processing
            archivos_pdf_a_procesar.append(ruta)
        
        if needs_splitting:
            # If it's a 'pradilla' multi-page PDF, split it into single-page files
            output_split_folder = os.path.join(os.path.dirname(ruta), "temp_split_invoices")
            archivos_pdf_a_procesar = split_pdf_into_single_page_files(ruta, output_split_folder)
            if not archivos_pdf_a_procesar:
                print("❌ No se pudieron dividir las páginas del PDF para 'pradilla'.")
                exit()
        else:
            # If it's a single PDF (not 'pradilla' multi-page or single-page 'pradilla'),
            # just add the original file to the list to process
            archivos_pdf_a_procesar.append(ruta)

    elif os.path.isdir(ruta):
        # Si es una carpeta, obtener todos los PDFs de la carpeta (comportamiento actual)
        archivos_pdf_a_procesar = [os.path.join(ruta, archivo) for archivo in os.listdir(ruta) if archivo.lower().endswith('.pdf')]
    else:
        print("❌ La ruta proporcionada no es un archivo PDF válido ni una carpeta.")
        exit()

    if not archivos_pdf_a_procesar:
        print("❌ No PDF files found to process.")
        exit()

    csv_path = os.path.join(os.path.dirname(ruta), 'facturas_resultado.csv')
    # Set VAT_RATE as a constant available globally, or pass it to extract_datos if it can vary per invoice.
    # For now, it's a global constant in utils.py
    from utils import VAT_RATE 
    
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Archivo', 'Tipo', 'Fecha', 'Número de Factura', 'Emisor', 'Cliente', 'CIF', 'Modelo', 'Matricula', "Base", "IVA", 'Importe'])

        for archivo in archivos_pdf_a_procesar:
            print(f"\n--- Processing file: {os.path.basename(archivo)} ---")
            tipo, fecha, numero_factura, emisor, cliente, cif, modelo, matricula, importe, base_imponible = extraer_datos(archivo, debug_mode)
            
            formatted_importe = 'No encontrado'
            if importe is not None:
                try:
                    numeric_importe = float(str(importe).replace(',', '.')) 
                    formatted_importe = f"{numeric_importe:.2f} €".replace('.', ',')
                except ValueError:
                    formatted_importe = str(importe)

            writer.writerow([
                os.path.basename(archivo),
                tipo or 'No encontrado',
                fecha or 'No encontrada',
                numero_factura or 'No encontrado',
                emisor or 'No encontrado', # Use the issuer field
                cliente or 'No encontrado', # Use the fixed client field
                cif or 'No encontrado',
                modelo or 'No encontrado',
                matricula or 'No encontrado',
                base_imponible or 'No encontrado',
                VAT_RATE,
                formatted_importe
            ])

    print(f"\n✅ Done! Check the results file in: {csv_path}")

    # Opcional: Limpiar los archivos PDF de una sola página temporales si se crearon
    # Only clean up if `output_split_folder` was actually defined due to splitting
    #if 'output_split_folder' in locals() and os.path.exists(output_split_folder):
    #    print(f"\nLimpiando archivos temporales en '{output_split_folder}'...")
    #    try:
    #       for f in os.listdir(output_split_folder):
    #            os.remove(os.path.join(output_split_folder, f))
    #        os.rmdir(output_split_folder)
    #        print("Limpieza completada.")
    #    except Exception as e:
    #        print(f"❌ Error durante la limpieza de archivos temporales: {e}")
