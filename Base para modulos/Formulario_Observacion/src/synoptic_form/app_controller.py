# src/synoptic_form/app_controller.py
# Controlador con gestión de estado explícita para observaciones independientes.

import json
from tkinter import filedialog
from pathlib import Path
from datetime import datetime

# Importaciones relativas a los otros módulos del paquete
from .view import SynopticFormView
from . import calculations as calc

class AppController:
    def __init__(self):
        self.view = SynopticFormView()
        
        # --- MODELO DE DATOS: Almacén para las 8 observaciones ---
        self.horas_z = ["06Z", "09Z", "12Z", "15Z", "18Z", "21Z", "00Z", "03Z"]
        self.observations_data = {hora: {} for hora in self.horas_z}
        self.current_observation_time = "06Z"

        # --- CONECTAR EVENTOS DE LA VISTA A LAS FUNCIONES DEL CONTROLADOR ---
        self.view.bind_auto_calculate(self._on_input_change)
        self.view.bind_nav_buttons(self.switch_observation_time)
        self.view.bind_save_button(self.save_to_json)

        # --- ESTADO INICIAL DE LA UI ---
        self.view.update_active_button(self.current_observation_time)

    def _on_input_change(self, *args):
        """Se activa con cada tecleo. Guarda el estado y luego calcula."""
        self._save_current_view_to_model()
        self.perform_calculations()

    def _save_current_view_to_model(self):
        """Obtiene todos los datos de la vista y los guarda en el modelo de datos."""
        current_data = self.view.get_all_values()
        self.observations_data[self.current_observation_time] = current_data

    def switch_observation_time(self, new_time: str):
        """Guarda los datos actuales, cambia de hora y carga los nuevos datos."""
        if new_time == self.current_observation_time:
            return  # No hacer nada si se hace clic en el botón ya activo

        # 1. Guardar el estado de la vista actual en el modelo (última vez)
        self._save_current_view_to_model()
        
        # 2. Actualizar la hora activa
        self.current_observation_time = new_time
        
        # 3. Cargar los datos de la nueva hora desde el modelo a la vista
        new_data = self.observations_data.get(new_time, {})
        self.view.set_all_values(new_data)
        
        # 4. Actualizar la UI
        self.view.update_active_button(self.current_observation_time)
        self.perform_calculations()  # Recalcular con los datos recién cargados

    def perform_calculations(self, *args):
        """Realiza los cálculos y actualiza los resultados en la vista."""
        self.view.display_error("")
        
        # Obtener los datos necesarios para el cálculo directamente de la vista
        inputs = self.view.get_input_values()
        seco_str = inputs.get("seco", "")
        humedo_str = inputs.get("humedo", "")
        
        if not seco_str or not humedo_str:
            self.view.display_results({})
            return
            
        try:
            temp_seco = float(seco_str)
            temp_humedo = float(humedo_str)
        except (ValueError, TypeError):
            self.view.display_error("Error: Ingrese valores numéricos.")
            self.view.display_results({})
            return

        if temp_humedo > temp_seco:
            self.view.display_error("Error: Th no puede ser mayor que Ts.")
            self.view.display_results({}) 
            return
        
        # Lógica de cálculo original
        tension_vapor = calc.calcular_tension_vapor(temp_seco, temp_humedo)
        
        humedad_relativa_final = ""
        punto_rocio_final = ""

        if isinstance(tension_vapor, (int, float)):
            humedad_relativa_final = calc.calcular_humedad_relativa(tension_vapor, temp_seco)
            if isinstance(humedad_relativa_final, (int, float)):
                punto_rocio_final = calc.calcular_punto_rocio(temp_seco, humedad_relativa_final)

        diferencia_temp = temp_seco - temp_humedo
        
        results_to_display = {
            "tension_vapor": tension_vapor,
            "humedad_relativa": humedad_relativa_final,
            "punto_rocio": punto_rocio_final,
            "diferencia": diferencia_temp
        }
        
        self.view.display_results(results_to_display)
        
    def save_to_json(self):
        """Guarda el diccionario completo de observaciones en un archivo JSON."""
        # Asegurarse de que los últimos datos de la vista se guardan antes de abrir el diálogo
        self._save_current_view_to_model()
        
        today_str = datetime.now().strftime("%Y%m%d")
        initial_filename = f"{today_str}_observacion.json"
        
        # Sugerir guardar en la carpeta 'data_output'
        save_path = Path(__file__).parent.parent.parent / "data_output"
        save_path.mkdir(exist_ok=True)  # Crear la carpeta si no existe
        
        filepath = filedialog.asksaveasfilename(
            title="Guardar archivo de observación JSON",
            initialdir=save_path,
            initialfile=initial_filename,
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")]
        )
        if not filepath:
            self.view.display_error("Guardado cancelado.")
            return

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self.observations_data, f, indent=4, ensure_ascii=False)
            self.view.display_error(f"Datos guardados.")
        except Exception as e:
            self.view.display_error(f"Error al guardar: {e}")

    def run(self):
        self.view.mainloop()