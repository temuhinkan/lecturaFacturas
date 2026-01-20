from nicegui import ui, events
import database
import os
import fitz  # PyMuPDF
import base64

# ----------------------------
# Estado global
# ----------------------------
class ValidadorState:
    def __init__(self):
        self.index = 0
        self.facturas = []
        self.rotation = 0
        self.zoom = 2.0
        self.start_point = None
        self.dragging = False
        self.current_rect = None
        # Variables para asignación
        self.ultimo_texto = ""
        self.ultimo_rect_pdf = None
        self.extractor_seleccionado = None

    def cargar_datos(self):
        self.facturas = database.fetch_all_invoices()


state = ValidadorState()

# ----------------------------
# Renderizado PDF a imagen
# ----------------------------
def obtener_imagen_procesada(ruta):
    if not os.path.exists(ruta):
        return None
    try:
        doc = fitz.open(ruta)
        page = doc.load_page(0)
        mat = fitz.Matrix(state.zoom, state.zoom).prerotate(state.rotation)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        doc.close()
        return img_bytes
    except Exception as e:
        print(f"Error render: {e}")
        return None

# ----------------------------
# Funciones para encontrar palabra/linea
# ----------------------------
def obtener_palabra_en_punto(page, x, y, margen=3):
    for w in page.get_text("words"):
        x0, y0, x1, y1, texto, *_ = w
        if x0-margen <= x <= x1+margen and y0-margen <= y <= y1+margen:
            return [x0, y0, x1, y1]
    return None

def obtener_linea_en_punto(page, x, y, margen=3):
    for b in page.get_text("blocks"):
        if "lines" not in b: continue
        for line in b["lines"]:
            for span in line["spans"]:
                x0, y0, x1, y1 = span["bbox"]
                if y0-margen <= y <= y1+margen:
                    return [x0, y0, x1, y1]
    return None

# ----------------------------
# Funciones de asignar y aprender
# ----------------------------
def encontrar_ancla_cercana(page, target_rect):
    words = page.get_text("words")
    if not words: return None
    center_x = (target_rect[0] + target_rect[2]) / 2
    center_y = (target_rect[1] + target_rect[3]) / 2
    best_anchor = None
    min_dist = float('inf')
    for w in words:
        if len(w[4]) < 3 or w[4].replace('.', '').isdigit(): continue
        anchor_x = (w[0] + w[2]) / 2
        anchor_y = (w[1] + w[3]) / 2
        dist = ((center_x - anchor_x)**2 + (center_y - anchor_y)**2)**0.5
        if dist < min_dist:
            min_dist = dist
            best_anchor = {'texto': w[4], 'x': w[0], 'y': w[1]}
    return best_anchor

def asignar_y_aprender(campo_destino):
    if not state.facturas or not state.ultimo_rect_pdf: 
        return
    f = state.facturas[state.index]

    # Asignar valor usando el texto editable del popup
    state.ultimo_texto = input_texto.value
    f[campo_destino] = state.ultimo_texto
    ui.notify(f"Asignado '{state.ultimo_texto}' a {campo_destino}", color='green')

    # Aprender posición relativa
    try:
        doc = fitz.open(f['path'])
        page = doc.load_page(0)
        ancla = encontrar_ancla_cercana(page, state.ultimo_rect_pdf)
        doc.close()
        if ancla and hasattr(database, 'save_learning_rule'):
            rel_x = state.ultimo_rect_pdf[0] - ancla['x']
            rel_y = state.ultimo_rect_pdf[1] - ancla['y']
            emisor_id = f.get('cif_emisor') or f.get('emisor') or "GENERICO"
            database.save_learning_rule(emisor_id, campo_destino, ancla['texto'], rel_x, rel_y, 0)
            ui.notify(f"Patrón aprendido con ancla: {ancla['texto']}", color='blue')
    except Exception as e:
        print(f"Error aprendizaje: {e}")

    dialogo_asignacion.close()

def relanzar_extraccion(f):
    extractor = state.extractor_seleccionado
    if not extractor:
        ui.notify('No hay extractor seleccionado', color='orange')
        return

    try:
        database.update_invoice_field(f['path'], 'extractor', extractor)
        database.run_extractor(f['path'], extractor)
        ui.notify(f'Extracción lanzada con {extractor}', color='green')
        vista_validar.refresh()
    except Exception as e:
        ui.notify(f'Error al extraer: {e}', color='red')
