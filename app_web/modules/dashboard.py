from nicegui import ui
import database

def get_db_counts():
    """Consulta rápida de conteos directamente a la BD."""
    counts = {
        'pendientes': 0,
        'stock': 0,
        'totales': 0,
        'clientes': 0,
        'gastos_mes': 0.0
    }
    
    with database.get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Facturas pendientes de validar
        cursor.execute("SELECT COUNT(*) FROM processed_invoices WHERE is_validated = 0")
        counts['pendientes'] = cursor.fetchone()[0]
        
        # 2. Facturas Totales
        cursor.execute("SELECT COUNT(*) FROM processed_invoices")
        counts['totales'] = cursor.fetchone()[0]
        
        # 3. Stock de Vehículos
        # NOTA: En tu create table se llama 'vehiculos', asegúrate de que coincida
        try:
            cursor.execute("SELECT COUNT(*) FROM vehiculos")
            counts['stock'] = cursor.fetchone()[0]
        except Exception:
            counts['stock'] = 0 # Por si la tabla no existe aún

        # 4. Clientes
        try:
            cursor.execute("SELECT COUNT(*) FROM clientes")
            counts['clientes'] = cursor.fetchone()[0]
        except Exception:
            counts['clientes'] = 0

        # Extra: Total Gastos (Suma de importes)
        cursor.execute("SELECT SUM(importe) FROM processed_invoices")
        res = cursor.fetchone()[0]
        counts['gastos_mes'] = res if res else 0.0

    return counts

def stat_card(title: str, value: str, icon_name: str, color_class: str):
    """Componente reutilizable para las tarjetas del dashboard."""
    with ui.card().classes('w-full sm:w-64 p-4 gap-2 no-shadow border border-gray-200'):
        with ui.row().classes('items-center w-full'):
            # Icono con fondo circular suave
            with ui.element('div').classes(f'p-3 rounded-full bg-{color_class}-100'):
                ui.icon(icon_name).classes(f'text-2xl text-{color_class}-600')
            
            # Textos
            with ui.column().classes('gap-0 ml-2'):
                ui.label(value).classes('text-2xl font-bold text-gray-800 leading-none')
                ui.label(title).classes('text-xs font-bold text-gray-500 uppercase tracking-wide')

@ui.refreshable
def vista_resumen():
    # Obtener datos frescos
    data = get_db_counts()
    
    # Contenedor Principal
    with ui.column().classes('w-full gap-6'):
        
        # Título
        with ui.row().classes('w-full items-center justify-between'):
            with ui.column().classes('gap-0'):
                ui.label('Panel de Control').classes('text-2xl font-bold text-blue-900')
                ui.label('Resumen general de la actividad').classes('text-gray-500 text-sm')
            ui.button(icon='refresh', on_click=vista_resumen.refresh).props('flat round color=blue-900')

        # Grid de Tarjetas
        with ui.row().classes('w-full gap-4 flex-wrap'):
            # Tarjeta 1: Pendientes (Naranja - Acción requerida)
            stat_card('Pendientes Validar', str(data['pendientes']), 'pending_actions', 'orange')
            
            # Tarjeta 2: Stock (Azul - Inventario)
            stat_card('Stock Vehículos', str(data['stock']), 'directions_car', 'blue')
            
            # Tarjeta 3: Facturas Totales (Indigo - Documentación)
            stat_card('Facturas Totales', str(data['totales']), 'description', 'indigo')
            
            # Tarjeta 4: Clientes (Verde - Negocio)
            stat_card('Clientes Activos', str(data['clientes']), 'groups', 'emerald')

        # Sección inferior (Ejemplo: Accesos rápidos o gráfica simple)
        ui.separator().classes('mt-4')
        
        with ui.row().classes('w-full gap-6'):
            # Columna Izquierda: Información Financiera rápida
            with ui.card().classes('flex-grow p-6 bg-slate-50 border-none'):
                ui.label('Volumen de Compras').classes('text-lg font-bold text-gray-700 mb-4')
                ui.label(f"{data['gastos_mes']:,.2f} €".replace(',', 'X').replace('.', ',').replace('X', '.')).classes('text-4xl font-black text-slate-800')
                ui.label('Total acumulado en facturas procesadas').classes('text-sm text-gray-400 mt-2')

            # Columna Derecha: Accesos rápidos
            with ui.card().classes('flex-grow p-6 border-none'):
                ui.label('Accesos Rápidos').classes('text-lg font-bold text-gray-700 mb-4')
                with ui.row().classes('gap-4'):
                    ui.button('Subir Factura', on_click=lambda: ui.notify('Usa el botón superior para importar')) \
                        .props('outline icon=upload color=blue-900')
                    ui.button('Ver Stock', on_click=lambda: ui.notify('Ir a sección Stock')) \
                        .props('outline icon=garage color=blue-900')