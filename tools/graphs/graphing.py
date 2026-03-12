import matplotlib.pyplot as plt
import tkinter as tk
from tkinter import ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from tools.popup import graphPopup
import numpy as np

def plot_basic_graph(root, x, y, title="Graph", xlabel="X-axis", ylabel="Y-axis"):
    fig, ax = plt.subplots()
    fig.set_size_inches(5.6, 3.0)
    ax.plot(x, y)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)

    popup = graphPopup(root, name=title, geometry="600x420")
    footer = ttk.Frame(popup.win)
    footer.pack(side="bottom", fill="x", padx=8, pady=6)

    ttk.Label(footer, text="Status: graph ready", anchor="w").pack(side="left")

    toolbar_frame = ttk.Frame(popup.win)
    toolbar_frame.pack(side="bottom", fill="x", padx=8, pady=(0, 4))

    canvas = FigureCanvasTkAgg(fig, master=popup.win)
    canvas.draw()
    canvas.get_tk_widget().pack(side="top", fill="both", expand=True, padx=8, pady=(8, 0))

    toolbar = NavigationToolbar2Tk(canvas, toolbar_frame, pack_toolbar=False)
    toolbar.update()
    toolbar.pack(side="left", fill="x")

    def close_popup():
        plt.close(fig)
        popup.win.destroy()

    ttk.Button(footer, text="Close", command=close_popup).pack(side="right")
    popup.win.protocol("WM_DELETE_WINDOW", close_popup)

def plot_scatter_graph(root, x, y, title="Scatter Graph", xlabel="X-axis", ylabel="Y-axis", lobf=False):
    fig, ax = plt.subplots()
    fig.set_size_inches(5.6, 3.0)
    ax.scatter(x, y)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)

    popup = graphPopup(root, name=title, geometry="600x420")
    footer = ttk.Frame(popup.win)
    footer.pack(side="bottom", fill="x", padx=8, pady=6)

    ttk.Label(footer, text="Status: graph ready", anchor="w").pack(side="left")

    toolbar_frame = ttk.Frame(popup.win)
    toolbar_frame.pack(side="bottom", fill="x", padx=8, pady=(0, 4))

    canvas = FigureCanvasTkAgg(fig, master=popup.win)
    canvas.draw()
    canvas.get_tk_widget().pack(side="top", fill="both", expand=True, padx=8, pady=(8, 0))

    toolbar = NavigationToolbar2Tk(canvas, toolbar_frame, pack_toolbar=False)
    toolbar.update()
    toolbar.pack(side="left", fill="x")

    if lobf:
        m, b = np.polyfit(x, y, 1)
        ax.plot(x, m * np.array(x) + b, color="red", label="Line of Best Fit")
        ax.legend()
        canvas.draw()

    def close_popup():
        plt.close(fig)
        popup.win.destroy()

    ttk.Button(footer, text="Close", command=close_popup).pack(side="right")
    popup.win.protocol("WM_DELETE_WINDOW", close_popup)

def plot_bar_graph(root, x, y, title="Bar Graph", xlabel="X-axis", ylabel="Y-axis"):
    fig, ax = plt.subplots()
    fig.set_size_inches(5.6, 3.0)
    ax.bar(x, y)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)

    popup = graphPopup(root, name=title, geometry="600x420")
    footer = ttk.Frame(popup.win)
    footer.pack(side="bottom", fill="x", padx=8, pady=6)

    ttk.Label(footer, text="Status: graph ready", anchor="w").pack(side="left")

    toolbar_frame = ttk.Frame(popup.win)
    toolbar_frame.pack(side="bottom", fill="x", padx=8, pady=(0, 4))

    canvas = FigureCanvasTkAgg(fig, master=popup.win)
    canvas.draw()
    canvas.get_tk_widget().pack(side="top", fill="both", expand=True, padx=8, pady=(8, 0))

    toolbar = NavigationToolbar2Tk(canvas, toolbar_frame, pack_toolbar=False)
    toolbar.update()
    toolbar.pack(side="left", fill="x")

    def close_popup():
        plt.close(fig)
        popup.win.destroy()

    ttk.Button(footer, text="Close", command=close_popup).pack(side="right")
    popup.win.protocol("WM_DELETE_WINDOW", close_popup)

def plot_line_graph(root, x, y, title="Line Graph", xlabel="X-axis", ylabel="Y-axis"):
    plot_basic_graph(root, x, y, title=title, xlabel=xlabel, ylabel=ylabel)