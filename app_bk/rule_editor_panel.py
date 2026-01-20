# rule_editor_panel.py

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Dict, Any, List, Optional
import json

from document_utils import get_document_lines
# Importaciones de módulos existentes (asumidos)
# Las constantes y módulos son importados por la App principal (self.app)
# y se acceden a través de ella.
# Se necesita rule_suggester y BaseInvoiceExtractor (accedidos vía self.app)
# y get_document_lines (vía self.app.get_document_lines)

# Constantes de reglas (MOCK_EXTRACTION_FIELDS copiado aquí para el ComboBox)
MOCK_EXTRACTION_FIELDS = [
    'TIPO', 'FECHA', 'NUM_FACTURA', 'EMISOR', 'CIF_EMISOR', 'CLIENTE', 
    'CIF', 'MODELO', 'MATRICULA', 'IMPORTE', 'BASE', 'IVA', 'TASAS'
]

NEW_RULE_TEMPLATE = {
    'type': 'VARIABLE',
    'ref_text': '',
    'offset': 0,
    'segment': 2,
    'value': ''
}


class RuleEditorPanel:
    
    def __init__(self, parent_frame, app_instance):
        self.app = app_instance
        self.parent = parent_frame
        
        self.rule_action_label = tk.StringVar(value="Seleccione una regla para editar o Añadir una Nueva")
        
        # Inicializar variables para el editor de reglas (conectadas a self.app.rule_vars)
        self.app.rule_vars = {
            'type': tk.StringVar(value=NEW_RULE_TEMPLATE['type']),
            'ref_text': tk.StringVar(value=NEW_RULE_TEMPLATE['ref_text']),
            'line': tk.StringVar(value=''),
            'offset': tk.StringVar(value=str(NEW_RULE_TEMPLATE['offset'])),
            'segment': tk.StringVar(value=str(NEW_RULE_TEMPLATE['segment'])),
            'value': tk.StringVar(value=NEW_RULE_TEMPLATE['value']),
        }
        
        self._create_rule_editor_panel(parent_frame)
        self._load_rules_for_selected_field() # Carga inicial

    def _create_rule_editor_panel(self, parent):
        """Panel para editar las reglas de extracción."""
        parent.config(padding="10")

        # 1. Selección del Campo (Key)
        field_selection_frame = ttk.LabelFrame(parent, text="1. Seleccionar Campo de Extracción", padding=10)
        field_selection_frame.pack(fill=tk.X, pady=5)
        ttk.Label(field_selection_frame, text="Campo de Destino:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        
        self.app.rule_target_var = tk.StringVar()
        self.app.rule_target_var.set(MOCK_EXTRACTION_FIELDS[0])
        field_combobox = ttk.Combobox(
            field_selection_frame, textvariable=self.app.rule_target_var, values=MOCK_EXTRACTION_FIELDS, state='readonly'
        )
        field_combobox.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=2)
        field_selection_frame.columnconfigure(1, weight=1)
        self.app.rule_target_var.trace_add("write", self._load_rules_for_selected_field)

        # 2. Lista de Reglas Existentes
        rules_list_frame = ttk.LabelFrame(parent, text="2. Reglas Actuales", padding=10)
        rules_list_frame.pack(fill=tk.X, pady=5)
        self.rules_listbox = tk.Listbox(rules_list_frame, height=5)
        self.rules_listbox.pack(fill=tk.X, expand=True)
        self.rules_listbox.bind('<<ListboxSelect>>', self._select_rule_from_listbox)
        
        # 3. Definición de Regla Activa
        rule_definition_frame = ttk.LabelFrame(parent, text="3. Regla Activa (Parámetros y Selección)", padding=10)
        rule_definition_frame.pack(fill=tk.X, pady=5)
        # (Se asume que la creación de todas las entradas (type, ref_text, line, offset, segment, value) va aquí, usando self.app.rule_vars)
        # AÑADIR: Una etiqueta dentro del marco para mostrar el estado dinámico (self.rule_action_label)
        ttk.Label(rule_definition_frame, textvariable=self.rule_action_label, foreground='blue').grid(row=0, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(0, 5))
        # Ejemplo de una sola entrada
        # Los siguientes elementos (Tipo de Regla, etc.) deberían empezar en la fila 1
        ttk.Label(rule_definition_frame, text="Tipo de Regla ('type'):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Combobox(rule_definition_frame, textvariable=self.app.rule_vars['type'], values=['VARIABLE', 'FIXED', 'FIXED_VALUE']).grid(row=1, column=1, sticky=tk.EW, padx=5, pady=2)
        
        # 4. Generación de Código y Botones de Acción
        code_output_frame = ttk.LabelFrame(parent, text="4. Regla Generada (Para Copiar en el Extractor)", padding=10)
        code_output_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.generated_rule_text = ScrolledText(code_output_frame, wrap=tk.WORD, height=8, font=('Consolas', 9))
        self.generated_rule_text.pack(fill=tk.BOTH, expand=True)
        
        action_button_frame = ttk.Frame(code_output_frame)
        action_button_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(action_button_frame, text="📝 Actualizar Código de Regla", command=self._generate_rule_code ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))
        ttk.Button(action_button_frame, text="➕ Añadir Regla", command=self._add_new_rule ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        ttk.Button(action_button_frame, text="💾 Actualizar Regla", command=self._update_existing_rule ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        ttk.Button(action_button_frame, text="🗑️ Eliminar Regla", command=self._delete_rule ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(5, 0))
        ttk.Button(action_button_frame, text="🧪 Probar Regla", command=self._test_rule ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(5, 0))

    def update_rule_editor_after_load(self):
        """Actualiza el editor de reglas (lista de reglas) tras cargar una nueva factura."""
        if self.app.rule_target_var:
            self._load_rules_for_selected_field()
            self.app.extractor_name_label_var.set(f"{self.app.extractor_name}.py")


    def _update_rule_editor_with_selection(self, selected_word: str, selected_line_content: Optional[str]):
        """
        Llamado por el visor para aplicar el texto seleccionado al editor.
        (El código del editor de reglas es muy extenso, se asume que se traslada fielmente)
        """
        if self.app.current_rule_index is None:
            # Si no hay regla seleccionada, usar la lógica para sugerir una regla nueva (el botón)
            if selected_word and selected_line_content and hasattr(self.app, 'rule_suggester'):
                # Si existe el módulo rule_suggester (asumido por el import original)
                suggested_rule = self.app.rule_suggester.suggest_best_rule(selected_word, selected_line_content)
                self.app.rule_vars['type'].set(suggested_rule.get('type', 'VARIABLE'))
                # ... (Actualizar las demás variables con la sugerencia) ...
                self.rule_action_label = tk.StringVar(value="Seleccione una regla para editar o Añadir una Nueva")  

        # Si hay un campo de datos activo, se aplica la selección como 'value' a ese campo
        if self.app.active_data_field:
            self._apply_selected_text_to_rule_value(selected_word)
    
    def _apply_selected_text_to_rule_value(self, selected_word: str):
        """ Aplica el texto seleccionado al campo 'value' de la regla actual (si la hay) o de una nueva. """
        # La lógica completa de aplicación de selección va aquí
        # ...
        self.app.rule_vars['value'].set(selected_word)
        self._generate_rule_code() # Refrescar el código generado

    def _load_rules_for_selected_field(self, *args):
        # *********** Mover lógica completa de _load_rules_for_selected_field aquí ***********
        field_key = self.app.rule_target_var.get()
        self.app.current_field_rules = self.app.current_extractor_mapping.get(field_key, [])
        self.app.current_rule_index = None 
        
        self.rules_listbox.delete(0, tk.END)
        if not self.app.current_field_rules:
            self.rules_listbox.insert(tk.END, "⚠️ No hay reglas definidas para este campo. ¡Añade una!")
            self.rule_action_label.set("Nueva Regla: Defina los parámetros.")
        else:
            # ... (Lógica de llenado del listbox)
            for i, rule in enumerate(self.app.current_field_rules):
                rule_str = json.dumps(rule, ensure_ascii=False).replace('"', "'")
                self.rules_listbox.insert(tk.END, f"Regla {i+1}: {rule_str}")

            self.rules_listbox.select_set(0)
            self.rules_listbox.event_generate("<<ListboxSelect>>")

    def _select_rule_from_listbox(self, event):
        # *********** Mover lógica completa de _select_rule_from_listbox aquí ***********
        # ... (Lógica de selección y llenado del formulario de edición)
        try:
            selection = self.rules_listbox.curselection()
            if not selection:
                self.app.current_rule_index = None
                self._reset_rule_form(NEW_RULE_TEMPLATE['type'])
                self.rule_action_label.set("Nueva Regla: Defina los parámetros.")
                return

            idx = selection[0]
            self.app.current_rule_index = idx
            rule = self.app.current_field_rules[idx]
            self.rule_action_label.set(f"Regla {idx + 1} de {len(self.app.current_field_rules)}: Editando")
            
            # Llenar las variables de la GUI
            for k, v in NEW_RULE_TEMPLATE.items():
                 self.app.rule_vars[k].set(str(rule.get(k, v)))
            self.app.rule_vars['line'].set(str(rule.get('line', ''))) # Manejo especial para 'line'

            self._generate_rule_code()

        except Exception as e:
            messagebox.showerror("Error de Selección", f"Error al cargar la regla: {e}")

    # (Métodos auxiliares: _get_current_rule_dict, _clean_rule_dict se trasladan aquí)
    def _get_current_rule_dict(self) -> Dict[str, Any]:
        rule_dict = {k: self.app.rule_vars[k].get() for k in self.app.rule_vars}
        return self._clean_rule_dict(rule_dict)

    def _clean_rule_dict(self, rule_dict: Dict[str, Any]) -> Dict[str, Any]:
        # *********** Mover lógica completa de _clean_rule_dict aquí ***********
        rule_type = rule_dict.get('type')
        # Limpieza de valores vacíos y de campos irrelevantes
        # ...
        return rule_dict

    def _add_new_rule(self):
        # *********** Mover lógica completa de _add_new_rule aquí ***********
        field_key = self.app.rule_target_var.get()
        new_rule = self._get_current_rule_dict()

        if len(new_rule) <= 1:
            messagebox.showwarning("Advertencia", "La regla está incompleta.")
            return

        if field_key not in self.app.current_extractor_mapping:
            self.app.current_extractor_mapping[field_key] = []
        self.app.current_extractor_mapping[field_key].append(new_rule)
        
        messagebox.showinfo("Regla Añadida", f"Nueva regla añadida al campo '{field_key}'.")
        self._load_rules_for_selected_field()

    def _update_existing_rule(self):
        # *********** Mover lógica completa de _update_existing_rule aquí ***********
        if self.app.current_rule_index is None:
            messagebox.showwarning("Advertencia", "Seleccione una regla para actualizar.")
            return
        
        updated_rule = self._get_current_rule_dict()
        self.app.current_field_rules[self.app.current_rule_index] = updated_rule
        self.app.current_extractor_mapping[self.app.rule_target_var.get()] = self.app.current_field_rules
        
        messagebox.showinfo("Regla Actualizada", "Regla actualizada con éxito.")
        self._load_rules_for_selected_field()


    def _delete_rule(self):
        # *********** Mover lógica completa de _delete_rule aquí ***********
        if self.app.current_rule_index is None:
            messagebox.showwarning("Advertencia", "Seleccione una regla para eliminar.")
            return

        if messagebox.askyesno("Confirmar Eliminación", f"¿Desea eliminar la Regla {self.app.current_rule_index + 1} para el campo '{self.app.rule_target_var.get()}'?"):
            self.app.current_field_rules.pop(self.app.current_rule_index)
            self.app.current_extractor_mapping[self.app.rule_target_var.get()] = self.app.current_field_rules
            messagebox.showinfo("Regla Eliminada", "Regla eliminada.")
            self._load_rules_for_selected_field()

    def _generate_rule_code(self):
        # *********** Mover lógica completa de _generate_rule_code aquí ***********
        rule_dict = self._get_current_rule_dict()
        
        code_str = json.dumps(rule_dict, indent=4, ensure_ascii=False)
        
        self.generated_rule_text.config(state=tk.NORMAL)
        self.generated_rule_text.delete(1.0, tk.END)
        self.generated_rule_text.insert(tk.END, code_str)
        self.generated_rule_text.config(state=tk.DISABLED)

    def _test_rule(self):
        # *********** Mover lógica completa de _test_rule aquí ***********
        rule_dict = self._get_current_rule_dict()

        if not self.app.file_path:
            messagebox.showerror("Error", "No hay documento cargado para probar.")
            return
        
       # CORRECCIÓN: Usamos la función importada directamente, no a través de self.app
        lines = get_document_lines(self.app.file_path)  
        
        try:
            # 4. Instanciar el Extractor Base (Sandbox)
            extractor = self.app.BaseInvoiceExtractor(lines, self.app.file_path) 
            
            # 5. Probar la regla
            result = extractor._apply_rule(rule_dict, self.app.rule_target_var.get()) # Asumiendo un método _apply_rule
            
            # 6. Mostrar el resultado al usuario
            if result:
                messagebox.showinfo("✅ Resultado de la Prueba", f"La regla extrajo con éxito:\n\nValor: '{result}'")
            else:
                messagebox.showwarning("❌ Resultado de la Prueba", "La regla no extrajo ningún valor con la configuración actual.")
                
        except Exception as e:
            messagebox.showerror("Error de Ejecución", f"Error al ejecutar la lógica de prueba: {e}")