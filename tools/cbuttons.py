import tkinter as tk
from tkinter import ttk


def make_button(parent, text, command=None, **overrides):
    """Create a top-menu button using ttk for cross-platform consistency.

    Returns a `ttk.Button` instance. Does NOT pack/place the button; caller should
    manage geometry.
    """
    button_options = {
        "style": overrides.pop("style", "TopMenu.TButton"),
    }
    btn = ttk.Button(parent, text=text, **button_options)
    if command is not None:
        btn.configure(command=command)
    return btn


class StyledButton(ttk.Button):
    """Optional subclass if callers prefer a class-based API."""

    def __init__(self, parent, text, command=None, **overrides):
        style_name = overrides.pop("style", "TopMenu.TButton")
        super().__init__(parent, text=text, style=style_name)
        if command is not None:
            self.configure(command=command)
