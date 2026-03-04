import tkinter as tk
import tools.cbuttons as cbuttons

class newPopup:
    def __init__(self, root, name="New Window - AHControl", geometry="400x300", ui=None):
        self.root = root
        self.name = name
        self.win = tk.Toplevel(self.root)
        self.win.title(self.name)
        self.win.geometry(geometry)
        self.ui = ui # a list, perhaps, of ui elements one by one. This is for a generic popup, i don't think it should be used for something advanced.
        self._create_ui()
    
    def _create_ui(self):
        if self.ui:
            for element in self.ui:
                element.pack()
