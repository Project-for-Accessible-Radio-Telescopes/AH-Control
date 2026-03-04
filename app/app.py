import tkinter as tk
import getpass
import os
import platform
import re
import sys
from datetime import datetime
import json

from ui.main_window import MainWindow

def _safe_log(window, text):
    if window is not None and hasattr(window, "_append_log"):
        try:
            window._append_log(text)
            return
        except Exception:
            pass
    print(text)


def _extract_app_version(root):
    try:
        with open("data/settings.json", "r", encoding="utf-8") as settings_file:
            settings = json.load(settings_file)
            version = settings.get("version", "unknown")
            return version
    except Exception:
        return "unknown"


def run_app():
    root = None
    main_window = None

    try:
        root = tk.Tk()
        main_window = MainWindow(root)

        login_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        app_version = _extract_app_version(root)

        _safe_log(main_window, "Application started successfully")
        _safe_log(main_window, f"Login time: {login_time}")
        _safe_log(main_window, f"AH version: {app_version}")
        _safe_log(main_window, f"User: {getpass.getuser()}")
        _safe_log(main_window, f"OS: {platform.platform()}")
        _safe_log(main_window, f"Python: {sys.version.split()[0]}")
        _safe_log(main_window, f"Working directory: {os.getcwd()}")
        _safe_log(main_window, f"Welcome to the AH Control v{app_version}!")

        root.mainloop()
    except Exception as error:
        _safe_log(main_window, f"Application error: {error}")
        print(f"Application error: {error}", file=sys.stderr)
        if root is not None:
            try:
                root.destroy()
            except Exception:
                pass
