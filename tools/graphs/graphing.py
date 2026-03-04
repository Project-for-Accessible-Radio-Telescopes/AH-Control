import matplotlib.pyplot as plt
import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from tools.popup import graphPopup

def plot_basic_graph(root, x, y, title="Graph", xlabel="X-axis", ylabel="Y-axis"):
    fig, ax = plt.subplots()
    fig.set_size_inches(5.6, 3.0)
    ax.plot(x, y)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)

    popup = graphPopup(root, name=title, geometry="600x420")
    footer = tk.Frame(popup.win)
    footer.pack(side="bottom", fill="x", padx=8, pady=6)

    tk.Label(footer, text="Graph ready", anchor="w").pack(side="left")

    canvas = FigureCanvasTkAgg(fig, master=popup.win)
    canvas.draw()
    canvas.get_tk_widget().pack(side="top", fill="both", expand=True, padx=8, pady=(8, 0))

    def close_popup():
        plt.close(fig)
        popup.win.destroy()

    tk.Button(footer, text="OK", command=close_popup).pack(side="right")
    popup.win.protocol("WM_DELETE_WINDOW", close_popup)


def plot_graph(root, x, y, title="Graph", xlabel="X-axis", ylabel="Y-axis"):
    plot_basic_graph(root, x, y, title=title, xlabel=xlabel, ylabel=ylabel)