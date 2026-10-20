# src/synoptic_form/view.py
# Define la clase de la ventana principal y todos sus widgets (la Vista).
# Versión final con navegación a la derecha, color de tema y scroll mejorado.

import customtkinter as ctk

HEADER_COLOR_PRIMARY = "#16a085"
TABLE_HEADER_COLOR = "#34495e"
NAV_BUTTON_HOVER_COLOR = ("gray70", "gray30")

class SynopticFormView(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Formulario de Datos Meteorológicos")
        self.geometry("1250x900")
        ctk.set_appearance_mode("dark")
        
        self.entries = {}
        self.results = {}
        
        # --- CAMBIO 1: Configuración del grid para poner el menú a la derecha ---
        self.grid_columnconfigure(0, weight=1) # Columna 0 (contenido) se expande
        self.grid_rowconfigure(0, weight=1)

        # --- CONTENIDO PRINCIPAL (EL FORMULARIO) ---
        self.main_frame = ctk.CTkScrollableFrame(self, label_text="Formulario de Datos Meteorológicos")
        self.main_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        # --- BARRA DE NAVEGACIÓN ---
        self.nav_frame = self._create_navigation_frame()
        self.nav_frame.grid(row=0, column=1, sticky="nsw") # Se coloca en la columna 1

        # El resto de la creación de la UI
        self.meteo_table_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.meteo_table_frame.pack(fill="x", expand=True, padx=10, pady=10)

        self.calc_table_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.calc_table_frame.pack(fill="x", expand=True, padx=10, pady=(20, 10))

        self.create_meteorological_table()
        self.create_station_calculations_table()
        
        error_label = ctk.CTkLabel(self.main_frame, text="", text_color="#e74c3c", font=ctk.CTkFont(size=12))
        error_label.pack(pady=5)
        self.results["error_label"] = error_label
        
        # --- CAMBIO 3: Habilitar el scroll con la rueda del ratón de forma explícita ---
        self.bind_mouse_wheel(self.main_frame, self.main_frame._parent_canvas)

    def bind_mouse_wheel(self, frame_to_bind, canvas):
        """Función para asegurar que la rueda del ratón funcione en el scrollable frame."""
        def on_mouse_wheel(event):
            # En Linux, event.delta es 120 para arriba y -120 para abajo
            # event.num es 4 para arriba y 5 para abajo
            if event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")

        # <MouseWheel> funciona en Windows/macOS, <Button-4/5> en Linux
        frame_to_bind.bind("<MouseWheel>", on_mouse_wheel)
        frame_to_bind.bind("<Button-4>", on_mouse_wheel)
        frame_to_bind.bind("<Button-5>", on_mouse_wheel)
        # Propagar el binding a todos los widgets hijos
        for child in frame_to_bind.winfo_children():
            if isinstance(child, (ctk.CTkFrame, ctk.CTkLabel, ctk.CTkEntry, ctk.CTkButton)):
                child.bind("<MouseWheel>", on_mouse_wheel)
                child.bind("<Button-4>", on_mouse_wheel)
                child.bind("<Button-5>", on_mouse_wheel)


    def _create_navigation_frame(self):
        frame = ctk.CTkFrame(self, width=150, corner_radius=0)
        frame.grid_rowconfigure(10, weight=1)

        header = ctk.CTkLabel(frame, text="Observación", font=ctk.CTkFont(size=18, weight="bold"))
        header.grid(row=0, column=0, padx=20, pady=20)

        self.nav_buttons = {}
        horas_z = ["06Z", "09Z", "12Z", "15Z", "18Z", "21Z", "00Z", "03Z"]
        for i, hora in enumerate(horas_z):
            button = ctk.CTkButton(frame, text=hora, corner_radius=0, height=40,
                                   fg_color="transparent", text_color=("gray10", "gray90"),
                                   hover_color=NAV_BUTTON_HOVER_COLOR, anchor="w")
            button.grid(row=i + 1, column=0, sticky="ew", padx=10)
            self.nav_buttons[hora] = button

        self.save_button = ctk.CTkButton(frame, text="Guardar JSON")
        self.save_button.grid(row=9, column=0, padx=10, pady=10, sticky="ew")

        return frame

    # --- El resto de tus funciones de creación de tablas no cambia ---
    # (Pega aquí tus funciones create_meteorological_table, create_station_calculations_table, etc.)
    def create_meteorological_table(self):
        parent = self.meteo_table_frame; total_cols = 7
        ctk.CTkLabel(parent, text="Observador", font=ctk.CTkFont(weight="bold", size=14), fg_color=HEADER_COLOR_PRIMARY, text_color="white", corner_radius=8).grid(row=0, column=0, columnspan=2, padx=3, pady=5, sticky="nsew")
        entry_obs = ctk.CTkEntry(parent, placeholder_text="Nombre del Observador...", border_width=1, corner_radius=6); entry_obs.grid(row=0, column=2, columnspan=5, padx=3, pady=5, sticky="nsew"); self.entries["nombre_observador"] = entry_obs
        header_texts = {1: ["MiMi MjMj", "YYGG Iw", "IIiii", "Fecha"], 3: ["Ir iX H VV", "N dd ff", "1sn T T T", "2sn Td Td Td", "4 P P P P", "5 a P P P", "7 ww W1 W2"], 5: ["8Nh CL CM CH", "333", "0CS DL DM DH", "1sn Tx Tx Tx", "2sn Tn Tn Tn", "3E j j j", "5 EEEjE"], 7: ["5n Fn Fn Fn", "56DL DM DH", "58/59 P24P24P24", "6 RRR tr", "7R24R24R24R24", "8NsChs hs", "8NsChs hs"], 9: ["8NsChs hs", "8NsChs hs", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp"], 11: ["9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp"], 13: ["9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp"], 15: ["9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp"]}
        placeholder_texts = {2: ["AAXX", "", "78", "DD/MM/AAAA HH:MM"], 4: ["", "", "10", "20", "4", "5", "7"], 6: ["8", "333", "0", "10", "20", "3///", ""], 8: ["", "56", "5", "6", "7", "8", "8"], 10: ["8", "8", "9", "9", "9", "9", "9"], 12: ["9", "9", "9", "9", "9", "9", "9"], 14: ["9", "9", "9", "9", "9", "9", "9"], 16: ["9", "9", "9", "9", "9", "9", "9"]}
        for r in range(16):
            grid_row = r + 1; is_header_row = (r % 2 == 0); headers = header_texts.get(grid_row, []); placeholders = placeholder_texts.get(grid_row, []); c_counter = 0
            for c in range(total_cols):
                if c_counter >= total_cols: break
                colspan = 1
                if grid_row == 1 and c == 3: colspan = 4
                if is_header_row:
                    try: text = headers[c]
                    except IndexError: continue
                    widget = ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(weight="bold"), fg_color=TABLE_HEADER_COLOR, text_color="white", corner_radius=6)
                else:
                    try: placeholder = placeholders[c]
                    except IndexError: continue
                    widget = ctk.CTkEntry(parent, placeholder_text=placeholder, border_width=1, corner_radius=6); key = f"meteo_{grid_row}_{c}"; self.entries[key] = widget
                widget.grid(row=grid_row, column=c_counter, columnspan=colspan, padx=3, pady=3, sticky="nsew"); c_counter += colspan
        for i in range(total_cols): parent.grid_columnconfigure(i, weight=1)
    def create_station_calculations_table(self):
        parent = self.calc_table_frame
        main_headers = ["Calculos de Estación", "Presión de la Estación", "P 3 Horas", "P 24 Horas", "Máx. / Min.", "Máx. / Min. (24 H)"]
        for i, text in enumerate(main_headers):
            col = i if i == 0 else i + 1; span = 2 if i == 0 else 1
            ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(weight="bold", size=14), fg_color=HEADER_COLOR_PRIMARY, text_color="white", corner_radius=8).grid(row=0, column=col, columnspan=span, sticky="nsew", padx=1, pady=5)
        table_structure = [("Ts.", 1, 0, 3, None, None), ("Pr.", 1, 1, 3, None, None), (None, 4, 0, 1, "°C", "ts"), (None, 4, 1, 1, "auto", "punto_rocio"), ("Th.", 5, 0, 3, None, None), ("Tv.", 5, 1, 3, None, None), (None, 8, 0, 1, "°C", "th"), (None, 8, 1, 1, "auto", "tension_vapor"), ("Dif.", 9, 0, 1, None, None), ("Hr.", 9, 1, 1, None, None), (None, 10, 0, 1, "auto", "diferencia"), (None, 10, 1, 1, "auto", "humedad_relativa"), ("Let. Barom.", 1, 2, 1, None, None), (None, 2, 2, 1, "Lectura...", "let_barom"), ("Correc. Temp.", 3, 2, 1, None, None), (None, 4, 2, 1, "0.0", "correc_temp"), ("Pres. Est.", 5, 2, 1, None, None), (None, 6, 2, 1, "1.6", "pres_est"), ("Correc. Alt.", 7, 2, 1, None, None), (None, 8, 2, 1, "Corrección...", "correc_alt"), ("Pres. NMM", 9, 2, 1, None, None), (None, 10, 2, 1, "1.6", "pres_nmm"), ("P 3", 1, 3, 3, None, None), (None, 4, 3, 1, "0.0", "p3"), ("Let..", 5, 3, 3, None, None), (None, 8, 3, 1, "0.0", "p3_let"), ("Dif.", 9, 3, 1, None, None), (None, 10, 3, 1, "0.0", "p3_dif"), ("P 24", 1, 4, 3, None, None), (None, 4, 4, 1, "Lectura...", "p24"), ("Let..", 5, 4, 3, None, None), (None, 8, 4, 1, "0.0", "p24_let"), ("Dif.", 9, 4, 1, None, None), (None, 10, 4, 1, "0.0", "p24_dif"), ("T Máx.", 1, 5, 3, None, None), (None, 4, 5, 1, "°C", "t_max"), ("T Mín.", 5, 5, 3, None, None), (None, 8, 5, 1, "°C", "t_min"), ("LL", 9, 5, 1, None, None), (None, 10, 5, 1, "mm", "ll"), ("T Máx.", 1, 6, 3, None, None), (None, 4, 6, 1, "°C", "t_max_24h"), ("T Mín.", 5, 6, 3, None, None), (None, 8, 6, 1, "°C", "t_min_24h"), ("LL", 9, 6, 1, None, None), (None, 10, 6, 1, "mm", "ll_24h")]
        for config in table_structure:
            text, row, col, r_span, placeholder, key = config
            if text is not None: ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(weight="bold"), fg_color=TABLE_HEADER_COLOR).grid(row=row, column=col, rowspan=r_span, sticky="nsew", padx=1, pady=1)
            else:
                if placeholder == "auto": widget = ctk.CTkEntry(parent, border_width=1, state="readonly"); self.results[key] = widget
                else: widget = ctk.CTkEntry(parent, border_width=1, placeholder_text=placeholder); self.entries[key] = widget
                widget.grid(row=row, column=col, rowspan=r_span, sticky="nsew", padx=1, pady=1)
        for i in range(7): parent.grid_columnconfigure(i, weight=1)
        for i in range(11): parent.grid_rowconfigure(i, weight=1)

    def get_all_values(self):
        return {key: widget.get() for key, widget in self.entries.items()}
    def set_all_values(self, data: dict):
        for key, widget in self.entries.items():
            value_to_set = data.get(key, ""); widget.delete(0, "end"); widget.insert(0, str(value_to_set))
    def bind_auto_calculate(self, command):
        self.after(100, lambda: self._bind_calculation_entries(command))
    def _bind_calculation_entries(self, command):
        if "ts" in self.entries: self.entries["ts"].bind("<KeyRelease>", command)
        if "th" in self.entries: self.entries["th"].bind("<KeyRelease>", command)
    def bind_nav_buttons(self, callback):
        for hora, button in self.nav_buttons.items(): button.configure(command=lambda h=hora: callback(h))
    def bind_save_button(self, callback):
        self.save_button.configure(command=callback)
        
    def update_active_button(self, active_hora: str):
        # --- CAMBIO 2a: Usar el color del tema del botón ---
        # Obtenemos el color de acento del tema actual de customtkinter
        selected_color = ctk.ThemeManager.theme["CTkButton"]["fg_color"]
        
        for hora, button in self.nav_buttons.items():
            if hora == active_hora:
                button.configure(fg_color=selected_color)
            else:
                button.configure(fg_color="transparent")

    def get_input_values(self):
        seco = self.entries.get("ts").get() if "ts" in self.entries else ""
        humedo = self.entries.get("th").get() if "th" in self.entries else ""
        return {"seco": seco, "humedo": humedo}
    def display_results(self, results: dict):
        def update_entry(widget_key, value, format_str="{:.2f}"):
            widget = self.results.get(widget_key)
            if widget:
                widget.configure(state="normal")
                widget.delete(0, "end")
                if isinstance(value, (int, float)): widget.insert(0, format_str.format(value))
                elif value is not None: widget.insert(0, str(value))
                widget.configure(state="readonly")
        update_entry("tension_vapor", results.get("tension_vapor"), format_str="{:.1f}")
        update_entry("humedad_relativa", results.get("humedad_relativa"), format_str="{:.0f}")
        update_entry("punto_rocio", results.get("punto_rocio"), format_str="{:.1f}")
        update_entry("diferencia", results.get("diferencia"), format_str="{:.1f}")
    def display_error(self, message):
        self.results["error_label"].configure(text=message)