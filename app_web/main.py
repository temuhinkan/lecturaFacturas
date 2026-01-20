from nicegui import app, ui
import os
import database
# Importamos la nueva función desde logic.py
from logic import process_single_pdf
# Importamos los módulos de las vistas
from modules import dashboard, validador, historico, clientes, stock,historico_exportaciones

# Inicialización de BD y Carpetas
database.setup_database()
RUTA_FACTURAS = r'C:/Users/temuh/OneDrive/Documentos/GitHub/lecturaFacturas/facturasTotal'

if not os.path.exists(RUTA_FACTURAS):
    os.makedirs(RUTA_FACTURAS)

app.add_static_files('/documentos', RUTA_FACTURAS)

# --- FUNCIONES DE LÓGICA DE INTERFAZ ---
async def procesar_subida_factura(e, dialog):
    """Maneja la subida física y el procesamiento por logic.py"""
    try:
        # 1. Obtener el nombre del archivo
        nombre_archivo = getattr(e, 'name', 'archivo_subido.pdf')
        print(f"DEBUG: Leyendo {nombre_archivo} con await e.file.read()...")
        
        # 2. LECTURA DEL CONTENIDO (Añadimos await aquí)
        if hasattr(e, 'file'):
            # ¡CLAVE!: Al ser una función asíncrona, necesitamos el await
            contenido = await e.file.read() 
        else:
            ui.notify('Error: No se encontró el atributo file', color='red')
            return

        if not contenido:
            ui.notify('El archivo está vacío', color='yellow')
            return

        # 3. Guardar el archivo físicamente
        ruta_destino = os.path.join(RUTA_FACTURAS, nombre_archivo)
        with open(ruta_destino, 'wb') as f:
            f.write(contenido)
        
        # 4. Procesar con logic.py
        ui.notify(f'Archivo guardado. Extrayendo datos...', color='blue')
        
        import logic
        # Como process_single_pdf no es asíncrona, la llamamos normal
        success, logs = logic.process_single_pdf(ruta_destino)
        
        print("\n" + "="*60)
        print(logs)
        print("="*60 + "\n")
        
        if success:
            ui.notify(f'Factura {nombre_archivo} procesada', color='green')
        else:
            ui.notify(f'Error en extracción de {nombre_archivo}', color='orange')
            
        dialog.close()
        
    except Exception as ex:
        import traceback
        traceback.print_exc()
        ui.notify(f'Error crítico: {ex}', color='red')

# --- PÁGINA PRINCIPAL ---

@ui.page('/')
def main_page():
    # El diálogo debe estar dentro o ser accesible por la página
    with ui.dialog() as uploader_dialog, ui.card().classes('p-4 w-96'):
        ui.label('Importar y Procesar Factura').classes('text-h6 mb-2')
        ui.upload(
            on_upload=lambda e: procesar_subida_factura(e, uploader_dialog),
            auto_upload=True,
            max_files=1
        ).props('accept=* label="Arrastre factura aquí"').classes('w-full')
        ui.button('CANCELAR', on_click=uploader_dialog.close).classes('w-full mt-2').props('flat')

    # Estilo de la barra superior
    with ui.header().classes('items-center justify-between bg-blue-900'):
        ui.label('ERP Compra-Venta de Vehículos').classes('text-h6 text-white')
        ui.button('IMPORTAR PDF', on_click=uploader_dialog.open).props('icon=upload color=white flat')

    # Menú lateral
    with ui.left_drawer(value=True).classes('bg-slate-100') as drawer:
        with ui.list().classes('w-full'):
            ui.item_label('MENÚ PRINCIPAL').classes('text-grey-7 font-bold p-4')
            
            with ui.item(on_click=lambda: show_view('resumen')).classes('hover:bg-blue-100 cursor-pointer'):
                ui.icon('dashboard').classes('mr-4')
                ui.label('Resumen')
            
            with ui.item(on_click=lambda: show_view('validar')).classes('hover:bg-blue-100 cursor-pointer'):
                ui.icon('fact_check').classes('mr-4')
                ui.label('Validar Facturas')

            with ui.item(on_click=lambda: show_view('clientes')).classes('hover:bg-blue-100 cursor-pointer'):
                ui.icon('people').classes('mr-4')
                ui.label('Clientes')
            with ui.item(on_click=lambda: show_view('stock')).classes('hover:bg-blue-100 cursor-pointer'):
                ui.icon('directions_car').classes('mr-4')
                ui.label('Vehículos')
            with ui.item(on_click=lambda: show_view('historico')).classes('hover:bg-blue-100 cursor-pointer'):
                ui.icon('history').classes('mr-4')
                ui.label('Histórico Completo')
            with ui.item(on_click=lambda: show_view('hist_export')).classes('hover:bg-blue-100 cursor-pointer'):
                ui.icon('archive').classes('mr-4')
                ui.label('Histórico Exportaciones')
            

    # Contenedor dinámico
    container = ui.column().classes('w-full p-8')
    
    def show_view(name):
        container.clear()
        with container:
            if name == 'resumen':
                dashboard.vista_resumen()
            elif name == 'validar':
                validador.vista_validar()
            elif name == 'clientes':
                clientes.vista_clientes()
            elif name == 'stock':
                stock.vista_stock()
            elif name == 'historico': # <--- AÑADIR ESTO
                historico.vista_historico()
            elif name == 'hist_export':
                historico_exportaciones.vista_historico_exportaciones()

    # Vista por defecto
    with container:
        show_view('resumen')
if __name__ in {"__main__", "__mp_main__"}:
    # Es vital proteger el arranque en Windows
    ui.run(title='ERP Automoción', port=9090)