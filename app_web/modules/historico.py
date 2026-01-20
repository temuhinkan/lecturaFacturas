from nicegui import ui
import database
import os
import pandas as pd
from datetime import datetime
from PDFEngineWeb import PDFEngineWeb

def vista_historico():
    pdf_engine = PDFEngineWeb()
    
    # --- FUNCIONES DE LÓGICA CON TRAZAS REFORZADAS ---
    def cargar_datos():
        print(">>> [LOG] Cargando datos desde la base de datos...")
        rows = database.fetch_all_invoices()
        table.rows = [dict(r) for r in rows]
        table.update()

    async def borrar_registros(paths):
        print(f">>> [LOG] Intento de borrado para: {paths}")
        if not paths:
            ui.notify('No hay nada seleccionado para borrar', type='warning')
            return
            
        with ui.dialog() as dialog, ui.card():
            ui.label(f'¿Eliminar definitivamente {len(paths)} registro(s)?')
            with ui.row():
                ui.button('SÍ', color='red', on_click=lambda: dialog.submit(True))
                ui.button('NO', on_click=dialog.close)
        
        if await dialog:
            for p in paths:
                print(f">>> [LOG] Ejecutando database.delete_invoice para: {p}")
                database.delete_invoice(p)
            ui.notify(f'{len(paths)} registros eliminados', color='black')
            table.selected = []
            cargar_datos()

    def ver_pdf(path):
        # TRAZA CRÍTICA
        print(f">>> [LOG] Solicitud ver_pdf recibida para: {path}")
        ui.notify(f'Intentando visualizar: {os.path.basename(path)}')
        
        try:
            if not os.path.exists(path):
                print(f">>> [ERROR] El archivo no existe en: {path}")
                ui.notify('Error: El archivo físico no existe en la carpeta', type='negative')
                return
            
            pdf_engine.load_document(path)
            img_b64 = pdf_engine.get_page_image_b64()
            pdf_display.set_source(f'data:image/png;base64,{img_b64}')
            pdf_display.visible = True
            placeholder.visible = False
            print(">>> [LOG] PDF renderizado con éxito en el visor.")
        except Exception as e:
            print(f">>> [ERROR EXCEPCIÓN] {e}")
            ui.notify(f'Error al abrir PDF: {e}', type='negative')

    # --- INTERFAZ ---
    ui.label('Histórico de Facturas').classes('text-xl font-bold mb-2')
    
    # BARRA SUPERIOR DE BOTONES
    with ui.row().classes('w-full mb-4 gap-2 items-center'):
        # BOTÓN DE TEST (Visualizar el que esté marcado con el check)
        ui.button('VISUALIZAR SELECCIONADO', icon='visibility', 
                  on_click=lambda: ver_pdf(table.selected[0]['path']) if table.selected else ui.notify('Selecciona primero una fila con el check lateral', type='warning')
                  ).props('color=orange unelevated')
        
        ui.button('Exportar Nuevos', icon='auto_awesome', 
                  on_click=lambda: ui.notify('Exportando...') # Lógica de excel aquí
                  ).props('color=green')
        
        ui.button('Borrar Selección', icon='delete_sweep', 
                  on_click=lambda: borrar_registros([r['path'] for r in table.selected])
                  ).props('color=red flat')
        
        ui.space()
        ui.button(on_click=cargar_datos, icon='refresh').props('flat round')

    with ui.row().classes('w-full no-wrap gap-4 items-start'):
        # TABLA
        with ui.column().classes('flex-grow bg-white border rounded shadow overflow-hidden').style('height: 60vh;'):
            columns = [
                {'name': 'acciones', 'label': 'Acciones', 'field': 'path', 'align': 'left'},
                {'name': 'status', 'label': 'Est.', 'field': 'is_validated', 'align': 'center'},
                {'name': 'fecha', 'label': 'Fecha', 'field': 'fecha', 'sortable': True},
                {'name': 'emisor', 'label': 'Emisor', 'field': 'emisor'},
                {'name': 'cif_emisor', 'label': 'CIF Emisor', 'field': 'cif_emisor'},
                {'name': 'cliente', 'label': 'Cliente', 'field': 'cliente'},
                {'name': 'importe', 'label': 'Total', 'field': 'importe'},
                {'name': 'base', 'label': 'Base', 'field': 'base'},
                {'name': 'iva', 'label': 'IVA', 'field': 'iva'},
                {'name': 'tasas', 'label': 'Tasas', 'field': 'tasas'},
                {'name': 'matricula', 'label': 'Matrícula', 'field': 'matricula'},
                {'name': 'concepto', 'label': 'Concepto', 'field': 'concepto'},
                {'name': 'exportado', 'label': 'Exportado', 'field': 'exportado'},
            ]

            table = ui.table(
                columns=columns, rows=[], row_key='path', selection='multiple'
            ).classes('w-full h-full text-xs')
            
            table.props('virtual-scroll sticky-header flat dense border')

            # SLOT DE ACCIONES: Usando la sintaxis más compatible posible
            table.add_slot('body-cell-acciones', '''
                <q-td :props="props">
                    <q-btn flat round dense icon="visibility" color="primary" 
                        @click="() => $parent.$emit('action_view', props.row.path)" />
                    <q-btn flat round dense icon="delete" color="grey" 
                        @click="() => $parent.$emit('action_delete', props.row.path)" />
                </q-td>
            ''')

            # ESCUCHADORES DE EVENTOS DE LA TABLA
            table.on('action_view', lambda e: ver_pdf(e.args))
            table.on('action_delete', lambda e: borrar_registros([e.args]))

            # SLOT STATUS
            table.add_slot('body-cell-status', '''
                <q-td :props="props">
                    <q-icon v-if="props.row.is_validated == 1" name="check_circle" color="green" size="xs" />
                    <q-icon v-else name="pending" color="orange" size="xs" />
                </q-td>
            ''')

        # COLUMNA DEL VISOR
        with ui.column().classes('w-1/3 bg-slate-100 border rounded relative overflow-auto shadow-inner').style('height: 60vh;'):
            with ui.column().classes('absolute-center items-center w-full') as placeholder:
                ui.icon('menu_book', size='lg').classes('text-gray-300')
                ui.label('Visor').classes('text-gray-400 text-xs')
            
            pdf_display = ui.interactive_image().classes('w-full bg-white shadow-md')
            pdf_display.visible = False

    cargar_datos()


