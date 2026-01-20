from nicegui import ui
import database
import pandas as pd
import io
from datetime import datetime

def vista_stock():
    # --- FUNCIONES DE FORMATEO (ESPAÑOL) ---
    def f_fecha(valor):
        if not valor or str(valor).lower() in ['nan', 'none', '']: return '-'
        try:
            return pd.to_datetime(valor).strftime('%d/%m/%Y')
        except:
            return str(valor)

    def f_moneda(valor):
        try:
            n = float(valor)
            return f"{n:,.2f} €".replace(',', 'X').replace('.', ',').replace('X', '.')
        except:
            return "0,00 €"

    # --- ESTADO REACTIVO ---
    # Almacena el vehículo que el usuario ha pinchado
    estado = {'matricula': None, 'datos': None, 'gastos': []}

    # --- LÓGICA DE DATOS ---
    def cargar_datos():
        rows = database.fetch_all_vehicles()
        for row in rows:
            row['fecha_v'] = f_fecha(row.get('fecha_compra'))
            row['total_v'] = f_moneda(row.get('total'))
        table.rows = rows
        table.update()

    async def seleccionar_vehiculo(e):
        try:
            # CORRECCIÓN AQUÍ: 
            # Si e.args es una lista, el diccionario suele estar en la posición 0 o 1
            # Probamos la forma más compatible:
            row_data = e.args.get('row') if isinstance(e.args, dict) else e.args[1] if len(e.args) > 1 else e.args[0]
            
            # Si sigue siendo una lista, intentamos extraer por índice o por atributo
            if isinstance(row_data, list):
                # En algunas versiones, matricula es la primera columna
                matricula = row_data[0] 
            else:
                matricula = row_data['matricula']

            # Buscar datos completos en la BD
            vehiculos = database.fetch_all_vehicles()
            vehiculo = next((v for v in vehiculos if v['matricula'] == matricula), None)
            
            # Obtener gastos (asegúrate que esta función existe en database.py)
            try:
                gastos = database.fetch_all_gastos_por_vehiculo(matricula)
            except:
                gastos = []
            
            estado['matricula'] = matricula
            estado['datos'] = vehiculo
            estado['gastos'] = gastos
            panel_detalle.refresh()
            
        except Exception as ex:
            print(f"Error en selección: {ex}")
            ui.notify("Error al seleccionar vehículo", type='negative')

    async def importar_excel(e):
        try:
            content = await e.file.read() if hasattr(e, 'file') else e.content.read()
            df = pd.read_excel(io.BytesIO(content)) if not e.name.lower().endswith('.csv') else pd.read_csv(io.BytesIO(content))
            df.columns = [str(c).strip().upper() for c in df.columns]
            
            for _, row in df.iterrows():
                matricula = str(row.get('MATRICULA', '')).strip()
                if matricula and matricula.lower() != 'nan':
                    data = {
                        'matricula': matricula,
                        'fecha': str(row.get('FECHA', '')),
                        'factura': str(row.get('FACTURA', '')),
                        'proveedor': str(row.get('PROVEEDOR-CLIENTE', '')),
                        'cif': str(row.get('CIF-DNI', '')),
                        'modelo': str(row.get('MODELO', '')),
                        'base': row.get('BASE', 0),
                        'iva': row.get('IVA 21%', 0),
                        'exento': str(row.get('EXENTO', '')),
                        'total': row.get('TOTAL', 0),
                    }
                    database.save_vehicle_from_excel(data)
            ui.notify('Importación Exitosa', color='green')
            cargar_datos()
        except Exception as ex:
            ui.notify(f'Error: {ex}', type='negative')

    # --- COMPONENTE DE DETALLE (DERECHA) ---
    @ui.refreshable
    def panel_detalle():
        if not estado['matricula']:
            with ui.column().classes('w-full h-full items-center justify-center text-gray-400'):
                ui.icon('ads_click', size='lg')
                ui.label('Selecciona un vehículo para ver el resumen')
            return

        v = estado['datos']
        gastos = estado['gastos']
        
        compra = float(v.get('total', 0) or 0)
        total_gastos = sum(float(g['importe'] or 0) for g in gastos)
        inversion = compra + total_gastos

        with ui.column().classes('w-full p-2'):
            ui.label(f"{v['modelo']}").classes('text-xl font-bold text-blue-900')
            ui.label(f"Matrícula: {v['matricula']}").classes('text-sm text-gray-500 mb-4')

            # Indicadores Rápidos
            with ui.row().classes('w-full gap-2 mb-4'):
                with ui.card().classes('bg-blue-50 p-3 flex-1'):
                    ui.label('Compra').classes('text-xs text-gray-500 uppercase')
                    ui.label(f_moneda(compra)).classes('font-bold')
                
                with ui.card().classes('bg-orange-50 p-3 flex-1'):
                    ui.label('Gastos Extra').classes('text-xs text-gray-500 uppercase')
                    ui.label(f_moneda(total_gastos)).classes('font-bold text-orange-700')

            with ui.card().classes('bg-green-100 p-4 w-full border-2 border-green-500 mb-4'):
                ui.label('INVERSIÓN TOTAL').classes('text-xs font-bold text-green-800')
                ui.label(f_moneda(inversion)).classes('text-2xl font-black text-green-900')

            ui.label('Desglose de Gastos').classes('font-bold text-sm mb-1')
            if gastos:
                cols_g = [
                    {'name': 'fecha', 'label': 'Fecha', 'field': 'fecha_gasto', 'align': 'left'},
                    {'name': 'concepto', 'label': 'Concepto', 'field': 'concepto', 'align': 'left'},
                    {'name': 'monto', 'label': 'Importe', 'field': 'importe', 'format': lambda x: f_moneda(x)}
                ]
                ui.table(columns=cols_g, rows=gastos).props('dense flat bordered').classes('w-full')
            else:
                ui.label('Sin gastos extra registrados').classes('text-xs italic text-gray-400')

    # --- INTERFAZ PRINCIPAL ---
    ui.label('Gestión de Stock e Inversión').classes('text-2xl font-bold mb-4')

    # BARRA SUPERIOR
    with ui.row().classes('w-full mb-4 items-center gap-3'):
        ui.button(icon='refresh', on_click=cargar_datos).props('outline')
        
        uploader = ui.upload(on_upload=importar_excel, auto_upload=True).classes('hidden')
        ui.button('Importar', icon='upload_file', on_click=lambda: uploader.run_method('pickFiles')).props('color=green')
        
        ui.button('Exportar', icon='download', on_click=lambda: ui.notify('Exportando...')).props('outline')
        
        ui.space()
        search = ui.input(placeholder='Buscar...').classes('w-64').props('outlined dense icon=search')

    # CUERPO DIVIDIDO
    with ui.row().classes('w-full no-wrap gap-4 items-start'):
        # Tabla izquierda (60% ancho)
        with ui.column().classes('w-3/5'):
            columns = [
                {'name': 'matricula', 'label': 'Matrícula', 'field': 'matricula', 'sortable': True, 'align': 'left'},
                {'name': 'modelo', 'label': 'Modelo', 'field': 'modelo', 'sortable': True, 'align': 'left'},
                {'name': 'fecha', 'label': 'F. Compra', 'field': 'fecha_v', 'sortable': True},
                {'name': 'total', 'label': 'Precio Compra', 'field': 'total_v', 'sortable': True, 'align': 'right'},
            ]
            table = ui.table(columns=columns, rows=[], row_key='matricula').classes('w-full cursor-pointer')
            table.props('flat bordered dense')
            table.on('rowClick', seleccionar_vehiculo)
            search.on('update:model-value', lambda e: table.filter(e.value))

        # Panel derecha (40% ancho)
        with ui.card().classes('w-2/5 min-h-[500px] bg-slate-50 border shadow-sm'):
            panel_detalle()

    cargar_datos()