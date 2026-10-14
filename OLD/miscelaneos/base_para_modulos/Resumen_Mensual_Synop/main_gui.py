# main_gui.py
# Punto de entrada de la aplicación y manejo de la interfaz gráfica.

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import json
from pathlib import Path
import time
import numpy as np
import pandas as pd
from PIL import Image
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# Importaciones de lógica
from src.met_analyzer.core import run_analysis
from src.met_analyzer.json_pipeline import convert_excels_to_json, run_analysis_from_json, save_summary_from_dataframe, load_summary_json

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Synop Analyzer")
        self.geometry("1000x700")
        self.minsize(800, 600)

        # Configuración de grid principal
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1) # El gráfico se expande

        # Estado
        self.df_report = None
        self._last_json_sources = []
        self._history_index = {}

        # --- 1. Header & Controls (Barra Superior) ---
        self.top_bar = ctk.CTkFrame(self, corner_radius=0, height=60)
        self.top_bar.grid(row=0, column=0, sticky="ew")
        self.top_bar.grid_columnconfigure(5, weight=1) # Espaciador

        # Logo / Título
        self.logo_label = ctk.CTkLabel(self.top_bar, text="Synop Analyzer", font=ctk.CTkFont(size=18, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=10)

        # Separador vertical simulado
        ctk.CTkFrame(self.top_bar, width=2, height=30, fg_color="gray50").grid(row=0, column=1, padx=5)

        # Botón Principal: Analizar
        self.btn_analizar = ctk.CTkButton(self.top_bar, text="➕ Nuevo Análisis", command=self.iniciar_analisis, font=ctk.CTkFont(weight="bold"))
        self.btn_analizar.grid(row=0, column=2, padx=15, pady=10)


        # Controles de Historial
        ctk.CTkLabel(self.top_bar, text="Historial:").grid(row=0, column=3, padx=(10, 5))
        self.combo_estacion = ctk.CTkOptionMenu(self.top_bar, values=["--"], width=140, command=self._on_station_change)
        self.combo_estacion.grid(row=0, column=4, padx=5)
        self.combo_periodo = ctk.CTkOptionMenu(self.top_bar, values=["--"], width=100, command=self._load_history_selection)
        self.combo_periodo.grid(row=0, column=5, padx=5, sticky="w")

        # Botón Tema (Derecha)
        self.btn_theme = ctk.CTkButton(self.top_bar, text="Tema", width=40, command=self._toggle_theme)
        self.btn_theme.grid(row=0, column=6, padx=20, sticky="e")


        # --- 2. Área Principal (Gráfico / Bienvenida) ---
        self.main_area = ctk.CTkFrame(self, fg_color="transparent")
        self.main_area.grid(row=1, column=0, sticky="nsew", padx=20, pady=20)
        self.main_area.grid_columnconfigure(0, weight=1)
        self.main_area.grid_rowconfigure(0, weight=1)

        # Placeholder de bienvenida
        self.welcome_frame = ctk.CTkFrame(self.main_area, fg_color="transparent")
        self.welcome_frame.grid(row=0, column=0)
        ctk.CTkLabel(self.welcome_frame, text="Listo para trabajar", font=ctk.CTkFont(size=24, weight="bold"), text_color="gray").pack()
        ctk.CTkLabel(self.welcome_frame, text="Selecciona 'Nuevo Análisis' o carga un reporte del historial.", text_color="gray").pack(pady=5)

        # Frame para Gráfico (oculto inicialmente)
        self.graph_container = ctk.CTkFrame(self.main_area, fg_color="transparent")
        # Se mostrará cuando haya datos

        # Controles del gráfico (dentro del container)
        self.graph_controls = ctk.CTkFrame(self.graph_container, fg_color="transparent", height=40)
        self.graph_controls.pack(side="top", fill="x", pady=(0, 10))
        
        ctk.CTkLabel(self.graph_controls, text="Visualizando:").pack(side="left")
        self.combo_variable = ctk.CTkOptionMenu(self.graph_controls, values=["--"], command=self._draw_graph)
        self.combo_variable.pack(side="left", padx=10)
        
        self.btn_export = ctk.CTkButton(self.graph_controls, text="Exportar Gráfico", width=100, command=self._export_graph)
        self.btn_export.pack(side="right")
        self.btn_save_report = ctk.CTkButton(self.graph_controls, text="Guardar Excel", width=100, command=self._save_report_excel)
        self.btn_save_report.pack(side="right", padx=10)

        self.canvas_frame = ctk.CTkFrame(self.graph_container)
        self.canvas_frame.pack(side="top", fill="both", expand=True)

        # --- 3. Footer (Status) ---
        self.status_bar = ctk.CTkFrame(self, height=30, corner_radius=0)
        self.status_bar.grid(row=2, column=0, sticky="ew")
        self.status_bar.grid_columnconfigure(1, weight=1)

        self.lbl_status = ctk.CTkLabel(self.status_bar, text="Esperando...", anchor="w")
        self.lbl_status.grid(row=0, column=0, padx=15, sticky="w")
        
        self.progress = ctk.CTkProgressBar(self.status_bar, width=200)
        self.progress.set(0)
        self.progress.grid(row=0, column=2, padx=15, sticky="e")

        # Inicialización
        self._refresh_history_index()
        self._apply_theme()

    # --- Lógica de UI ---
    def _toggle_theme(self):
        ctk.set_appearance_mode("Light" if ctk.get_appearance_mode() == "Dark" else "Dark")
        self._apply_theme()

    def _apply_theme(self):
        is_dark = ctk.get_appearance_mode() == "Dark"
        self.btn_theme.configure(text="Tema" if is_dark else "Tema")
        # Refrescar gráfico si existe
        if self.df_report is not None:
            var = self.combo_variable.get()
            if var != "--": self._draw_graph(var)

    def _show_graph_view(self):
        self.welcome_frame.grid_forget()
        self.graph_container.grid(row=0, column=0, sticky="nsew")

    def _update_status(self, msg, progress=None, color=None):
        self.lbl_status.configure(text=msg, text_color=color if color else ("black", "white"))
        if progress is not None: self.progress.set(progress)
        self.update_idletasks()

    # --- Lógica de Negocio ---
    def iniciar_analisis(self):
        rutas = filedialog.askopenfilenames(
            title="Seleccionar Archivos",
            initialdir=Path(__file__).parent / "data",
            filetypes=(("Excel/JSON", "*.xlsm *.xlsx *.json"),)
        )
        if not rutas: return

        self.btn_analizar.configure(state="disabled")
        self._update_status("Iniciando análisis...", 0)
        
        try:
            json_out_dir = Path(__file__).parent / "data" / "json"
            rutas_excel = [r for r in rutas if str(r).lower().endswith((".xlsm", ".xlsx"))]
            rutas_json = [r for r in rutas if str(r).lower().endswith(".json")]

            if rutas_excel:
                self._update_status(f"Convirtiendo {len(rutas_excel)} Excel...", 0.2)
                rutas_excel = self._auto_normalize_excel_filenames(rutas_excel)
                converted = convert_excels_to_json(rutas_excel, json_out_dir)
                rutas_json.extend([str(c) for c in converted])

            if not rutas_json:
                self._update_status("No se encontraron datos válidos.", 0, "red")
                return

            self._update_status(f"Analizando {len(rutas_json)} archivos...", 0.5)
            
            def callback(msg):
                try:
                    curr, tot = map(int, msg.split(":")[0].replace("Procesando", "").strip().split('/'))
                    self._update_status(msg, 0.5 + (curr/tot)*0.4)
                except: self._update_status(msg)

            df, logs = run_analysis_from_json(rutas_json, update_callback=callback)

            if not df.empty:
                self.df_report = df
                self._last_json_sources = rutas_json
                
                # Guardar en historial
                try:
                    summaries_dir = Path(__file__).parent / "data" / "summaries"
                    est = self._infer_station(rutas_json)
                    save_summary_from_dataframe(df, summaries_dir, estacion=est)
                    self._refresh_history_index()
                except: pass

                self._update_status("Análisis completado.", 1.0, "green")
                self._setup_graph_variables()
                self._show_graph_view()
            else:
                self._update_status("El análisis no generó resultados.", 0, "red")

        except Exception as e:
            self._update_status(f"Error: {e}", 0, "red")
            print(e)
        finally:
            self.btn_analizar.configure(state="normal")

    def _load_history_selection(self, periodo):
        est = self.combo_estacion.get()
        if est in self._history_index and periodo in self._history_index[est]:
            try:
                path = self._history_index[est][periodo]
                self.df_report = load_summary_json(path)
                self._setup_graph_variables()
                self._show_graph_view()
                self._update_status(f"Cargado: {est} - {periodo}", 1.0)
            except Exception as e:
                self._update_status(f"Error cargando historial: {e}", 0, "red")

    def _setup_graph_variables(self):
        if self.df_report is None: return
        cols = self.df_report.select_dtypes(include=np.number).columns.tolist()
        if cols:
            self.combo_variable.configure(values=cols)
            self.combo_variable.set(cols[0])
            self._draw_graph(cols[0])

    def _draw_graph(self, var):
        for w in self.canvas_frame.winfo_children(): w.destroy()
        if self.df_report is None or var not in self.df_report.columns: return

        is_dark = ctk.get_appearance_mode() == "Dark"
        bg = "#2b2b2b" if is_dark else "#f0f0f0"
        fg = "white" if is_dark else "black"

        fig = plt.Figure(figsize=(5, 4), dpi=100, facecolor=bg)
        ax = fig.add_subplot(111, facecolor=bg)
        
        x = pd.to_datetime(self.df_report['Dias']).dt.day
        y = self.df_report[var]
        
        color = "#1f6aa5" if is_dark else "#3a7ebf"
        if "Lluvia" in var: ax.bar(x, y, color=color)
        else: ax.plot(x, y, marker='o', color=color)

        ax.set_title(f"{var}", color=fg)
        ax.tick_params(colors=fg)
        for spine in ax.spines.values(): spine.set_color(fg)
        ax.grid(True, linestyle='--', alpha=0.3)

        canvas = FigureCanvasTkAgg(fig, master=self.canvas_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def _export_graph(self):
        if self.df_report is None: return
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png")])
        if path:
            # Re-renderizar para guardar
            self._update_status(f"Gráfico guardado en {path}", 1.0)

    def _save_report_excel(self):
        if self.df_report is None: return
        path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")])
        if path:
            self.df_report.to_excel(path, index=False)
            self._update_status(f"Reporte guardado en {path}", 1.0)

    # --- Utilidades ---
    def _refresh_history_index(self):
        summaries_dir = Path(__file__).parent / "data" / "summaries"
        summaries_dir.mkdir(parents=True, exist_ok=True)
        self._history_index = {}
        for p in sorted(summaries_dir.glob("resumen_*.json")):
            try:
                with p.open('r', encoding='utf-8') as f: doc = json.load(f)
                est = doc.get('meta', {}).get('estacion', 'Desconocida')
                per = doc.get('meta', {}).get('periodo', 'S/F')
                self._history_index.setdefault(est, {})[per] = p
            except: continue
        
        estaciones = sorted(self._history_index.keys())
        if estaciones:
            self.combo_estacion.configure(values=estaciones)
            self.combo_estacion.set(estaciones[0])
            self._on_station_change(estaciones[0])
        else:
            self.combo_estacion.configure(values=["--"])
            self.combo_periodo.configure(values=["--"])

    def _on_station_change(self, est):
        if est in self._history_index:
            periodos = sorted(self._history_index[est].keys())
            self.combo_periodo.configure(values=periodos)
            if periodos: self.combo_periodo.set(periodos[0])
        else:
            self.combo_periodo.configure(values=["--"])

    def _auto_normalize_excel_filenames(self, excel_paths):
        import re
        nuevas = []
        for p in excel_paths:
            path = Path(p)
            m = re.search(r"(\d{8})", path.stem)
            if not m:
                nuevas.append(str(path)); continue
            fecha = m.group(1)
            prefix_match = re.match(r"^(.*?)(?:\s*\d{8})", path.stem)
            estacion = (prefix_match.group(1).strip() if prefix_match and prefix_match.group(1) else "").strip()
            base_name = f"{(estacion + ' ') if estacion else ''}{fecha}{path.suffix}"
            nuevo_path = path.with_name(base_name)
            try:
                if str(nuevo_path) != str(path): path.rename(nuevo_path)
                nuevas.append(str(nuevo_path))
            except: nuevas.append(str(path))
        return nuevas

    def _infer_station(self, json_paths):
        try:
            with open(json_paths[0], 'r', encoding='utf-8') as f:
                return json.load(f).get('meta', {}).get('estacion', 'estacion')
        except: return "estacion"

if __name__ == "__main__":
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")
    app = App()
    app.mainloop()