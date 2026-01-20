import fitz  # PyMuPDF
import os

def split_pdf_into_single_page_files(input_pdf_path, output_folder="split_invoices"):
    """
    Divide un PDF y devuelve rutas absolutas de los archivos generados usando PyMuPDF.
    """
    output_pdf_paths = []
    
    # Asegurar ruta absoluta para la carpeta de salida
    if not os.path.isabs(output_folder):
        base_dir = os.path.dirname(os.path.abspath(input_pdf_path))
        output_folder = os.path.join(base_dir, output_folder)

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"Carpeta de salida creada: {output_folder}")

    try:
        # Abrir el documento original
        src_doc = fitz.open(input_pdf_path)
        base_name = os.path.splitext(os.path.basename(input_pdf_path))[0]
        
        print(f"Dividiendo '{base_name}' ({len(src_doc)} páginas)...")

        for i in range(len(src_doc)):
            # Crear un nuevo documento vacío
            new_doc = fitz.open()
            # Copiar la página 'i' del original al nuevo
            new_doc.insert_pdf(src_doc, from_page=i, to_page=i)
            
            # Nombre del archivo de salida
            filename = f"{base_name}_page_{i + 1}.pdf"
            output_path = os.path.join(output_folder, filename)
            
            # Guardar
            new_doc.save(output_path)
            new_doc.close()
            
            output_pdf_paths.append(os.path.abspath(output_path))

        src_doc.close()
        print(f"✅ División completada. {len(output_pdf_paths)} facturas generadas.")
        return output_pdf_paths

    except Exception as e:
        print(f"❌ Error al dividir PDF: {e}")
        return []

if __name__ == "__main__":
    pass