from nicegui import ui
import database
import pandas as pd
import io

class ClientesView:
    def __init__(self):
        self.selected_cliente = None
        self.clientes_list = []
        # Variables para almacenar los datos de las tablas
        self.rules = []
        self.configs = []

    def refresh_data(self):
        """Recarga la lista de clientes desde la BD."""
        self.clientes_list = database.fetch_all_clients()
        self.render_list.refresh()

    def select_cliente(self, cliente):
        """Acción al hacer clic en un cliente de la lista."""
        self.selected_cliente = cliente
        # 1. Buscamos sus reglas y configs en la base de datos
        self.rules, self.configs = self.fetch_extraction_rules_and_config()
        
        # 2. Refrescamos todas las partes de la interfaz que dependen del cliente
        self.render_form.refresh()
        self.render_rules_table.refresh()
        self.render_configs_table.refresh()

    @ui.refreshable
    def render_list(self, search_query=''):
        """Renderiza la lista lateral de clientes."""
        query = search_query.lower()
        filtered = [c for c in self.clientes_list 
                    if query in (c.get('nombre') or '').lower() or query in (c.get('cif') or '').lower()]
        
        with ui.scroll_area().classes('h-[75vh]'):
            with ui.list().props('separator').classes('w-full'):
                for c in filtered:
                    with ui.item(on_click=lambda c=c: self.select_cliente(c)).classes('hover:bg-blue-50 cursor-pointer'):
                        with ui.item_section().props('avatar'):
                            ui.icon('person', color='blue-900')
                        with ui.item_section():
                            ui.item_label(c.get('nombre') or 'Sin nombre').classes('font-bold')
                            ui.item_label(f"CIF: {c.get('cif') or '---'}").classes('text-xs text-gray-500')

    @ui.refreshable
    def render_form(self):
        """Formulario de edición del cliente seleccionado."""
        if not self.selected_cliente:
            ui.label('Seleccione un cliente para ver detalles').classes('text-gray-400 mt-20 text-center w-full')
            return

        with ui.card().classes('w-full p-4'):
            ui.label(f"Editando: {self.selected_cliente.get('nombre')}").classes('text-lg font-bold mb-4')
            with ui.grid(columns=2).classes('w-full'):
                ui.input('Nombre').bind_value(self.selected_cliente, 'nombre').props('outlined dense')
                ui.input('CIF').bind_value(self.selected_cliente, 'cif').props('outlined dense')
                ui.input('Extractor Default').bind_value(self.selected_cliente, 'extractor_default').props('outlined dense')
                ui.input('Palabras Clave').bind_value(self.selected_cliente, 'palabras_clave').props('outlined dense')
            
            ui.button('GUARDAR CAMBIOS', on_click=self.guardar_cliente).classes('mt-4 bg-blue-900 text-white')

    @ui.refreshable
    def render_rules_table(self):
        """Tabla de Reglas Knowledge Base."""
        if not self.rules:
            ui.label('No hay reglas KB para este emisor.').classes('text-gray-400 italic p-4')
            return
        
        columns = [
            {'name': 'campo', 'label': 'Campo', 'field': 'campo', 'align': 'left'},
            {'name': 'ancla', 'label': 'Texto Ancla', 'field': 'ancla', 'align': 'left'},
            {'name': 'pagina', 'label': 'Pág', 'field': 'pagina'},
            {'name': 'confianza', 'label': 'Conf.', 'field': 'confianza'},
        ]
        ui.table(columns=columns, rows=self.rules, row_key='campo').props('dense flat border')

    @ui.refreshable
    def render_configs_table(self):
        """Tabla de Configuraciones de Extractor."""
        if not self.configs:
            ui.label('No hay configuraciones para este extractor.').classes('text-gray-400 italic p-4')
            return

        columns = [
            {'name': 'field_id', 'label': 'Campo ID', 'field': 'field_id', 'align': 'left'},
            {'name': 'type', 'label': 'Tipo', 'field': 'type', 'align': 'left'},
            {'name': 'ref_text', 'label': 'Ref. Text', 'field': 'ref_text', 'align': 'left'},
            {'name': 'value', 'label': 'Valor Fijo', 'field': 'value', 'align': 'left'},
        ]
        ui.table(columns=columns, rows=self.configs, row_key='config_id').props('dense flat border')

    def fetch_extraction_rules_and_config(self):
        """Obtiene reglas y configuraciones de la DB para el cliente actual."""
        if not self.selected_cliente:
            return [], []

        cif_cliente = self.selected_cliente.get('cif')
        extractor_name = self.selected_cliente.get('extractor_default')

        rules = []
        configs = []

        try:
            with database.get_db_connection() as conn:
                cursor = conn.cursor()

                # 1. Reglas Knowledge Base
                cursor.execute("""
                    SELECT campo, ancla, rel_x, rel_y, pagina, confianza
                    FROM knowledge_base
                    WHERE emisor_id = ?
                    ORDER BY campo
                """, (cif_cliente,))
                rules = [dict(row) for row in cursor.fetchall()]

                # 2. Configuraciones Extractor (Ajustado nombre de tabla a 'extractors')
                cursor.execute("""
                    SELECT ec.config_id, e.extractor_id, ec.field_id, ec.type, 
                           ec.ref_text, ec.offset, ec.segment, ec.value, ec.line
                    FROM extractor_configurations AS ec
                    JOIN extractors AS e ON ec.extractor_id = e.extractor_id
                    WHERE e.name = ?
                    ORDER BY ec.config_id
                """, (extractor_name,))
                configs = [dict(row) for row in cursor.fetchall()]

            print(f"LOG: {len(rules)} reglas y {len(configs)} configs cargadas para {cif_cliente}")
            return rules, configs

        except Exception as e:
            print(f"❌ Error DB Clientes: {e}")
            return [], []

    def guardar_cliente(self):
        if database.save_client(self.selected_cliente):
            ui.notify('Cliente actualizado correctamente', color='green')
            self.refresh_data()
        else:
            ui.notify('Error al guardar', color='red')

    def nuevo_cliente(self):
        self.selected_cliente = {'nombre': 'Nuevo Cliente', 'cif': '', 'extractor_default': 'Genérico'}
        self.rules, self.configs = [], []
        self.render_form.refresh()
        self.render_rules_table.refresh()
        self.render_configs_table.refresh()

    def exportar_excel(self):
        """Exporta los datos del cliente, reglas y configs a un Excel multi-pestaña."""
        if not self.selected_cliente:
            ui.notify('Seleccione un cliente primero', color='orange')
            return

        try:
            # 1. Crear DataFrames de Pandas
            df_cliente = pd.DataFrame([self.selected_cliente])
            df_rules = pd.DataFrame(self.rules)
            df_configs = pd.DataFrame(self.configs)

            # 2. Crear un buffer en memoria para el archivo Excel
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_cliente.to_excel(writer, sheet_name='Datos Generales', index=False)
                
                if not df_rules.empty:
                    df_rules.to_excel(writer, sheet_name='Reglas KB', index=False)
                
                if not df_configs.empty:
                    df_configs.to_excel(writer, sheet_name='Configuraciones', index=False)

            # 3. Descargar el archivo a través del navegador
            content = output.getvalue()
            nombre_archivo = f"Config_{self.selected_cliente.get('nombre', 'cliente')}.xlsx"
            
            ui.download(content, nombre_archivo)
            ui.notify('Exportación completada', color='green')

        except Exception as e:
            ui.notify(f'Error al exportar: {e}', color='red')
            print(f"Error Export: {e}")

    async def importar_excel(self, e):
        """Lee el Excel y actualiza Datos, Reglas KB y Configuración de Extractor."""
        try:
            content = e.content.read()
            # sheet_name=None carga todas las pestañas en un diccionario de DataFrames
            excel_data = pd.read_excel(io.BytesIO(content), sheet_name=None)
            
            # 1. ACTUALIZAR DATOS GENERALES DEL CLIENTE
            if 'Datos Generales' in excel_data:
                df_gen = excel_data['Datos Generales']
                if not df_gen.empty:
                    datos = df_gen.iloc[0].to_dict()
                    # Limpiar NaNs para SQLite
                    datos = {k: (None if pd.isna(v) else v) for k, v in datos.items()}
                    database.save_client(datos)
                    self.selected_cliente = datos

            cif = self.selected_cliente.get('cif')
            extractor_nombre = self.selected_cliente.get('extractor_default')

            # 2. ACTUALIZAR REGLAS KNOWLEDGE BASE (Pestaña 'Reglas KB')
            if 'Reglas KB' in excel_data and cif:
                self._import_rules_to_db(cif, excel_data['Reglas KB'])

            # 3. ACTUALIZAR CONFIGURACIÓN DE EXTRACTOR (Pestaña 'Configuraciones')
            if 'Configuraciones' in excel_data and extractor_nombre:
                self._import_configs_to_db(extractor_nombre, excel_data['Configuraciones'])

            ui.notify(f'Importación exitosa: {e.name}', color='green')
            
            # Recargar interfaz
            self.refresh_data()
            self.select_cliente(self.selected_cliente)

        except Exception as ex:
            ui.notify(f'Error crítico en importación: {ex}', color='red')
            print(f"Error Import: {ex}")

    def _import_rules_to_db(self, cif, df):
        """Reemplaza las reglas KB para un CIF específico."""
        with database.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM knowledge_base WHERE emisor_id = ?", (cif,))
            for _, row in df.iterrows():
                cursor.execute("""
                    INSERT INTO knowledge_base (emisor_id, campo, ancla, rel_x, rel_y, pagina, confianza)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (cif, row.get('campo'), row.get('ancla'), row.get('rel_x'), 
                      row.get('rel_y'), row.get('pagina', 0), row.get('confianza', 0.9)))
            conn.commit()

    def _import_configs_to_db(self, extractor_name, df):
        """Reemplaza la configuración de un extractor dinámico por su nombre."""
        with database.get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Primero obtenemos el ID del extractor para poder vincular las filas
            cursor.execute("SELECT extractor_id FROM extractors WHERE name = ?", (extractor_name,))
            res = cursor.fetchone()
            if not res:
                print(f"No se encontró el extractor {extractor_name}, saltando config.")
                return
            
            ext_id = res['extractor_id']
            
            # Limpiamos config antigua e insertamos la nueva
            cursor.execute("DELETE FROM extractor_configurations WHERE extractor_id = ?", (ext_id,))
            for _, row in df.iterrows():
                cursor.execute("""
                    INSERT INTO extractor_configurations (extractor_id, field_id, type, ref_text, offset, segment, value, line)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (ext_id, row.get('field_id'), row.get('type'), row.get('ref_text'), 
                      row.get('offset'), row.get('segment'), row.get('value'), row.get('line')))
            conn.commit()