# ----------------------------
# Manejo de ratón
# ----------------------------
def manejar_raton(e: events.MouseEventArguments):
    global visor_interactivo, dialogo_asignacion, input_texto
    f = state.facturas[state.index]

    if e.type not in ('click', 'mousemove'):
        return

    try:
        doc = fitz.open(f['path'])
        page = doc.load_page(0)
        mat = fitz.Matrix(state.zoom, state.zoom).prerotate(state.rotation)
        pdf_pt = fitz.Point(e.image_x, e.image_y) * ~mat
        x, y = pdf_pt.x, pdf_pt.y

        # Drag dinámico
        if e.type == 'mousemove':
            if e.buttons == 1 and state.start_point is None:
                state.start_point = (x, y)
                state.dragging = True
            elif e.buttons == 1 and state.start_point:
                x1, y1 = state.start_point
                img_rect = fitz.Rect(min(x1, x), min(y1, y), max(x1, x), max(y1, y)) * mat
                visor_interactivo.content = f'<rect x="{img_rect.x0}" y="{img_rect.y0}" width="{img_rect.width}" height="{img_rect.height}" fill="rgba(255,0,0,0.15)" stroke="red" stroke-width="2"/>'
            elif e.buttons == 0 and state.dragging:
                x1, y1 = state.start_point
                rect_pdf = [min(x1, x), min(y1, y), max(x1, x), max(y1, y)]
                state.start_point = None
                state.dragging = False
                state.ultimo_rect_pdf = rect_pdf
                texto = page.get_text("text", clip=rect_pdf).strip()
                if texto:
                    state.ultimo_texto = texto
                    input_texto.value = texto
                    dialogo_asignacion.open()
                return
        # Click simple
        if e.type == 'click' and not state.dragging:
            rect_seleccionado = obtener_linea_en_punto(page, x, y) if e.ctrl else obtener_palabra_en_punto(page, x, y)
            if rect_seleccionado:
                texto = page.get_text("text", clip=rect_seleccionado).strip()
                if texto:
                    state.ultimo_texto = texto
                    state.ultimo_rect_pdf = rect_seleccionado
                    img_rect = fitz.Rect(rect_seleccionado) * mat
                    visor_interactivo.content = f'<rect x="{img_rect.x0}" y="{img_rect.y0}" width="{img_rect.width}" height="{img_rect.height}" fill="rgba(255,0,0,0.15)" stroke="red" stroke-width="2"/>'
                    input_texto.value = texto
                    dialogo_asignacion.open()

        doc.close()
    except Exception as ex:
        print(f"Error ratón: {ex}")
def detectar_extractor_del_log(log_text):
    import re
    # Busca patrones como "Usado extractor: extractors.leroy.Leroy" o "Usado extractor: GENERICO"
    match = re.search(r"Usado extractor: (?:extractors\.\w+\.)?(\w+)", log_text)
    if match:
        return match.group(1)
    if "extractor genérico" in log_text.lower():
        return "GENERICO"
    return None
