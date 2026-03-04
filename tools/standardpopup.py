import tkinter as tk
from tkinter import ttk
# import images to be used too

class msgPopup:
    def __init__(self, title, message, msgtype="info", size=(400, 250)):
        self.win = tk.Toplevel()
        self.win.title(f"{title} {msgtype.capitalize()} - AH-Control")
        self.win.geometry(f"{size[0]}x{size[1]}")

        

        # self.error_icon = tk.PhotoImage(file="./assets/visual/error.svg")
        # self.info_icon = tk.PhotoImage(file="./assets/visual/info.svg")
        
        self.info_label = tk.Label(self.win)

        if msgtype == "error":
            self.info_label.config(text="Error: ", fg="red")
        elif msgtype == "warning":
            self.info_label.config(text="Warning: ", fg="yellow")
        elif msgtype == "success":
            self.info_label.config(text="Success: ", fg="green")
        elif msgtype == "info":
            self.info_label.config(text="Info: ", fg="#007acc")

        self.info_label.pack(pady=10)

        tk.Label(self.win, text=message, wraplength=(size[0]-30)).pack(pady=5)
        ttk.Button(self.win, text="OK", command=self.win.destroy).pack(pady=8)