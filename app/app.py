import tkinter as tk
import getpass
import os
import platform
import re
import sys
from datetime import datetime

from ui.main_window import MainWindow
from logic.settings_manager import load_settings_file


def _app_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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
        settings = load_settings_file("data/settings.json")
        return str(settings.get("version", "unknown"))
    except Exception:
        return "unknown"


def run_app():
    root = None
    main_window = None

    try:
        # we normalise the working directory
        # so that relative paths work correctly.
        # this is optional for dev runs but necessary for releases.
        os.chdir(_app_base_dir())

        root = tk.Tk()
        main_window = MainWindow(root)

        icon_path = os.path.join("assets", "visual", "icon.png")
        try:
            icon = tk.PhotoImage(file=icon_path)
            root.iconphoto(False, icon)
        except Exception:
            _safe_log(main_window, f"Non-critical warning: Icon failed to load")

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
        try:
            _safe_log(main_window, f"Application error: {error}")
        except:
            print(f"Application error: {error}", file=sys.stderr)
        if root is not None:
            try:
                root.destroy()
            except Exception:
                pass
