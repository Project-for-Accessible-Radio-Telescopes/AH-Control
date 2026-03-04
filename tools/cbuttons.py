import tkinter as tk


def make_button(parent, text, command=None, **overrides):
    """Create a plain rectangular button with the project's default style.

    Returns a `tk.Button` instance. Does NOT pack/place the button; caller should
    manage geometry.
    """
    style = dict(
        bg="#767676",
        bd=0,
        relief="flat",
        highlightthickness=0,
        activebackground="#e0e0e0",
        padx=8,
        pady=4,
    )
    style.update(overrides)

    btn = tk.Button(parent, text=text, **{k: v for k, v in style.items() if v is not None})
    if command:
        btn.configure(command=command)
    return btn


class StyledButton(tk.Button):
    """Optional subclass if callers prefer a class-based API."""

    def __init__(self, parent, text, command=None, **overrides):
        style = dict(
            bg="#eeeeee",
            bd=1,
            relief="solid",
            highlightthickness=0,
            activebackground="#e0e0e0",
            padx=8,
            pady=4,
        )
        style.update(overrides)
        super().__init__(parent, text=text, **{k: v for k, v in style.items() if v is not None})
        if command:
            self.configure(command=command)
