from nicegui import ui
import database
import pandas as pd
import io

def vista_historico_exportaciones():
    ui.label('Histórico de Exportaciones').classes('text-2xl font-bold mb-4')

    def cargar_lotes():
        lotes = database.fetch_export_history()
        table.rows = lotes
        table.update()

    def re_exportar(e):
        # e.args contiene los datos de la fila en NiceGUI
        lote_id = e.args['row']['exportado']
        facturas = database.fetch_invoices_by_export_batch(lote_id)
        
        if not facturas:
            ui.notify('No se encontraron facturas para este lote', type='negative')
            return

        # Generar Excel en memoria
        df = pd.DataFrame(facturas)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Exportacion')
        
        # Descargar
        ui.download(output.getvalue(), f"Re-exportacion_{lote_id.replace(':', '-')}.xlsx")
        ui.notify(f'Descargando lote: {lote_id}')

    columns = [
        {'name': 'exportado', 'label': 'Fecha de Exportación (Lote)', 'field': 'exportado', 'sortable': True, 'align': 'left'},
        {'name': 'total_facturas', 'label': 'Nº Facturas', 'field': 'total_facturas', 'sortable': True},
        {'name': 'acciones', 'label': 'Acciones', 'field': 'acciones'}
    ]

    table = ui.table(columns=columns, rows=[], row_key='exportado').classes('w-full')
    
    # Slot para el botón de re-exportar
    table.add_slot('body-cell-acciones', '''
        <q-td :props="props">
            <q-btn flat dense color="primary" icon="download" @click="$parent.$emit('re_export', props)">
                Re-exportar
            </q-btn>
        </q-td>
    ''')
    
    table.on('re_export', re_exportar)

    cargar_lotes()