# --- Instancia global ---
view = ClientesView()

def vista_clientes():
    view.refresh_data()
    
    with ui.row().classes('w-full items-center justify-between mb-4'):
        ui.label('Gestión de Clientes').classes('text-2xl font-bold text-blue-900')
        
        with ui.row().classes('gap-2 items-center'):
            # Botón Nuevo
            ui.button('NUEVO', icon='add', on_click=view.nuevo_cliente).classes('bg-green-700')
            
            # Botón Exportar
            ui.button('EXPORTAR', icon='download', on_click=view.exportar_excel).classes('bg-slate-800')
            
            # --- BOTÓN IMPORTAR (Solución robusta) ---
            # Usamos el propio ui.upload estilizado como botón para que NO falle el clic
            ui.upload(
                on_upload=view.importar_excel,
                auto_upload=True,
                label="IMPORTAR"
            ).props('flat color=primary icon=upload_file').classes('bg-slate-800 text-white rounded w-40 h-10')
            ui.tooltip('Importar configuración desde Excel')

    # Resto del código (columnas, tablas, etc.) igual...
    with ui.row().classes('w-full no-wrap gap-6'):
        with ui.column().classes('w-1/3 gap-4'):
            search = ui.input(placeholder='Buscar...').classes('w-full').props('outlined dense')
            search.on('update:model-value', lambda e: view.render_list.refresh(e.value))
            view.render_list()
        
        # Columna Derecha: Detalles y Tablas
        with ui.column().classes('flex-grow gap-4'):
            view.render_form()
            
            # Pestañas para las reglas y configuraciones
            with ui.tabs().classes('w-full') as tabs:
                ui.tab('Reglas KB')
                ui.tab('Config Extractor')
            
            with ui.tab_panels(tabs, value='Reglas KB').classes('w-full border'):
                with ui.tab_panel('Reglas KB'):
                    view.render_rules_table()
                with ui.tab_panel('Config Extractor'):
                    view.render_configs_table()