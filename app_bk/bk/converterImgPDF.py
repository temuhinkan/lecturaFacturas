from PIL import Image
import pytesseract
import os # Asegurarse de que os está importado

def convert_image_to_searchable_pdf(image_path, output_pdf_path):
    try:
        # Abrir la imagen
        img = Image.open(image_path)

        # Realizar OCR y obtener el texto en formato PDF (hOCR o PDF de Tesseract)
        # Tesseract puede generar un PDF directamente.
        # Asegúrate de que Tesseract esté instalado en tu sistema y su ruta añadida al PATH
        # O configura pytesseract.pytesseract.tesseract_cmd = r'<path_to_tesseract_executable>'

        # Este método es el más directo para un PDF "buscable":
        # 'spa' para español. Se genera el PDF directamente en la ruta especificada.
        pdf_output = pytesseract.image_to_pdf_or_hocr(img, extension='pdf', lang='spa')
        
        with open(output_pdf_path, 'wb') as f:
            f.write(pdf_output)

        print(f"Imagen '{image_path}' convertida a PDF searchable: '{output_pdf_path}'")
        return output_pdf_path
    except Exception as e:
        print(f"Error al convertir imagen a PDF: {e}")
        return None

# Ejemplo de uso (no es parte del código que se ejecuta, solo para referencia):
# if __name__ == '__main__':
#     # Asegúrate de tener una imagen de prueba, por ejemplo, 'test_image.png'
#     # y que la ruta a Tesseract esté configurada si no está en el PATH
#     pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe' 
#     
#     image_file = "test_image.png" # Reemplaza con una imagen real
#     # Generar el PDF en el mismo directorio que la imagen de prueba
#     output_pdf_file = os.path.join(os.path.dirname(image_file), f"{os.path.splitext(os.path.basename(image_file))[0]}_ocr.pdf")
#     
#     generated_pdf = convert_image_to_searchable_pdf(image_file, output_pdf_file)
#     if generated_pdf:
#        print(f"PDF generado: {generated_pdf}")
#     else:
#        print("Fallo la generación del PDF.")