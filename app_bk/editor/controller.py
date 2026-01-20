import database
import logic
import tkinter as tk
import re
from tkinter import messagebox
import sqlite3

class EditorController:
    def __init__(self, view, engine, all_files=None, current_idx=0):
        """
        Inicializa el controlador del editor.
        :param view: Instancia de EditorView
        :param engine: Instancia de PDFEngine
        :param all_files: Lista de rutas de todas las facturas para navegación
        :param current_idx: Índice de la factura actual en la lista
        """
        self.view = view
        self.engine = engine
        
        # Estado de navegación entre archivos
        self.all_files = all_files or []
        self.current_idx = current_idx
        
        # Estado del documento actual
        self.pdf_path = None
        self.rect_id = None
        self.start_x = None
        self.start_y = None
        self.entries = {}

        # 1. Configuración de botones de la barra de herramientas
        self.view.btn_zoom_in.config(command=self.handle_zoom_in)
        self.view.btn_zoom_out.config(command=self.handle_zoom_out)
        self.view.btn_rotate.config(command=self.handle_rotate)
        
        # 2. Configuración de navegación entre facturas (Botones Anter. / Siguiente)
        self.view.btn_prev.config(command=self.prev_invoice)
        self.view.btn_next.config(command=self.next_invoice)

        # 3. Configuración del Selector de Extractor y Re-procesado
        try:
            nombres_extractores = database.get_all_extractor_names()
            self.view.combo_extractor['values'] = nombres_extractores
            self.view.btn_reprocesar.config(command=self.forzar_extraccion)
        except Exception as e:
            print(f"Error al inicializar selector de extractores: {e}")

        # 4. Binds del Canvas para selección de área y zoom
        self.view.canvas.bind("<ButtonPress-1>", self.on_press)
        self.view.canvas.bind("<B1-Motion>", self.on_drag)
        self.view.canvas.bind("<MouseWheel>", self.on_wheel)
        
        # Menú contextual (clic derecho) adaptado al sistema operativo
        if self.view.tk.call('tk', 'windowingsystem') == 'aqua': # macOS
            self.view.canvas.bind("<Button-2>", self.show_menu)
        else: # Windows/Linux
            self.view.canvas.bind("<Button-3>", self.show_menu)

    def load_file(self, path):
        """Carga un archivo PDF y recupera sus datos de la base de datos."""
        self.pdf_path = path
        self.engine.load_document(path)
        
        data = self.obtener_datos_completos(path)
        if data:
            # Detectar nombre del extractor analizando el Log
            log_text = data.get('log_data', '')
            nombre_extractor = "GENÉRICO"
            match = re.search(r"Usado extractor específico: .*?\.(\w+)", log_text)
            if match:
                nombre_extractor = match.group(1)
            
            # Actualizar interfaz con el extractor usado y el log
            self.view.lbl_extractor.config(text=f"Extractor: {nombre_extractor}")
            self.view.txt_log.delete('1.0', tk.END)
            self.view.txt_log.insert(tk.END, log_text)
            
            # Generar formulario de edición dinámico
            self.poblar_formulario(data)
            
        self.refresh_view()

    def obtener_datos_completos(self, path):
        """Consulta la base de datos para obtener la fila completa de la factura."""
        try:
            with database.get_db_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM processed_invoices WHERE path = ?", (path,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            print(f"Error al obtener datos de DB: {e}")
            return None

    def forzar_extraccion(self):
        nuevo_extractor = self.view.combo_extractor.get()
        if not nuevo_extractor:
            messagebox.showwarning("Aviso", "Selecciona un extractor.")
            return

        try:
            # 1. Llamamos a la lógica. ESTO DEVUELVE UNA TUPLA, NO UN DICCIONARIO
            resultado_tupla = logic.extraer_datos(self.pdf_path, debug_mode=True,extractor_manual=nuevo_extractor)
            
            # 2. Definimos las claves para convertir la tupla en diccionario (mismo orden que en logic.py)
            KEYS = ['Tipo', 'Fecha', 'Número de Factura', 'Emisor', 'CIF Emisor',
                    'Cliente', 'CIF', 'Modelo', 'Matricula', 'Importe', 'Base', 'IVA', 'Tasas']
            
            # Verificamos que tenemos datos
            if resultado_tupla:
                # Separamos datos y log (el último elemento es el log)
                datos_valores = resultado_tupla[:-1]
                log_data = resultado_tupla[-1]
                
                # Creamos el diccionario
                data_dict = dict(zip(KEYS, datos_valores))
                data_dict['DebugLines'] = log_data
                data_dict['Archivo'] = self.pdf_path # Necesario para consistencia
                
                # 3. Guardamos en la base de datos
                database.insert_invoice_data(data_dict, self.pdf_path, is_validated=0)
                
                # 4. Recargamos la interfaz
                self.load_file(self.pdf_path)
                messagebox.showinfo("Éxito", f"Factura re-procesada con {nuevo_extractor}")
            else:
                messagebox.showerror("Error", "No se pudieron obtener datos válidos.")
                
        except Exception as e:
            messagebox.showerror("Error", f"Fallo crítico: {e}")

    def next_invoice(self):
        """Navega a la siguiente factura en la lista."""
        if self.current_idx < len(self.all_files) - 1:
            self.current_idx += 1
            self.load_file(self.all_files[self.current_idx])

    def prev_invoice(self):
        """Navega a la factura anterior en la lista."""
        if self.current_idx > 0:
            self.current_idx -= 1
            self.load_file(self.all_files[self.current_idx])

    def refresh_view(self):
        """Renderiza la página actual del PDF en el canvas."""
        img = self.engine.get_page_image()
        total_pages = self.engine.pdf_doc.page_count
        self.view.lbl_page.config(text=f"Pág: {self.engine.current_page + 1} / {total_pages}")
        
        # Ajustar scroll y mostrar imagen
        self.view.canvas.config(scrollregion=(0, 0, self.engine.page_width, self.engine.page_height))
        self.view.canvas.create_image(0, 0, anchor=tk.NW, image=img)
        self.view.canvas.image = img
        self._setup_bindings()
        

    def poblar_formulario(self, data):
        """Genera los campos y asegura que el botón Guardar esté presente."""
        # Limpiar campos anteriores
        for widget in self.view.fields_container.winfo_children():
            widget.destroy()
        
        # Lista completa de campos incluyendo los nuevos
        campos_config = [
            ('numero_factura', 'Nº Factura'),
            ('fecha', 'Fecha'),
            ('emisor', 'Emisor'),
            ('cif_emisor', 'CIF Emisor'),
            ('cliente', 'Cliente (Receptor)'), # <--- Nuevo
            ('cif', 'CIF Cliente'),            # <--- Nuevo
            ('matricula', 'Matrícula'),
            ('modelo', 'Modelo'),
            ('concepto', 'Concepto'),
            ('tasas', 'Tasas'),
            ('iva_porcentaje', '% IVA'),
            ('base', 'Base Imponible'),
            ('iva', 'Cuota IVA'),
            ('importe', 'Total Importe')
        ]

        self.entries = {}
        for campo, etiqueta in campos_config:
            f = tk.Frame(self.view.fields_container)
            f.pack(fill=tk.X, pady=2)
            tk.Label(f, text=etiqueta, width=13, anchor='w').pack(side=tk.LEFT)
            
            var = tk.StringVar()
            valor_inicial = str(data.get(campo, '') or '')
            
            # Valor por defecto para % IVA
            if campo == 'iva_porcentaje' and (not valor_inicial or valor_inicial == 'None'):
                valor_inicial = "21"
                
            var.set(valor_inicial)
            ent = tk.Entry(f, textvariable=var)
            ent.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.entries[campo] = ent
            
            # Traza para cálculos automáticos cuando cambien valores clave
            if campo in ['importe', 'tasas', 'iva_porcentaje']:
                var.trace_add("write", lambda *args: self.recalcular_totales())

        # --- RE-INSERCIÓN DEL BOTÓN GUARDAR ---
        # Lo colocamos en un frame separado al final para que siempre sea visible
        btn_save = tk.Button(
            self.view.fields_container, 
            text="💾 Guardar Cambios y Entrenar", 
            bg="#28a745", 
            fg="white",
            font=('Arial', 10, 'bold'),
            pady=10,
            command=self.guardar_db
        )
        btn_save.pack(fill=tk.X, pady=20)
    
    def recalcular_totales(self):
        """Calcula automáticamente Base e IVA restando las tasas del importe total."""
        try:
            # Limpieza de datos (comas por puntos para cálculos)
            str_importe = self.entries['importe'].get().replace(',', '.') or "0"
            str_tasas = self.entries['tasas'].get().replace(',', '.') or "0"
            str_base = self.entries['base'].get().replace(',', '.') or "0"
            str_iva = self.entries['iva'].get().replace(',', '.') or "0"
            str_iva_pct = self.entries['iva_porcentaje'].get().replace(',', '.') or "21"

            importe_total = float(str_importe)
            base = float(str_base)
            tasas = float(str_tasas)
            iva = float(str_iva)
            iva_pct = float(str_iva_pct)

            print(f"⚙️ Traza Cálculo: Total({importe_total}) - Tasas({tasas}) | IVA: {iva_pct}%")

            # El IVA solo se aplica a lo que no son tasas
            sujeto_a_iva = importe_total - tasas
            
            if sujeto_a_iva < 0:
                print("⚠️ Traza: Las tasas no pueden ser mayores que el importe.")
                return

            base_calculada = sujeto_a_iva / (1 + (iva_pct / 100))
            iva_calculado = sujeto_a_iva - base_calculada

            # Actualizamos los campos en la interfaz
            self.entries['base'].delete(0, tk.END)
            self.entries['base'].insert(0, f"{base_calculada:.2f}")
            
            self.entries['iva'].delete(0, tk.END)
            self.entries['iva'].insert(0, f"{iva_calculado:.2f}")
            
            print(f"✅ Resultado: Base {base_calculada:.2f} | IVA {iva_calculado:.2f}")

        except ValueError:
            # Error silencioso mientras el usuario borra o escribe valores incompletos
            pass

    def guardar_db(self):
        """Guarda los datos y decide si aprender nuevas reglas."""
        # 1. Obtener si el usuario quiere que el sistema aprenda
        quiere_aprender = self.view.var_auto_aprender.get()
        
        print(f"💾 Traza: Guardando datos. ¿Aprender activado?: {quiere_aprender}")

        for campo, entry in self.entries.items():
            # --- CORRECCIÓN: Ignorar campos que solo son de UI (cálculo) ---
            if campo == 'iva_porcentaje':
                continue
            # ---------------------------------------------------------------

            valor = entry.get()
            
            # Solo intentamos guardar si el campo no es de cálculo
            try:
                database.update_invoice_field(self.pdf_path, campo, valor)
            except Exception as e:
                print(f"Error guardando campo {campo}: {e}")
                continue
            
            # 2. Solo aprendemos si el check está activo Y el campo fue editado (fondo amarillo)
            if quiere_aprender and entry.cget("background") == "#fff3cd":
                print(f"🧠 Aprendizaje: El campo '{campo}' ha sido corregido. Generando regla...")
                self.generar_regla_aprendizaje(campo, valor)

        messagebox.showinfo("Éxito", "Cambios guardados correctamente.")

    def generar_regla_aprendizaje(self, campo, valor_corregido):
        # 1. Identificar quién es el emisor (prioridad: CIF > Nombre > Extractor)
        emisor_id = self.entries.get('cif_emisor').get() or self.entries.get('emisor').get() or "GENERICO"
        
        # 2. Obtener las coordenadas del rectángulo rojo que dibujó el usuario
        if not self.rect_id:
            return # Si no hay rectángulo dibujado, no podemos aprender posición
            
        coords_rect = self.view.canvas.coords(self.rect_id) # [x1, y1, x2, y2]
        
        # 3. Llamar al motor para buscar un "Ancla" (texto estático cerca del rectángulo)
        ancla_data = self.engine.find_nearest_anchor(coords_rect)
        
        if ancla_data:
            # Calculamos la distancia relativa
            rel_x = coords_rect[0] - ancla_data['x']
            rel_y = coords_rect[1] - ancla_data['y']
            
            # --- CORRECCIÓN AQUÍ ---
            # Pasamos los argumentos desglosados, tal como lo pide database.py
            database.save_learning_rule(
                emisor_id,             # 1. Emisor
                campo,                 # 2. Campo
                ancla_data['texto'],   # 3. Ancla
                rel_x,                 # 4. Distancia X (Antes pasabas el dict completo aquí)
                rel_y,                 # 5. Distancia Y
                self.engine.current_page # 6. Página (Ahora sí llega a su sitio)
            )
            print(f"🧠 Sistema Entrenado: Cuando veas '{ancla_data['texto']}', "
                f"el campo '{campo}' está a {rel_x:.1f}, {rel_y:.1f} px.")

    # --- Lógica de Interacción con el PDF (Mouse) ---
    def on_press(self, event):
        self.start_x = self.view.canvas.canvasx(event.x)
        self.start_y = self.view.canvas.canvasy(event.y)
        if self.rect_id: 
            self.view.canvas.delete(self.rect_id)
        self.rect_id = self.view.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline='red', width=2)

    def on_drag(self, event):
        cur_x = self.view.canvas.canvasx(event.x)
        cur_y = self.view.canvas.canvasy(event.y)
        self.view.canvas.coords(self.rect_id, self.start_x, self.start_y, cur_x, cur_y)

    def on_wheel(self, event):
        if event.delta > 0: self.handle_zoom_in()
        else: self.handle_zoom_out()

    def handle_zoom_in(self): self.engine.zoom_in(); self.refresh_view()
    def handle_zoom_out(self): self.engine.zoom_out(); self.refresh_view()
    def handle_rotate(self): self.engine.rotate_cw(); self.refresh_view()

    def _setup_bindings(self):
        """Vincula los eventos de teclado y foco para recalcular automáticamente."""
        campos_clave = ['base', 'importe', 'iva', 'tasas', 'iva_porcentaje']
        
        for campo in campos_clave:
            if campo in self.entries:
                entry = self.entries[campo]
                # Al pulsar ENTER
                entry.bind('<Return>', lambda event, c=campo: self.on_manual_change(c))
                # Al perder el foco (clic fuera o TAB)
                entry.bind('<FocusOut>', lambda event, c=campo: self.on_manual_change(c))

    def on_manual_change(self, campo_modificado):
        """Se ejecuta cuando el usuario escribe y termina de editar."""
        self.recalcular_totales(origen=campo_modificado)

    def _parse_float(self, valor_str):
        """Convierte texto (1.234,56 o 1234.56) a float seguro."""
        if not valor_str: return 0.0
        try:
            # Limpieza: quitamos símbolos de moneda y espacios
            limpio = valor_str.replace('€', '').strip()
            if ',' in limpio and '.' in limpio:
                # Caso complejo: 1.200,50 -> quitamos punto, cambiamos coma
                limpio = limpio.replace('.', '').replace(',', '.')
            elif ',' in limpio:
                # Caso estándar español: 1200,50 -> cambiamos coma por punto
                limpio = limpio.replace(',', '.')
            return float(limpio)
        except ValueError:
            return 0.0

    def recalcular_totales(self, origen='base'):
        """
        Calcula Base, IVA y Total manteniendo la coherencia matemática.
        Fórmula: Total = Base + IVA + Tasas
        """
        try:
            # 1. Obtener valores actuales limpios
            base = self._parse_float(self.entries['base'].get())
            importe_total = self._parse_float(self.entries['importe'].get())
            tasas = self._parse_float(self.entries.get('tasas').get()) # Tasas puede no existir
            
            # Porcentaje de IVA (por defecto 21 si está vacío)
            iva_pct_str = self.entries.get('iva_porcentaje').get()
            iva_pct = self._parse_float(iva_pct_str) if iva_pct_str else 21.0
            
            nuevo_base = base
            nuevo_iva = 0.0
            nuevo_total = importe_total

            # 2. Lógica de Cálculo según qué campo tocó el usuario
            if origen == 'importe':
                # INVERSO: Total -> Base (descontando tasas primero)
                # Base = (Total - Tasas) / (1 + %IVA)
                subtotal_sin_tasas = importe_total - tasas
                nuevo_base = subtotal_sin_tasas / (1 + (iva_pct / 100))
                nuevo_iva = subtotal_sin_tasas - nuevo_base
                nuevo_total = importe_total # El total es lo que el usuario puso

            elif origen in ['base', 'iva_porcentaje']:
                # DIRECTO: Base -> Total
                nuevo_iva = base * (iva_pct / 100)
                nuevo_total = base + nuevo_iva + tasas
            
            elif origen == 'tasas':
                # Si cambian las tasas, sumamos al total manteniendo la base
                nuevo_iva = base * (iva_pct / 100)
                nuevo_total = base + nuevo_iva + tasas

            # 3. Actualizar la Interfaz (formato con 2 decimales)
            # Usamos una función auxiliar para no disparar eventos en bucle
            self._update_entry_safe('base', f"{nuevo_base:.2f}")
            self._update_entry_safe('iva', f"{nuevo_iva:.2f}")
            self._update_entry_safe('importe', f"{nuevo_total:.2f}")
            self._update_entry_safe('tasas', f"{tasas:.2f}")

        except Exception as e:
            print(f"Error en cálculo: {e}")

    def _update_entry_safe(self, campo, valor):
        """Actualiza un campo sin disparar eventos recursivos."""
        if campo in self.entries:
            entry = self.entries[campo]
            actual = entry.get()
            # Solo actualizamos si el valor ha cambiado para evitar parpadeos
            if actual != valor:
                entry.delete(0, tk.END)
                entry.insert(0, str(valor).replace('.', ',')) # Formato español visual

    def show_menu(self, event):
        """Muestra el menú contextual con trazas de depuración."""
        if not self.rect_id: 
            print("🔍 Traza: Intento de menú sin rectángulo.")
            return
            
        self.view.context_menu.delete(0, tk.END)
        coords = self.view.canvas.coords(self.rect_id)
        print(f"🔍 Traza: Coordenadas detectadas: {coords}")

        # Extraer texto usando el motor
        texto_detectado = ""
        if hasattr(self.engine, 'get_text_from_coords'):
            texto_detectado = self.engine.get_text_from_coords(*coords)
            print(f"🔍 Traza: Texto extraído del PDF: '{texto_detectado}'")
        else:
            print("⚠️ Traza: Error - engine no tiene 'get_text_from_coords'")

        if not texto_detectado:
            self.view.context_menu.add_command(label="No se detectó texto", state="disabled")
        else:
            # Mostrar previsualización del texto
            resumen = (texto_detectado[:15] + '..') if len(texto_detectado) > 15 else texto_detectado
            self.view.context_menu.add_command(label=f"Copiar: {resumen}", state="disabled")
            self.view.context_menu.add_separator()

            # Campos destino (excluyendo los que se calculan solos)
            for campo in self.entries.keys():
                    
                nombre_label = campo.replace('_', ' ').title()
                self.view.context_menu.add_command(
                    label=f"Asignar a {nombre_label}",
                    command=lambda c=campo, t=texto_detectado: self.asignar_valor(c, t)
                )

        self.view.context_menu.post(event.x_root, event.y_root)

    def asignar_valor(self, campo, texto):
        """Método llamado por el menú contextual (Click derecho)."""
        print(f"🚀 Traza: Asignando '{texto}' al campo '{campo}'")
        if campo in self.entries:
            self.entries[campo].delete(0, tk.END)
            self.entries[campo].insert(0, texto.strip())
            self.entries[campo].config(background="#fff3cd")
            
            # AQUÍ LLAMAMOS AL RECALCULO FORZANDO EL ORIGEN
            if campo in ['importe', 'tasas', 'base', 'iva']:
                self.recalcular_totales(origen=campo)

    def next_page(self):
        """Cambia a la siguiente página del PDF."""
        if self.engine.pdf_doc and self.engine.current_page < self.engine.pdf_doc.page_count - 1:
            self.engine.current_page += 1
            self.refresh_view()

    def prev_page(self):
        """Cambia a la página anterior del PDF."""
        if self.engine.pdf_doc and self.engine.current_page > 0:
            self.engine.current_page -= 1
            self.refresh_view()