# standard input for the application

import tkinter as tk

class stdInput:
    def __init__(self, root, prompt="Enter a value:", pos=[20, 10]):
        self.root = root
        self.value = None

        self.label = tk.Label(self.root, text=prompt)
        self.label.pack(padx=pos[0], pady=(pos[1], 0))

        self.input_box = tk.Entry(self.root)
        self.input_box.pack(padx=pos[0], pady=pos[1])
        self.input_box.focus_set()

    def get(self):
        self.value = self.input_box.get()
        return self.value