from PIL import Image
import os
import fitz # PyMuPDF
import easyocr # La nueva librería OCR
import io # Necesario para manejar el objeto Image como bytes en fitz
import traceback # Para mejor depuración

# Importamos la función de EasyOCR y su configuración del otro archivo para reusar el lector cacheado
# Esto asume que 'logic.py' está disponible y exporta la función 'get_ocr_reader'
from logic import get_ocr_reader 


def convert_image_to_searchable_pdf(image_path: str, output_pdf_path: str) -> str | None:
    """
    Convierte una imagen (JPG, PNG) a un archivo PDF con capacidad de búsqueda (searchable PDF).
    Utiliza EasyOCR para extraer el texto y PyMuPDF (fitz) para crear la capa de texto invisible.

    Args:
        image_path (str): La ruta al archivo de imagen de entrada.
        output_pdf_path (str): La ruta donde se guardará el PDF de salida.

    Returns:
        str | None: La ruta al archivo PDF creado, o None en caso de error.
    """
    if not easyocr or not fitz or not Image:
        print("❌ Dependencias de OCR o PDF no disponibles (EasyOCR/fitz/PIL).")
        return None

    reader = get_ocr_reader()
    if not reader:
        return None

    try:
        # 1. Abrir la imagen
        img = Image.open(image_path)
        img_width, img_height = img.size

        # 2. Realizar OCR con EasyOCR
        # Se necesita el detalle completo para obtener las coordenadas (bounding boxes)
        print("Iniciando OCR con EasyOCR para generar capa de texto...")
        ocr_results = reader.readtext(image_path, detail=1, paragraph=False)
        print(f"OCR completado. {len(ocr_results)} elementos de texto encontrados.")

        # 3. Crear el nuevo documento PDF con PyMuPDF
        doc = fitz.open()
        
        # Ajustar el tamaño de la página al tamaño de la imagen (en puntos, 72 DPI)
        # fitz usa puntos (1/72 de pulgada). Si no se ajusta, se usa tamaño A4 por defecto.
        page = doc.new_page(width=img_width, height=img_height)
        page_rect = page.rect # Rectángulo completo de la página

        # 4. Insertar la imagen de fondo
        img_byte_arr = io.BytesIO()
        try:
            # Intentar guardar como JPEG para minimizar tamaño, usar PNG si falla
            img.save(img_byte_arr, format='JPEG', optimize=True, quality=95)
        except (IOError, OSError): # Puede fallar si la imagen no tiene los modos adecuados
            img.save(img_byte_arr, format='PNG')
        
        # Insertar imagen en la página
        page.insert_image(page_rect, stream=img_byte_arr.getvalue())

        # 5. Insertar la capa de texto invisible
        font = 'helv'
        
        for bbox, text, conf in ocr_results:
            # Extraer las coordenadas del bounding box
            # bbox: [[x1, y1], [x2, y2], [x3, y3], [x4, y4]] (4 pares de coordenadas)
            x_coords = [p[0] for p in bbox]
            y_coords = [p[1] for p in bbox]
            
            # Crear el rectángulo delimitador (x0, y0, x1, y1)
            rect = fitz.Rect(min(x_coords), min(y_coords), max(x_coords), max(y_coords))
            
            if rect.width <= 0 or rect.height <= 0:
                continue

            # Calcular un tamaño de fuente aproximado
            # Usar la altura del bounding box como el tamaño de la fuente
            font_size = max(1.0, rect.height) 
            
            try:
                # insert_textbox para encajar el texto en el rectángulo
                page.insert_textbox(
                    rect, 
                    text, 
                    fontsize=font_size, 
                    fontname=font, 
                    # render=3 hace que el texto sea invisible (la clave del searchable PDF)
                    render=3, 
                    align=fitz.TEXT_ALIGN_LEFT
                )
            except Exception as insert_e:
                print(f"Advertencia: Falló la inserción de texto para '{text[:20]}...'. Error: {insert_e}")


        # 6. Guardar el PDF resultante
        doc.save(output_pdf_path, garbage=4, deflate=True)
        doc.close()

        print(f"✅ Imagen '{image_path}' convertida a PDF searchable: '{output_pdf_path}' (usando EasyOCR + fitz)")
        return output_pdf_path
    
    except Exception as e:
        print(f"❌ Error al convertir imagen a PDF (EasyOCR + fitz): {e}")
        traceback.print_exc()
        return None

# Ejemplo de uso (no es parte del código que se ejecuta, solo para referencia):
# if __name__ == '__main__':
#     # Asegúrate de tener una imagen de prueba, por ejemplo, 'test_image.png'
#     # y que las dependencias estén instaladas (easyocr, PyMuPDF, Pillow)
#     pass