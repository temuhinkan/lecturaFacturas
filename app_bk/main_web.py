import flet as ft
import os
import database
import logic
from PDFEngineWeb import PDFEngineWeb

# Aseguramos que la BBDD esté lista al iniciar
database.setup_database()
database.initialize_extractors_data()

def main(page: ft.Page):
    page.title = "Sistema de Gestión de Facturas (Web)"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0

    # --- Lógica de la Vista EDITOR (El Visor + Formulario) ---
    def vista_editor(invoice_path):
        # 1. Preparar el motor PDF
        engine = PDFEngineWeb()
        if not engine.load_document(invoice_path):
            return ft.View("/error", [ft.Text("Error cargando archivo")])

        # Obtener imagen para web
        img_b64, w, h = engine.get_page_image_b64()

        # Variables de estado para el rectángulo de selección
        start_x = 0
        start_y = 0
        
        # Componentes UI reactivos
        rect_selection = ft.Container(
            border=ft.border.all(2, "red"),
            bgcolor=ft.colors.with_opacity(0.3, "red"),
            visible=False,
            top=0, left=0, width=0, height=0,
        )

        txt_log = ft.Text("Listo para extraer...", size=12, color="grey")

        # Campos del formulario (Refs para poder leerlos/escribirlos)
        fields = {
            "numero_factura": ft.Ref[ft.TextField](),
            "fecha": ft.Ref[ft.TextField](),
            "emisor": ft.Ref[ft.TextField](),
            "cif_emisor": ft.Ref[ft.TextField](),
            "importe": ft.Ref[ft.TextField](),
            "base": ft.Ref[ft.TextField](),
            "iva": ft.Ref[ft.TextField](),
        }

        # Cargar datos existentes de la BBDD
        existing_data = {}
        try:
            with database.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM processed_invoices WHERE path = ?", (invoice_path,))
                row = cursor.fetchone()
                if row: existing_data = dict(row)
        except Exception as e:
            print(f"Error BBDD: {e}")

        # Función para asignar valor a un campo desde el menú o lógica
        def asignar_valor(campo, valor):
            if campo in fields and fields[campo].current:
                fields[campo].current.value = valor
                fields[campo].current.update()

        # Eventos del Mouse (Dibujar rectángulo)
        def on_pan_start(e: ft.DragStartEvent):
            nonlocal start_x, start_y
            start_x = e.local_x
            start_y = e.local_y
            rect_selection.left = start_x
            rect_selection.top = start_y
            rect_selection.width = 0
            rect_selection.height = 0
            rect_selection.visible = True
            rect_selection.update()

        def on_pan_update(e: ft.DragUpdateEvent):
            rect_selection.width = abs(e.local_x - start_x)
            rect_selection.height = abs(e.local_y - start_y)
            rect_selection.update()

        def on_pan_end(e: ft.DragEndEvent):
            # 1. Obtener coordenadas finales
            x1, y1 = start_x, start_y
            x2 = start_x + rect_selection.width
            y2 = start_y + rect_selection.height
            
            # 2. Extraer texto usando el motor
            texto = engine.get_text_from_web_coords(x1, y1, x2, y2)
            txt_log.value = f"Texto detectado: {texto}"
            txt_log.update()
            
            # 3. Mostrar menú contextual (BottomSheet) para asignar
            mostrar_menu_asignacion(texto)

        def mostrar_menu_asignacion(texto):
            def asignar_y_cerrar(e, campo):
                asignar_valor(campo, texto)
                bs.open = False
                bs.update()

            # Opciones del menú
            opciones = []
            for key, ref in fields.items():
                nombre = key.replace("_", " ").title()
                opciones.append(
                    ft.ListTile(
                        title=ft.Text(f"Asignar a {nombre}"),
                        on_click=lambda e, c=key: asignar_y_cerrar(e, c)
                    )
                )

            bs = ft.BottomSheet(
                ft.Container(
                    ft.Column([
                        ft.Text(f"Texto: {texto}", weight="bold"),
                        ft.Divider(),
                        ft.Column(opciones, scroll=ft.ScrollMode.AUTO, height=200)
                    ], padding=10),
                    padding=10
                )
            )
            page.overlay.append(bs)
            bs.open = True
            page.update()

        def guardar_cambios(e):
            # Guardar en BBDD
            for key, ref in fields.items():
                if ref.current:
                    database.update_invoice_field(invoice_path, key, ref.current.value)
            
            snack = ft.SnackBar(ft.Text("✅ Factura guardada correctamente"))
            page.overlay.append(snack)
            snack.open = True
            page.update()

        # --- LAYOUT DEL EDITOR ---
        
        # Columna Izquierda: Visor Interactivo
        visor_stack = ft.Stack(
            [
                ft.Image(src_base64=img_b64, fit=ft.ImageFit.CONTAIN, width=w, height=h),
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

        # Columna Derecha: Formulario
        form_controls = [
            ft.Text("Editar Factura", size=20, weight="bold"),
            ft.Divider(),
            ft.TextField(ref=fields["numero_factura"], label="Nº Factura", value=existing_data.get("numero_factura", "")),
            ft.TextField(ref=fields["fecha"], label="Fecha", value=existing_data.get("fecha", "")),
            ft.TextField(ref=fields["emisor"], label="Emisor", value=existing_data.get("emisor", "")),
            ft.TextField(ref=fields["cif_emisor"], label="CIF Emisor", value=existing_data.get("cif_emisor", "")),
            ft.Divider(),
            ft.Row([
                ft.TextField(ref=fields["base"], label="Base", value=str(existing_data.get("base", "")), expand=1),
                ft.TextField(ref=fields["iva"], label="IVA", value=str(existing_data.get("iva", "")), expand=1),
            ]),
            ft.TextField(ref=fields["importe"], label="TOTAL", value=str(existing_data.get("importe", "")), text_size=18, weight="bold"),
            ft.Divider(),
            txt_log,
            ft.ElevatedButton("Guardar Cambios", on_click=guardar_cambios, bgcolor="green", color="white", height=50)
        ]

        return ft.View(
            f"/editor",
            [
                ft.AppBar(title=ft.Text(f"Editando: {os.path.basename(invoice_path)}"), bgcolor="blue"),
                ft.Row(
                    [
                        ft.Container(content=ft.Column([visor_stack], scroll=ft.ScrollMode.AUTO), expand=2, bgcolor="#f0f0f0", padding=10),
                        ft.Container(content=ft.Column(form_controls, scroll=ft.ScrollMode.AUTO), expand=1, padding=20)
                    ],
                    expand=True
                )
            ]
        )

    # --- Lógica de la Vista HOME (Tabla de Facturas) ---
    def vista_home():
        invoices = database.fetch_all_invoices()
        
        filas = []
        for inv in invoices:
            is_valid = inv['is_validated'] == 1
            icon = ft.Icon(ft.icons.CHECK_CIRCLE, color="green") if is_valid else ft.Icon(ft.icons.WARNING, color="orange")
            
            # Click en la fila para ir al editor
            # Usamos un lambda que captura el path
            filas.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(icon),
                        ft.DataCell(ft.Text(os.path.basename(inv['path']))),
                        ft.DataCell(ft.Text(inv['emisor'] or "")),
                        ft.DataCell(ft.Text(inv['fecha'] or "")),
                        ft.DataCell(ft.Text(f"{inv['importe']} €" if inv['importe'] else "")),
                    ],
                    on_select_changed=lambda e, p=inv['path']: page.go(f"/editor?path={p}")
                )
            )

        tabla = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Estado")),
                ft.DataColumn(ft.Text("Archivo")),
                ft.DataColumn(ft.Text("Emisor")),
                ft.DataColumn(ft.Text("Fecha")),
                ft.DataColumn(ft.Text("Total")),
            ],
            rows=filas,
            border=ft.border.all(1, "grey"),
            vertical_lines=ft.border.BorderSide(1, "grey"),
            horizontal_lines=ft.border.BorderSide(1, "grey"),
        )

        return ft.View(
            "/",
            [
                ft.AppBar(title=ft.Text("Dashboard de Facturas"), bgcolor="blue"),
                ft.Container(
                    content=ft.Column([
                        ft.Text("Mis Facturas", size=30, weight="bold"),
                        ft.ElevatedButton("Recargar", on_click=lambda _: page.go("/")), # Recarga simple
                        tabla
                    ], scroll=ft.ScrollMode.AUTO),
                    padding=20,
                    expand=True
                )
            ]
        )

    # --- Router (Gestor de Navegación) ---
    def route_change(route):
        page.views.clear()
        
        # Ruta Principal (Home)
        if page.route == "/":
            page.views.append(vista_home())
            
        # Ruta Editor (ej: /editor?path=C:/facturas/fac1.pdf)
        elif page.route.startswith("/editor"):
            # Extraer el parámetro 'path' de la URL
            try:
                # Forma simple de parsear params en string
                path_param = page.route.split("?path=")[1]
                # En web real, decodificaríamos URL, aquí asumimos path local directo
                page.views.append(vista_editor(path_param))
            except IndexError:
                page.views.append(ft.View("/error", [ft.Text("Falta el path de la factura")]))

        page.update()

    def view_pop(view):
        page.views.pop()
        top_view = page.views[-1]
        page.go(top_view.route)

    page.on_route_change = route_change
    page.on_view_pop = view_pop
    
    # Iniciar en Home
    page.go("/")

ft.run(main, view=ft.AppView.WEB_BROWSER)