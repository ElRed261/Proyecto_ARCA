import customtkinter as ctk
import tkinter as tk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

print("Initializing CTk with Matplotlib...")
try:
    app = ctk.CTk()
    app.geometry("400x300")
    
    fig = plt.Figure(figsize=(5, 4), dpi=100)
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 2, 3])
    
    canvas = FigureCanvasTkAgg(fig, master=app)
    canvas.draw()
    canvas.get_tk_widget().pack()
    
    print("Canvas packed. Updating...")
    app.update()
    print("Update successful.")
    app.destroy()
    print("Destroyed.")
except Exception as e:
    print(f"Error: {e}")