from nicegui import ui
import database
import os
import pandas as pd
from datetime import datetime
from PDFEngineWeb import PDFEngineWeb

def vista_historico():
    pdf_engine = PDFEngineWeb()
    
    # --- FUNCIONES DE LÓGICA ---
    def cargar_datos():
        print("DEBUG: Cargando datos desde BD...")
        rows = database.fetch_all_invoices()
        table.rows = [dict(r) for r in rows]
        table.update()

    def generar_excel(lista_rows, nombre_base):
        if not lista_rows:
            ui.notify('No hay datos seleccionados', type='warning')
            return
        
        try:
            df = pd.DataFrame(lista_rows)
            # Columnas requeridas
            cols = ['fecha', 'numero_factura', 'emisor', 'cif_emisor', 'cliente', 'cif', 'matricula', 'base', 'iva', 'importe', 'tasas', 'concepto']
            cols_final = [c for c in cols if c in df.columns]
            
            nombre_archivo = f"{nombre_base}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
            df[cols_final].to_excel(nombre_archivo, index=False)
            
            # Actualizar estado de exportación
            fecha_str = datetime.now().strftime('%d/%m/%Y %H:%M')
            for r in lista_rows:
                database.update_invoice_field(r['path'], 'exportado', fecha_str)
            
            ui.download(nombre_archivo)
            ui.notify(f'Exportados {len(lista_rows)} registros', color='green')
            cargar_datos()
        except Exception as e:
            ui.notify(f'Error al exportar: {e}', type='negative')

    async def borrar_registros(paths):
        # Aseguramos que paths sea una lista
        if isinstance(paths, str): paths = [paths]
        
        if not paths:
            ui.notify('Selecciona registros para borrar', type='warning')
            return
            
        with ui.dialog() as dialog, ui.card():
            ui.label(f'¿Eliminar {len(paths)} registro(s) de la base de datos?')
            with ui.row():
                ui.button('SÍ, BORRAR', color='red', on_click=lambda: dialog.submit(True))
                ui.button('CANCELAR', on_click=dialog.close)
        
        if await dialog:
            for p in paths:
                print(f"DEBUG: Borrando {p}")
                database.delete_invoice(p)
            ui.notify('Eliminado correctamente')
            table.selected = []
            cargar_datos()

    def ver_pdf(path):
        print(f"DEBUG: Visualizando {path}")
        ui.notify(f'Abriendo: {os.path.basename(path)}')
        try:
            if not os.path.exists(path):
                ui.notify('Archivo no encontrado en disco', type='negative')
                return
            pdf_engine.load_document(path)
            img_b64 = pdf_engine.get_page_image_b64()
            pdf_display.set_source(f'data:image/png;base64,{img_b64}')
            pdf_display.visible = True
            placeholder.visible = False
        except Exception as e:
            ui.notify(f'Error visor: {e}', type='negative')

    # --- INTERFAZ ---
    ui.label('Histórico de Facturas').classes('text-xl font-bold mb-2')
    
    # Botones superiores
    with ui.row().classes('w-full mb-4 gap-2 items-center'):
        # 1. Exportar nuevos (validados y no exportados)
        ui.button('Exportar Pendientes', icon='auto_awesome', 
                  on_click=lambda: generar_excel([r for r in table.rows if r['is_validated']==1 and not r.get('exportado')], 'Nuevos_Validados')).props('color=green')
        
        # 2. Exportar selección (lo que esté marcado con el tick)
        ui.button('Exportar Selección', icon='checklist', 
                  on_click=lambda: generar_excel(table.selected, 'Seleccion_Manual')).props('color=blue outline')
        
        # 3. Borrar seleccionados
        ui.button('Borrar Seleccionados', icon='delete_sweep', 
                  on_click=lambda: borrar_registros([r['path'] for r in table.selected])).props('color=red flat')
        
        ui.space()
        ui.button(on_click=cargar_datos, icon='refresh').props('flat round')

    with ui.row().classes('w-full no-wrap gap-4 items-start'):
        # TABLA
        with ui.column().classes('flex-grow bg-white border rounded shadow overflow-hidden').style('height: 60vh;'):
            columns = [
                {'name': 'acciones', 'label': 'Acciones', 'field': 'path', 'align': 'left'},
                {'name': 'status', 'label': 'Est.', 'field': 'is_validated', 'align': 'center'},
                {'name': 'fecha', 'label': 'Fecha', 'field': 'fecha', 'sortable': True},
                {'name': 'emisor', 'label': 'Emisor', 'field': 'emisor'},
                {'name': 'cif_emisor', 'label': 'CIF Emisor', 'field': 'cif_emisor'},
                {'name': 'cliente', 'label': 'Cliente', 'field': 'cliente'},
                {'name': 'importe', 'label': 'Total', 'field': 'importe'},
                {'name': 'base', 'label': 'Base', 'field': 'base'},
                {'name': 'iva', 'label': 'IVA', 'field': 'iva'},
                {'name': 'tasas', 'label': 'Tasas', 'field': 'tasas'},
                {'name': 'matricula', 'label': 'Matrícula', 'field': 'matricula'},
                {'name': 'concepto', 'label': 'Concepto', 'field': 'concepto'},
                {'name': 'exportado', 'label': 'Exportado', 'field': 'exportado'},
            ]

            table = ui.table(
                columns=columns, rows=[], row_key='path', selection='multiple'
            ).classes('w-full h-full text-xs')
            
            table.props('virtual-scroll sticky-header flat dense border')

            # --- SLOT DE ACCIONES (SOLUCIÓN DEFINITIVA) ---
            # Usamos una llamada directa al listener de NiceGUI
            table.add_slot('body-cell-acciones', '''
                <q-td :props="props">
                    <q-btn flat round dense icon="visibility" color="primary" 
                        @click="() => $parent.$emit('row_view', props.row.path)" />
                    <q-btn flat round dense icon="delete" color="grey" 
                        @click="() => $parent.$emit('row_delete', props.row.path)" />
                </q-td>
            ''')

            # Escuchadores de eventos
            table.on('row_view', lambda e: ver_pdf(e.args))
            table.on('row_delete', lambda e: borrar_registros(e.args))

            # Visualización de estado y exportación
            table.add_slot('body-cell-status', '''
                <q-td :props="props">
                    <q-icon v-if="props.row.is_validated == 1" name="check_circle" color="green" size="xs" />
                    <q-icon v-else name="pending" color="orange" size="xs" />
                </q-td>
            ''')
            table.add_slot('body-cell-exportado', '''
                <q-td :props="props">
                    <q-badge v-if="props.value" color="blue" dense>{{ props.value }}</q-badge>
                </q-td>
            ''')

        # VISOR
        with ui.column().classes('w-1/3 bg-slate-50 border rounded relative overflow-auto shadow-inner').style('height: 60vh;'):
            with ui.column().classes('absolute-center items-center w-full') as placeholder:
                ui.icon('menu_book', size='lg').classes('text-gray-300')
                ui.label('Visor de Factura').classes('text-gray-400 text-xs')
            
            pdf_display = ui.interactive_image().classes('w-full bg-white')
            pdf_display.visible = False

    cargar_datos()