import flet as ft
from app.editor.PDFEngine_web import PDFEngineWeb # Tu clase modificada en Paso 1

def vista_editor(page: ft.Page, invoice_path):
    engine = PDFEngineWeb()
    engine.load_document(invoice_path)
    
    # Estado del rectángulo de selección
    start_x = 0
    start_y = 0
    rect_selection = ft.Container(
        border=ft.border.all(2, "red"),
        bgcolor=ft.colors.with_opacity(0.2, "red"),
        visible=False,
        top=0, left=0, width=0, height=0,
    )

    # Imagen en base64
    img_b64, w, h = engine.get_page_image_b64()
    imagen_factura = ft.Image(src_base64=img_b64, fit=ft.ImageFit.CONTAIN)

    # Eventos del Mouse (Lo que antes hacías en controller.py)
    def on_pan_start(e: ft.DragStartEvent):
        nonlocal start_x, start_y
        start_x = e.local_x
        start_y = e.local_y
        rect_selection.left = start_x
        rect_selection.top = start_y
        rect_selection.width = 0
        rect_selection.height = 0
        rect_selection.visible = True
        page.update()

    def on_pan_update(e: ft.DragUpdateEvent):
        current_x = e.local_x
        current_y = e.local_y
        # Calcular ancho/alto dinámicamente
        rect_selection.width = abs(current_x - start_x)
        rect_selection.height = abs(current_y - start_y)
        page.update()

    def on_pan_end(e: ft.DragEndEvent):
        # ¡Aquí tienes las coordenadas finales para enviar a tu lógica de extracción!
        x1, y1 = start_x, start_y
        x2 = start_x + rect_selection.width
        y2 = start_y + rect_selection.height
        
        # Llamar a tu motor de texto original
        texto = engine.get_text_from_coords(x1, y1, x2, y2)
        print(f"Texto extraído: {texto}")
        
        # Mostrar menú contextual (como tenías en Tkinter)
        mostrar_menu_asignacion(texto)

    # El "Lienzo" web
    stack_interactivo = ft.Stack(
        controls=[
            imagen_factura,
            ft.GestureDetector(
                on_pan_start=on_pan_start,
                on_pan_update=on_pan_update,
                on_pan_end=on_pan_end,
                drag_interval=50,
            ),
            rect_selection
        ],
        width=w, height=h
    )

    return ft.Row([
        ft.Column([stack_interactivo], scroll=ft.ScrollMode.AUTO), # Izquierda: Visor
        ft.Column([ft.TextField(label="Nº Factura"), ft.TextField(label="Importe")]) # Derecha: Formulario
    ])