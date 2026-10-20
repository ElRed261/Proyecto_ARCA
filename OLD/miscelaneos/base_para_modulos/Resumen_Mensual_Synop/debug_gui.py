import customtkinter as ctk
import tkinter as tk

print("Initializing CTk...")
try:
    app = ctk.CTk()
    app.geometry("400x300")
    print("CTk Initialized.")
    
    label = ctk.CTkLabel(app, text="Hello World")
    label.pack()
    
    print("Starting mainloop...")
    # app.mainloop() # Don't block, just test init
    app.update()
    print("Update successful.")
    app.destroy()
    print("Destroyed.")
except Exception as e:
    print(f"Error: {e}")