# ----------------------------
# Vista principal
# ----------------------------
@ui.refreshable
def vista_validar():
    state.cargar_datos()
    if not state.facturas:
        ui.label('No hay facturas').classes('p-10 text-h4')
        return

    f = state.facturas[state.index]
    extractores = database.get_extractor_names()

    if not state.extractor_seleccionado:
        detectado = detectar_extractor_del_log(f.get('log_data', ''))
        if detectado and detectado in extractores:
            state.extractor_seleccionado = detectado
        else:
            state.extractor_seleccionado = extractores[0] if extractores else None


    # Diálogo global editable
    global dialogo_asignacion, input_texto
    with ui.dialog() as dialogo_asignacion:
        with ui.card().classes('p-4 w-96'):
            ui.label('Asignar valor').classes('text-lg font-bold mb-2')
            input_texto = ui.input('', value=state.ultimo_texto).props('outlined dense').classes('w-full mb-4')
            campos = [
                ('Fecha', 'fecha'), ('Nº Factura', 'numero_factura'),
                ('Emisor', 'emisor'), ('CIF Emisor', 'cif_emisor'),
                ('Cliente', 'cliente'), ('CIF Cliente', 'cif'),
                ('Base', 'base'), ('IVA', 'iva'), ('TOTAL', 'importe')
            ]
            with ui.grid(columns=2).classes('gap-2'):
                for label, key in campos:
                    ui.button(label, on_click=lambda k=key: asignar_y_aprender(k)).props('outline dense')

    # Contenedor principal
    with ui.column().classes('w-full h-screen gap-0 overflow-hidden'):

        # Barra superior con zoom y rotar
        with ui.row().classes('w-full bg-white p-2 border-b items-center shadow-sm px-4'):
            ui.button(icon='rotate_right', on_click=lambda: (setattr(state, 'rotation', (state.rotation + 90) % 360), vista_validar.refresh())).props('flat')
            ui.separator().props('vertical')
            ui.button(icon='zoom_in', on_click=lambda: (setattr(state, 'zoom', state.zoom + 0.5), vista_validar.refresh())).props('flat')
            ui.button(icon='zoom_out', on_click=lambda: (setattr(state, 'zoom', max(0.5, state.zoom - 0.5)), vista_validar.refresh())).props('flat')
            ui.space()
            ui.label(os.path.basename(f['path'])).classes('text-xs font-bold truncate')
            ui.space()
            ui.button(icon='chevron_left', on_click=lambda: (setattr(state, 'index', state.index-1), vista_validar.refresh())).set_visibility(state.index > 0)
            ui.label(f"{state.index+1}/{len(state.facturas)}")
            ui.button(icon='chevron_right', on_click=lambda: (setattr(state, 'index', state.index+1), vista_validar.refresh())).set_visibility(state.index < len(state.facturas)-1)

        # Fila principal: visor y formulario
        with ui.row().classes('w-full flex-grow gap-0 overflow-hidden'):
            # Visor
            with ui.scroll_area().classes('w-3/4 h-full bg-slate-300 p-0'):
                global visor_interactivo
                img_data = obtener_imagen_procesada(f['path'])
                if img_data:
                    src = f"data:image/png;base64,{base64.b64encode(img_data).decode()}"
                    visor_interactivo = ui.interactive_image(
                        src,
                        content='<svg></svg>',
                        on_mouse=manejar_raton,
                        sanitize=False
                    ).style('width: auto; height: 100%; cursor: crosshair') \
                     .props('drag_crosshair')
                else:
                    ui.label('Error al renderizar imagen')

            # Formulario
            with ui.column().classes('w-1/4 h-full bg-white border-l p-4 overflow-y-auto'):

                ui.label('DATOS FACTURA').classes('text-xs font-black text-blue-900 mb-4')
                
                ui.input('Fecha').bind_value(f, 'fecha').props('dense outlined')
                ui.input('Factura Nº').bind_value(f, 'numero_factura').props('dense outlined')
                ui.input('Emisor').bind_value(f, 'emisor').props('dense outlined')
                ui.input('CIF Emisor').bind_value(f, 'cif_emisor').props('dense outlined')
                ui.input('Cliente').bind_value(f, 'cliente').props('dense outlined')
                ui.input('CIF Cliente').bind_value(f, 'cif').props('dense outlined')
                ui.input('Concepto').bind_value(f, 'concepto').props('dense outlined')
                ui.input('Matrícula').bind_value(f, 'matricula').props('dense outlined')
                with ui.row().classes('w-full no-wrap gap-2'):
                    ui.number('BASE', format='%.2f').bind_value(f, 'base').props('dense outlined').classes('w-1/2')
                    ui.number('IVA', format='%.2f').bind_value(f, 'iva').props('dense outlined').classes('w-1/2')
                ui.number('TOTAL', format='%.2f').bind_value(f, 'importe').props('dense outlined bg-yellow-50 font-bold').classes('w-full')
                extractores = database.get_extractor_names()

                ui.label('EXTRACTOR').classes('text-xs font-bold text-gray-600 mt-4')

                ui.select(
                    options=extractores,
                    value=state.extractor_seleccionado or extractores[0] if extractores else None,
                    on_change=lambda e: setattr(state, 'extractor_seleccionado', e.value)
                ).props('dense outlined').classes('w-full')
                ui.button(
                    'RELANZAR EXTRACCIÓN',
                    icon='restart_alt',
                    on_click=lambda: relanzar_extraccion(f)
                ).classes('w-full mt-2 bg-blue-700 text-white font-bold')
                ui.button('GUARDAR', on_click=lambda: database.update_invoice_field(f['path'], 'is_validated', 1))\
                    .classes('w-full mt-4 bg-green-800 text-white font-bold h-10')

        # Logs debajo
        with ui.expansion('LOGS', icon='terminal').classes('w-full bg-slate-900 text-green-400'):
            ui.markdown(f"```text\n{f.get('log_data', '')}\n```").classes('p-2 text-[11px]')
