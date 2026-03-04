import tkinter as tk


class CustomMenu:
    """Reusable popup menu manager using a Toplevel per menu.

    Usage:
        manager = CustomMenu(root)
        manager.show_menu(button, [("Label", callback), ...])
    """

    def __init__(self, root):
        self.root = root
        self.open_menu = None
        self.open_button = None

        # Global handlers
        self.root.bind_all("<Button-1>", self._global_click, add="+")
        self.root.bind_all("<Escape>", lambda e: self.close_menu(), add="+")

    def _create_menu_toplevel(self, items):
        top = tk.Toplevel(self.root)
        top.withdraw()
        top.overrideredirect(True)
        top.transient(self.root)
        top.attributes("-topmost", True)

        # Use `#cccccc` as the visible border color and `#eeeeee` as the menu background
        outer = tk.Frame(top, bd=0, bg="#cccccc")
        outer.pack(fill="both", expand=True)

        # Inner content holds the items and shows the `#eeeeee` background
        content = tk.Frame(outer, bd=0, bg="#eeeeee")
        content.pack(padx=1, pady=1, fill="both", expand=True)

        for text, cmd in items:
            b = tk.Label(
                content,
                text=text,
                anchor="w",
                bg="#eeeeee",
                fg="black",  # Add foreground color for text
                activebackground="#e0e0e0",
                activeforeground="#cccccc",
                font=("TkDefaultFont", 10),  # Use default font
                padx=2,
                pady=2,
                bd=1,  # Slight border width
                relief="solid",
            )
            b.pack(fill="x", padx=4, pady=2)

            # Bind click event
            b.bind("<Button-1>", lambda e, c=cmd: self._menu_action(c))

            # Simple hover: slightly darker gray on hover
            b.bind("<Enter>", lambda e, w=b: w.configure(bg="#e0e0e0"))
            b.bind("<Leave>", lambda e, w=b: w.configure(bg="#eeeeee"))

        return top

    def show_menu(self, button, items):
        self._clear_text_selection()

        # Toggle behavior: if same button clicked, close
        if self.open_button is button:
            self.close_menu()
            return

        self.close_menu()

        menu = self._create_menu_toplevel(items)
        x = button.winfo_rootx()
        y = button.winfo_rooty() + button.winfo_height()
        menu.geometry(f"+{x}+{y}")
        menu.deiconify()

        self.open_menu = menu
        self.open_button = button

    def close_menu(self):
        if self.open_menu:
            try:
                self.open_menu.destroy()
            except Exception:
                pass
        self.open_menu = None
        self.open_button = None

    def _menu_action(self, cmd):
        self._clear_text_selection()
        self.close_menu()
        try:
            cmd()
        except Exception:
            pass

    def _clear_text_selection(self):
        def clear_recursive(widget):
            if isinstance(widget, tk.Text):
                try:
                    widget.tag_remove("sel", "1.0", "end")
                except Exception:
                    pass

            for child in widget.winfo_children():
                clear_recursive(child)

        try:
            clear_recursive(self.root)
        except Exception:
            pass

    def _global_click(self, event):
        # If no menu open, nothing to do
        if not self.open_menu:
            return

        widget = event.widget

        # If click was on the button that opened the menu, ignore (button handler toggles)
        if widget is self.open_button:
            return

        # If click happened inside the open_menu toplevel, ignore
        try:
            clicked_toplevel = widget.winfo_toplevel()
        except Exception:
            clicked_toplevel = None

        if clicked_toplevel is self.open_menu:
            return

        # Otherwise close
        self.close_menu()
