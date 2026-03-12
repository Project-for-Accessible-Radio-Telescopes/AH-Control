import tkinter as tk
from tkinter import ttk

class msgPopup:
    def __init__(self, title, message, msgtype="info", size=(400, 250)):
        self.win = tk.Toplevel()
        self.win.title(f"AH-Control | {title}")
        self.win.geometry(f"{size[0]}x{size[1]}")

        container = ttk.Frame(self.win, padding=12)
        container.pack(fill="both", expand=True)

        self.info_label = ttk.Label(container)

        if msgtype == "error":
            self.info_label.config(text="Error", foreground="#c92a2a")
        elif msgtype == "warning":
            self.info_label.config(text="Warning", foreground="#e67700")
        elif msgtype == "success":
            self.info_label.config(text="Success", foreground="#2b8a3e")
        else:
            self.info_label.config(text="Info", foreground="#1971c2")

        self.info_label.pack(anchor="w", pady=(0, 6))

        ttk.Label(container, text=message, wraplength=(size[0] - 36), justify="left").pack(anchor="w", pady=(0, 12))

        actions = ttk.Frame(container)
        actions.pack(fill="x")
        ttk.Button(actions, text="OK", command=self.win.destroy).pack(side="right")