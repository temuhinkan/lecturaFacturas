import PyPDF2
import os

def split_pdf_into_single_page_files(input_pdf_path, output_folder="split_invoices"):
    """
    Divide un archivo PDF de varias páginas en archivos PDF individuales,
    donde cada archivo de salida contiene una sola página del PDF original.

    Args:
        input_pdf_path (str): La ruta al archivo PDF de entrada.
        output_folder (str): El nombre de la carpeta donde se guardarán los PDFs divididos.
                              Si no existe, se creará.
    Returns:
        list: Una lista de las rutas completas a los archivos PDF de una sola página creados.
    """
    output_pdf_paths = []
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"Carpeta de salida creada: {output_folder}")

    try:
        with open(input_pdf_path, 'rb') as infile:
            reader = PyPDF2.PdfReader(infile)
            num_pages = len(reader.pages)
            print(f"El PDF '{os.path.basename(input_pdf_path)}' tiene {num_pages} páginas.")

            for page_num in range(num_pages):
                writer = PyPDF2.PdfWriter()
                writer.add_page(reader.pages[page_num])

                # Generar un nombre de archivo para la página individual
                base_name = os.path.splitext(os.path.basename(input_pdf_path))[0]
                output_pdf_path = os.path.join(output_folder, f"{base_name}_page_{page_num + 1}.pdf")

                with open(output_pdf_path, 'wb') as outfile:
                    writer.write(outfile)
                print(f"Página {page_num + 1} guardada como '{output_pdf_path}'")
                output_pdf_paths.append(output_pdf_path)

        print(f"\n✅ ¡Proceso de división completado para '{os.path.basename(input_pdf_path)}'!")
        return output_pdf_paths

    except FileNotFoundError:
        print(f"❌ Error: El archivo '{input_pdf_path}' no fue encontrado.")
        return []
    except Exception as e:
        print(f"❌ Ocurrió un error al procesar el PDF: {e}")
        return []

if __name__ == "__main__":
    # Ejemplo de uso:
    # Asegúrate de reemplazar 'ruta/a/tu/archivo.pdf' con la ruta real de tu PDF de múltiples facturas.
    # Puedes poner el PDF en la misma carpeta que este script, o especificar una ruta completa.
    
    # Crea un archivo PDF de ejemplo si no existe (solo para probar el script)
    # import io
    # from reportlab.lib.pagesizes import letter
    # from reportlab.pdfgen import canvas
    #
    # def create_dummy_pdf(filepath, num_pages):
    #     c = canvas.Canvas(filepath, pagesize=letter)
    #     for i in range(num_pages):
    #         c.drawString(100, 750, f"Esta es la factura de la página {i+1}")
    #         c.drawString(100, 700, f"Contenido de la factura {i+1}...")
    #         c.showPage()
    #     c.save()
    #
    # dummy_pdf_path = "facturas_multiples.pdf"
    # if not os.path.exists(dummy_pdf_path):
    #     print(f"Creando un PDF de ejemplo: {dummy_pdf_path}")
    #     create_dummy_pdf(dummy_pdf_path, 3) # Crea un PDF con 3 páginas de ejemplo

    # Ruta de tu PDF real con múltiples facturas
    input_pdf = "facturas_multiples.pdf" # Reemplaza con la ruta a tu PDF
    split_pdf_into_single_page_files(input_pdf)

    # Si tienes un archivo específico que quieres usar (por ejemplo, los de las facturas que hemos estado viendo):
    # split_pdf_into_single_page_files("ruta/a/tu/otro_pdf_con_multiples_facturas.pdf", "facturas_sumauto_separadas")
