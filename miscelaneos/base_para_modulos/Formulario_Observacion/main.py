# main.py
# Punto de entrada principal para lanzar la aplicación.

from src.synoptic_form.app_controller import AppController

if __name__ == "__main__":
    app = AppController()
    app.run()