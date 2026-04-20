import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from tkinter import filedialog
import json
import os
import threading
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from tools.graphs.graphing import plot_basic_graph
from ui.settings_window import SettingsWindow
from ui.advanced_signal_window import AdvancedSignalWindow
from ui.health_diagnostics_window import HealthDiagnosticsWindow
from ui.data_recording_window import DataRecordingWindow
from ui.lesson_wizard_window import LessonWizardWindow
from ui.comparison_window import ComparisonWindow
from ui.recording_browser_window import RecordingBrowserWindow
import webbrowser
from logic.file_ext import build_session_payload, write_ahf_file, read_ahf_file

import numpy as np
from logic.sdr_advanced import (
    analyze_recording_for_advanced_view,
    build_frequency_axis_mhz,
    extract_peak_metrics,
)
from logic.rtl_sdr_recording import (
    detect_rtl_sdr_devices,
    capture_rtl_sdr_samples,
    get_rtlsdr_class,
    get_rtlsdr_import_error,
)

from tools.cmenu import CustomMenu
from tools import cbuttons
from tools.spreadsheet import SpreadsheetWindow
from tools.popup import newPopup
from tools.standardpopup import msgPopup

from logic.local_info import obtain_local_info, compute_sidereal_time_and_hour_angle
from logic.settings_manager import load_settings_file, save_settings_file

class MainWindow:
    def __init__(self, root):
        self.root = root
        self.root.geometry("500x300")
        self._spreadsheet_windows = []
        self._recording_annotations = {}
        self._recent_recordings = []

        # Use CustomMenu manager for popup menus
        self.menu = CustomMenu(self.root)

        self.settings = load_settings_file("data/settings.json")

        self.root.title(f"AH-Control v{self.settings.get('version')}")

        self._create_menu_bar(theme=self.settings.get("theme", "light"))
        self._create_content(theme=self.settings.get("theme", "light"))
        self._apply_runtime_settings()
        self._bind_log_selection_guards()

    def _bind_log_selection_guards(self):
        if not hasattr(self, "log_text"):
            return

        # Block mouse/keyboard selection shortcuts in the log view.
        blocked_events = [
            "<Button-1>",
            "<B1-Motion>",
            "<Double-Button-1>",
            "<Triple-Button-1>",
            "<Shift-Button-1>",
            "<Control-a>",
            "<Command-a>",
            "<<SelectAll>>",
        ]
        for event_name in blocked_events:
            self.log_text.bind(event_name, lambda _event: "break")

        # Clear lingering selection when pointer/focus moves away from the log.
        self.log_text.bind("<ButtonRelease-1>", self._clear_log_selection, add="+")
        self.log_text.bind("<Leave>", self._clear_log_selection, add="+")
        self.log_text.bind("<FocusOut>", self._clear_log_selection, add="+")

    def _clear_log_selection(self, _event=None):
        if not hasattr(self, "log_text"):
            return
        try:
            self.log_text.tag_remove("sel", "1.0", "end")
        except Exception:
            return

    def _run_in_background(self, work_fn, on_success=None, on_error=None, on_finally=None):
        def runner():
            try:
                result = work_fn()
                if on_success is not None:
                    self.root.after(0, lambda value=result: on_success(value))
            except Exception as error:
                if on_error is not None:
                    self.root.after(0, lambda caught_error=error: on_error(caught_error))
            finally:
                if on_finally is not None:
                    self.root.after(0, on_finally)

        threading.Thread(target=runner, daemon=True).start()

    def _parse_float(self, raw_text, field_name):
        text = str(raw_text).strip()
        if not text:
            raise ValueError(f"{field_name} is required")
        try:
            return float(text)
        except ValueError as error:
            raise ValueError(f"{field_name} must be a valid number") from error

    def _validate_range(self, value, field_name, minimum=None, maximum=None):
        if minimum is not None and value < minimum:
            raise ValueError(f"{field_name} must be >= {minimum}")
        if maximum is not None and value > maximum:
            raise ValueError(f"{field_name} must be <= {maximum}")
        return value

    def _get_rtlsdr_class(self):
        return get_rtlsdr_class()

    def _show_rtlsdr_dependency_error(self):
        import_error = get_rtlsdr_import_error()
        error_text = str(import_error) if import_error else "RTL-SDR dependency unavailable"
        messagebox.showerror(
            "RTL-SDR Unavailable",
            "RTL-SDR support is not available in this environment.\n\n"
            "Install the native `librtlsdr` library and reconnect your device, then try again.\n\n"
            f"Details: {error_text}",
        )

    def _create_menu_bar(self, theme="light"):
        if theme == "dark":
            menu_bg = "#555555"
            menu_fg = "#aaaaaa"
        else:
            menu_bg = "#eeeeee"
            menu_fg = "#cccccc"

        self._menu_scroll_offset = 0
        self._menu_theme = theme
        self._menu_bg = menu_bg

        # Full-width menu bar background
        self.menu_bar = tk.Frame(self.root, bg=menu_bg, height=28)
        self.menu_bar.pack(fill="x", side="top")
        self.menu_bar.pack_propagate(False)

        # Divider under the menu bar to create a crisp bottom border
        self._menu_divider = tk.Frame(self.root, height=1, bg=menu_fg)
        self._menu_divider.pack(fill="x")

        # Canvas for scrollable menu buttons
        self.menu_canvas = tk.Canvas(
            self.menu_bar,
            bg=menu_bg,
            highlightthickness=0,
            bd=0,
            height=28,
        )
        self.menu_canvas.pack(side="left", fill="both", expand=True, padx=(0, 2))

        # Frame to hold the actual menu buttons inside the canvas
        self.menu_btns_frame = tk.Frame(self.menu_canvas, bg=menu_bg)
        self.menu_window = self.menu_canvas.create_window(
            (0, 0),
            window=self.menu_btns_frame,
            anchor="nw",
        )

        # Left scroll arrow button
        self.menu_left_btn = cbuttons.make_button(self.menu_bar, text="<")
        self.menu_left_btn.configure(width=1, command=self._scroll_menu_left)
        self.menu_left_btn.pack(side="left", padx=(2, 0))

        # Right scroll arrow button
        self.menu_right_btn = cbuttons.make_button(self.menu_bar, text=">")
        self.menu_right_btn.configure(width=1, command=self._scroll_menu_right)
        self.menu_right_btn.pack(side="right", padx=2)

        # Bind events for layout and resize
        self.menu_btns_frame.bind("<Configure>", self._on_menu_buttons_configure)
        self.menu_canvas.bind("<Configure>", self._on_menu_canvas_configure)
        self.root.bind("<Configure>", self._update_menu_bar_overflow, add="+")

        # Create menu buttons and pack into the scrollable frame
        self.file_btn = cbuttons.make_button(self.menu_btns_frame, text="File")
        self.file_btn.pack(side="left", padx=4)
        self.file_btn.configure(command=lambda: self.menu.show_menu(self.file_btn, [
            ("New Project", self.new_project),
            ("Save Project", self.save_project),
            ("Open Project", self.open_project),
            ("New Spreadsheet", self.on_new),
            ("Open Spreadsheet", self.on_open),
            ("Exit", self.root.quit),
        ]))

        self.help_btn = cbuttons.make_button(self.menu_btns_frame, text="Help")
        self.help_btn.pack(side="left")
        self.help_btn.configure(command=lambda: self.menu.show_menu(self.help_btn, [
            ("About", self.on_about),
            ("Documentation", lambda: webbrowser.open("https://parttelescopes.web.app/documentation.html")),
        ]))

        self.tools_btn = cbuttons.make_button(self.menu_btns_frame, text="Tools")
        self.tools_btn.pack(side="left", padx=4)
        self.tools_btn.configure(command=lambda: self.menu.show_menu(self.tools_btn, [
            ("Calibration", self.calibration_tool),
            ("Health Diagnostics", self.health_diagnostics_action),
            ("Settings", self.settings_tool),
            ("Local Information", lambda: self.obtain_local_info()),
        ]))

        self.record_btn = cbuttons.make_button(self.menu_btns_frame, text="Record")
        self.record_btn.pack(side="left")
        self.record_btn.configure(command=lambda: self.menu.show_menu(self.record_btn, [
            ("Begin Data Recording", self.start_recording_menu),
            ("Run RFI Mapping", self.rfi_mapping_action),
            ("Advanced Signal View", self.advanced_signal_view_action),
            ("Compare Recordings", self.compare_recordings_action),
            ("Info", lambda: msgPopup("Recording Tools", "Use the 'Begin Data Recording' option to capture IQ data from a connected RTL-SDR device. Use RFI Mapping for quick power sweeps and Advanced/Compare views for inspection.")),
            ("Recording Browser", self.recording_browser_action),
        ]))

        self.learning_btn = cbuttons.make_button(self.menu_btns_frame, text="Learning")
        self.learning_btn.pack(side="left", padx=4)
        self.learning_btn.configure(command=lambda: self.menu.show_menu(self.learning_btn, [
            ("Lesson Wizard", self.lesson_wizard_action),
            ("Resource Library", self.resource_library_action),
            ("Education Mode", self.education_mode_action),
        ]))

    def _on_menu_buttons_configure(self, event=None):
        """Called when menu buttons frame is resized."""
        self.menu_canvas.configure(scrollregion=self.menu_canvas.bbox("all"))
        self._update_menu_bar_overflow()

    def _on_menu_canvas_configure(self, event=None):
        """Called when canvas is resized."""
        self._update_menu_bar_overflow()

    def _update_menu_bar_overflow(self, event=None):
        """Detect overflow and show/hide arrow buttons accordingly."""
        try:
            canvas_width = self.menu_canvas.winfo_width()
            frame_width = self.menu_btns_frame.winfo_reqwidth()

            if canvas_width < 1 or frame_width < 1:
                return

            has_overflow = frame_width > canvas_width

            if has_overflow:
                self.menu_left_btn.pack(side="left", padx=(2, 0))
                self.menu_right_btn.pack(side="right", padx=2)
                self._update_arrow_states()
            else:
                self.menu_left_btn.pack_forget()
                self.menu_right_btn.pack_forget()
                self._menu_scroll_offset = 0
                self.menu_canvas.coords(self.menu_window, (0, 0))
        except Exception:
            pass

    def _update_arrow_states(self):
        """Enable/disable arrow buttons based on scroll position."""
        frame_width = self.menu_btns_frame.winfo_reqwidth()
        canvas_width = self.menu_canvas.winfo_width()
        max_offset = max(0, frame_width - canvas_width)

        self.menu_left_btn.state(["!disabled"] if self._menu_scroll_offset > 0 else ["disabled"])
        self.menu_right_btn.state(["!disabled"] if self._menu_scroll_offset < max_offset else ["disabled"])

    def _scroll_menu_left(self):
        """Scroll menu buttons to the left."""
        self._menu_scroll_offset = max(0, self._menu_scroll_offset - 60)
        self.menu_canvas.coords(self.menu_window, (-self._menu_scroll_offset, 0))
        self._update_arrow_states()

    def _scroll_menu_right(self):
        """Scroll menu buttons to the right."""
        frame_width = self.menu_btns_frame.winfo_reqwidth()
        canvas_width = self.menu_canvas.winfo_width()
        max_offset = max(0, frame_width - canvas_width)
        self._menu_scroll_offset = min(max_offset, self._menu_scroll_offset + 60)
        self.menu_canvas.coords(self.menu_window, (-self._menu_scroll_offset, 0))
        self._update_arrow_states()

    def _normalize_recording_path(self, path):
        if not isinstance(path, str) or not path.strip():
            return ""
        return os.path.abspath(os.path.normpath(path))

    def _on_recording_annotations_changed(self, source_file, annotations):
        key = self._normalize_recording_path(source_file)
        if not key:
            return
        if annotations:
            self._recording_annotations[key] = list(annotations)
        elif key in self._recording_annotations:
            del self._recording_annotations[key]

    def _register_recent_recording(self, samples_path):
        normalized = self._normalize_recording_path(samples_path)
        if not normalized:
            return
        self._recent_recordings = [path for path in self._recent_recordings if path != normalized]
        self._recent_recordings.insert(0, normalized)
        self._recent_recordings = self._recent_recordings[:20]

    def _resolve_latest_recording_path(self):
        for path in self._recent_recordings:
            if os.path.exists(path):
                return path

        recordings_dir = os.path.join("data", "recordings")
        if not os.path.isdir(recordings_dir):
            return None

        npy_files = []
        for name in os.listdir(recordings_dir):
            if name.lower().endswith(".npy"):
                full = os.path.join(recordings_dir, name)
                try:
                    npy_files.append((os.path.getmtime(full), full))
                except Exception:
                    continue

        if not npy_files:
            return None
        npy_files.sort(reverse=True)
        latest = npy_files[0][1]
        self._register_recent_recording(latest)
        return latest

    def _resolve_two_latest_recordings(self):
        candidates = []
        for path in self._recent_recordings:
            if os.path.exists(path):
                candidates.append(path)
            if len(candidates) >= 2:
                return candidates[0], candidates[1]

        recordings_dir = os.path.join("data", "recordings")
        if not os.path.isdir(recordings_dir):
            return None, None

        npy_files = []
        for name in os.listdir(recordings_dir):
            if name.lower().endswith(".npy"):
                full = os.path.join(recordings_dir, name)
                try:
                    npy_files.append((os.path.getmtime(full), full))
                except Exception:
                    continue

        npy_files.sort(reverse=True)
        if len(npy_files) < 2:
            return None, None

        first = npy_files[0][1]
        second = npy_files[1][1]
        self._register_recent_recording(first)
        self._register_recent_recording(second)
        return first, second

    def _create_content(self, theme="light"):
        if theme == "dark":
            self.root.configure(bg="#333333")
        else:
            self.root.configure(bg="#ffffff")

        frame = ttk.Frame(self.root, padding=20)
        frame.pack(fill="both", expand=True)

        self.log_container = ttk.Frame(frame)
        self.log_container.pack(fill="both", expand=True)

        self.log_text = tk.Text(
            self.log_container,
            wrap="word",
            height=12,
            font=("Menlo", 11),
            padx=8,
            pady=6,
            takefocus=0,
            exportselection=False,
        )
        # Use a classic Tk scrollbar with explicit styling so it remains clearly visible.
        self.log_scrollbar = tk.Scrollbar(
            self.log_container,
            orient="vertical",
            command=self.log_text.yview,
            width=14,
            bg="#d9d9d9",
            activebackground="#bfbfbf",
            troughcolor="#f2f2f2",
            relief="sunken",
            borderwidth=1,
        )
        self.log_text.configure(yscrollcommand=self.log_scrollbar.set)
        self.log_text.tag_configure("log_entry", spacing1=2, spacing2=1, spacing3=10)

        self.log_text.pack(side="left", fill="both", expand=True)
        self.log_scrollbar.pack(side="right", fill="y")

        self.log_text.configure(state="disabled")
        self.log_text.configure(font=("TkDefaultFont", 10), spacing1=2, spacing3=2)

    def _append_log(self, text):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{text}\n", "log_entry")

        # Clear any active selection so new entries never remain highlighted.
        self.log_text.tag_remove("sel", "1.0", "end")

        # Force the viewport to the real bottom, including wrapped/overflow lines.
        self.log_text.see("end")
        self.log_text.yview_moveto(1.0)
        self.log_text.configure(state="disabled")

    # Example commands
    def on_new(self):
        # Open a new spreadsheet window
        sheet = SpreadsheetWindow(self.root)
        self._spreadsheet_windows.append(sheet)
        self._append_log("New spreadsheet opened")

    def on_open(self):
        filepath = filedialog.askopenfilename(
            title="Open Spreadsheet",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
        )
        if not filepath:
            return 
        sheet = SpreadsheetWindow(self.root, file_path=filepath)
        self._spreadsheet_windows.append(sheet)
        self._append_log("Spreadsheet opened")

    def _active_spreadsheets(self):
        active = []
        for sheet in self._spreadsheet_windows:
            try:
                if hasattr(sheet, "win") and sheet.win.winfo_exists():
                    active.append(sheet)
            except Exception:
                continue
        self._spreadsheet_windows = active
        return active

    def _session_log_entries(self):
        if not hasattr(self, "log_text"):
            return []

        try:
            log_content = self.log_text.get("1.0", "end-1c")
        except Exception:
            return []

        lines = [line for line in log_content.splitlines() if line.strip()]
        return lines

    def _clear_log(self):
        if not hasattr(self, "log_text"):
            return

        try:
            self.log_text.configure(state="normal")
            self.log_text.delete("1.0", "end")
            self.log_text.configure(state="disabled")
        except Exception:
            return

    def _write_settings(self, settings):
        os.makedirs("data", exist_ok=True)
        self.settings = save_settings_file(settings, settings_path="data/settings.json")

    def _apply_runtime_settings(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        theme = self.settings.get("theme", "light")
        if hasattr(self, "menu") and self.menu is not None:
            self.menu.set_theme(theme)

        if theme == "dark":
            self.root.configure(bg="#333333")
            menu_bg = "#555555"
            menu_fg = "#aaaaaa"
            btn_bg = "#666666"
            btn_fg = "#f1f1f1"
            btn_active = "#7a7a7a"
            log_bg = "#1f1f1f"
            log_fg = "#f1f1f1"
            insert_bg = "#f1f1f1"

            style.configure(".", background="#333333", foreground="#f1f1f1")
            style.configure("TFrame", background="#333333")
            style.configure("TLabel", background="#333333", foreground="#f1f1f1")
            style.configure("TButton", background="#505050", foreground="#f1f1f1")
            style.map("TButton", background=[("active", "#666666")])
            style.configure("TCheckbutton", background="#333333", foreground="#f1f1f1")
            style.configure("TNotebook", background="#333333")
            style.configure("TNotebook.Tab", background="#505050", foreground="#f1f1f1")
            style.map("TNotebook.Tab", background=[("selected", "#6b6b6b")])
            style.configure("TEntry", fieldbackground="#2c2c2c", foreground="#f1f1f1")
            style.configure("TCombobox", fieldbackground="#2c2c2c", foreground="#f1f1f1", background="#505050")
            style.map("TCombobox", fieldbackground=[("readonly", "#2c2c2c")], foreground=[("readonly", "#f1f1f1")])
            style.configure("TSpinbox", fieldbackground="#2c2c2c", foreground="#f1f1f1")
            style.configure("TopMenu.TButton", background=btn_bg, foreground=btn_fg, padding=(8, 3), relief="flat")
            style.map("TopMenu.TButton", background=[("active", btn_active)], foreground=[("active", btn_fg)])
        else:
            self.root.configure(bg="#ffffff")
            menu_bg = "#eeeeee"
            menu_fg = "#cccccc"
            btn_bg = "#f2f2f2"
            btn_fg = "#111111"
            btn_active = "#e0e0e0"
            log_bg = "#ffffff"
            log_fg = "#111111"
            insert_bg = "#111111"

            style.configure(".", background="#ffffff", foreground="#111111")
            style.configure("TFrame", background="#ffffff")
            style.configure("TLabel", background="#ffffff", foreground="#111111")
            style.configure("TButton", background="#f2f2f2", foreground="#111111")
            style.map("TButton", background=[("active", "#e0e0e0")])
            style.configure("TCheckbutton", background="#ffffff", foreground="#111111")
            style.configure("TNotebook", background="#ffffff")
            style.configure("TNotebook.Tab", background="#f2f2f2", foreground="#111111")
            style.map("TNotebook.Tab", background=[("selected", "#e0e0e0")])
            style.configure("TEntry", fieldbackground="#ffffff", foreground="#111111")
            style.configure("TCombobox", fieldbackground="#ffffff", foreground="#111111", background="#f2f2f2")
            style.map("TCombobox", fieldbackground=[("readonly", "#ffffff")], foreground=[("readonly", "#111111")])
            style.configure("TSpinbox", fieldbackground="#ffffff", foreground="#111111")
            style.configure("TopMenu.TButton", background=btn_bg, foreground=btn_fg, padding=(8, 3), relief="flat")
            style.map("TopMenu.TButton", background=[("active", btn_active)], foreground=[("active", btn_fg)])

        if hasattr(self, "menu_bar"):
            self.menu_bar.configure(bg=menu_bg)
        if hasattr(self, "_menu_divider"):
            self._menu_divider.configure(bg=menu_fg)
        if hasattr(self, "menu_canvas"):
            self.menu_canvas.configure(bg=menu_bg)
        if hasattr(self, "menu_btns_frame"):
            self.menu_btns_frame.configure(bg=menu_bg)

        for button_name in ["file_btn", "help_btn", "tools_btn", "record_btn", "learning_btn", "menu_left_btn", "menu_right_btn"]:
            btn = getattr(self, button_name, None)
            if btn is not None:
                btn.configure(style="TopMenu.TButton")

        if hasattr(self, "log_text"):
            font_size = int(self.settings.get("font_size", 10))
            self.log_text.configure(font=("TkDefaultFont", font_size), bg=log_bg, fg=log_fg, insertbackground=insert_bg)

        if hasattr(self, "log_scrollbar"):
            if theme == "dark":
                self.log_scrollbar.configure(bg="#5c5c5c", activebackground="#787878", troughcolor="#2a2a2a")
            else:
                self.log_scrollbar.configure(bg="#d9d9d9", activebackground="#bfbfbf", troughcolor="#f2f2f2")

    def new_project(self):
        should_continue = messagebox.askyesno(
            "New Project",
            "Start a new project session? This will close open spreadsheet windows and clear the log.",
        )
        if not should_continue:
            return

        for sheet in self._active_spreadsheets():
            try:
                sheet.win.destroy()
            except Exception:
                continue

        self._spreadsheet_windows = []
        self._clear_log()
        self._append_log("Started a new project session")

    def save_project(self):
        project_path = filedialog.asksaveasfilename(
            title="Save AH Project",
            defaultextension=".ahf",
            filetypes=[("AH Project Files", "*.ahf"), ("All Files", "*.*")],
        )
        if not project_path:
            return

        try:
            open_sheet_paths = []
            for sheet in self._active_spreadsheets():
                path = getattr(sheet, "_saved_path", None)
                if path:
                    open_sheet_paths.append(path)

            payload = build_session_payload(
                settings=self._read_settings(),
                log_entries=self._session_log_entries(),
                spreadsheet_paths=open_sheet_paths,
                recording_annotations=[
                    {
                        "samples_path": path,
                        "annotations": notes,
                    }
                    for path, notes in self._recording_annotations.items()
                    if notes
                ],
            )
            written_path = write_ahf_file(project_path, payload)
            messagebox.showinfo("Save Project", f"Project saved to\n{written_path}")
            self._append_log(f"Project saved: {written_path}")
        except Exception as error:
            messagebox.showerror("Save Project", f"Could not save project:\n{error}")

    def open_project(self):
        project_path = filedialog.askopenfilename(
            title="Open AH Project",
            filetypes=[("AH Project Files", "*.ahf"), ("All Files", "*.*")],
        )
        if not project_path:
            return

        try:
            payload = read_ahf_file(project_path)

            saved_settings = payload.get("settings", {})
            if saved_settings:
                self._write_settings(saved_settings)
                self.root.title(f"AH-Control v{saved_settings.get('version', '0.1.0')}")

            for sheet in self._active_spreadsheets():
                try:
                    sheet.win.destroy()
                except Exception:
                    continue
            self._spreadsheet_windows = []
            self._recording_annotations = {}

            restored_count = 0
            missing_count = 0
            for csv_path in payload.get("open_spreadsheets", []):
                if not isinstance(csv_path, str) or not csv_path.strip():
                    continue
                if os.path.exists(csv_path):
                    sheet = SpreadsheetWindow(self.root, file_path=csv_path)
                    self._spreadsheet_windows.append(sheet)
                    restored_count += 1
                else:
                    self._append_log(f"Missing spreadsheet in project: {csv_path}")
                    missing_count += 1

            restored_annotations = 0
            for entry in payload.get("recording_annotations", []):
                samples_path = self._normalize_recording_path(entry.get("samples_path", ""))
                annotations = entry.get("annotations", [])
                if not samples_path or not isinstance(annotations, list):
                    continue
                self._recording_annotations[samples_path] = list(annotations)
                restored_annotations += len(annotations)

            self._clear_log()
            for line in payload.get("log_entries", []):
                if isinstance(line, str):
                    self._append_log(line)

            self._append_log(f"Project opened: {project_path}")
            messagebox.showinfo(
                "Open Project",
                (
                    f"Project loaded from\n{project_path}\n\n"
                    f"Spreadsheets restored: {restored_count}\n"
                    f"Spreadsheets missing: {missing_count}\n"
                    f"Annotations restored: {restored_annotations}"
                ),
            )
        except Exception as error:
            messagebox.showerror("Open Project", f"Could not open project:\n{error}")

    def on_about(self):
        settings = self._read_settings()
        version = settings.get("version", "0.1.0")
        self.help_popup = msgPopup(
            title="About AH-Control",
            message=(
                f"Welcome to AH Control v{version}! This application is intended to be a simple data collection and analysis tool to complement the PART Access Horizon telescope, but it can be used with any RTL-SDR device. To get started, connect your RTL-SDR that is linked to your antenna to this device and use the 'Record' menu to capture data. Use the 'Tools' menu for calibration and settings. If you want to load an existing project, or create a new one to save your data, click on the 'File' menu. Settings can be changed under tools. For further documentation, visit the Help menu. Happy exploring! - The PART Team"
                ),
                size=(450, 300),
                msgtype="info"
        )

    def _detect_rtl_sdr_devices(self):
        return detect_rtl_sdr_devices()

    def _build_device_selector(self, parent):
        devices = self._detect_rtl_sdr_devices()
        if not devices:
            return devices, None

        labels = [device["label"] for device in devices]
        selector = ttk.Combobox(parent, values=labels, state="readonly")
        selector.current(0)
        return devices, selector

    def calibration_tool(self):
        if self._get_rtlsdr_class() is None:
            self._show_rtlsdr_dependency_error()
            self._append_log("Calibration unavailable: missing RTL-SDR dependency")
            return

        popup = newPopup(self.root, name="Calibration Tool", geometry="460x300")

        ttk.Label(popup.win, text="Select RTL-SDR device").pack(pady=(10, 2))
        devices, device_selector = self._build_device_selector(popup.win)

        if device_selector is None:
            ttk.Label(popup.win, text="No RTL-SDR device detected.").pack(pady=6)
            ttk.Button(
                popup.win,
                text="Retry Detection",
                command=lambda: (popup.win.destroy(), self.calibration_tool()),
            ).pack(pady=8)
            self._append_log("Calibration: no SDR device detected")
            return

        device_selector.pack(fill="x", padx=12)

        ttk.Label(popup.win, text="Center Frequency (Hz)").pack(pady=(8, 2))
        center_freq_entry = ttk.Entry(popup.win)
        center_freq_entry.insert(0, "100000000")
        center_freq_entry.pack(fill="x", padx=12)

        ttk.Label(popup.win, text="Sample Rate (Hz)").pack(pady=(8, 2))
        sample_rate_entry = ttk.Entry(popup.win)
        sample_rate_entry.insert(0, "2048000")
        sample_rate_entry.pack(fill="x", padx=12)

        ttk.Label(popup.win, text="Gain (dB)").pack(pady=(8, 2))
        gain_entry = ttk.Entry(popup.win)
        gain_entry.insert(0, "20")
        gain_entry.pack(fill="x", padx=12)

        status_label = ttk.Label(popup.win, text="Ready")
        status_label.pack(pady=10)

        widgets_to_disable = [device_selector, center_freq_entry, sample_rate_entry, gain_entry]

        def run_calibration():
            selected_label = device_selector.get()
            selected_device = next((d for d in devices if d["label"] == selected_label), None)
            if selected_device is None:
                messagebox.showerror("Calibration", "Please select a device.")
                return

            try:
                center_freq_hz = self._validate_range(
                    self._parse_float(center_freq_entry.get(), "Center Frequency"),
                    "Center Frequency",
                    minimum=1_000,
                    maximum=3_000_000_000,
                )
                sample_rate_hz = self._validate_range(
                    self._parse_float(sample_rate_entry.get(), "Sample Rate"),
                    "Sample Rate",
                    minimum=1_000,
                    maximum=3_200_000,
                )
                gain_db = self._validate_range(
                    self._parse_float(gain_entry.get(), "Gain"),
                    "Gain",
                    minimum=-10,
                    maximum=60,
                )
            except ValueError as error:
                messagebox.showerror("Calibration", str(error))
                return

            status_label.config(text="Calibrating...")
            run_button.state(["disabled"])
            for widget in widgets_to_disable:
                try:
                    widget.state(["disabled"])
                except Exception:
                    continue

            def do_calibration():
                samples = capture_rtl_sdr_samples(
                    device_index=selected_device["index"],
                    center_freq_hz=center_freq_hz,
                    sample_rate_hz=sample_rate_hz,
                    gain_db=gain_db,
                    num_samples=262144,
                    settings=self.settings,
                )
                avg_power = float(np.mean(np.abs(samples) ** 2))
                return avg_power

            def on_success(avg_power):
                status_label.config(text=f"Calibration OK | Avg power: {avg_power:.6f}")
                self._append_log(f"Calibration complete: device {selected_device['index']}")

            def on_error(error):
                messagebox.showerror("Calibration", f"Calibration failed: {error}")
                status_label.config(text="Calibration failed")
                self._append_log("Calibration failed")

            def on_finally():
                run_button.state(["!disabled"])
                for widget in widgets_to_disable:
                    try:
                        widget.state(["!disabled"])
                    except Exception:
                        continue

            self._run_in_background(do_calibration, on_success=on_success, on_error=on_error, on_finally=on_finally)

        run_button = ttk.Button(popup.win, text="Run Calibration", command=run_calibration)
        run_button.pack(pady=(2, 12))
        self._append_log("Calibration tool opened")

    def health_diagnostics_action(self):
        if self._get_rtlsdr_class() is None:
            self._show_rtlsdr_dependency_error()
            self._append_log("Health diagnostics unavailable: missing RTL-SDR dependency")
            return

        HealthDiagnosticsWindow(
            root=self.root,
            detect_devices_fn=self._detect_rtl_sdr_devices,
            read_samples_fn=lambda **kwargs: capture_rtl_sdr_samples(settings=self.settings, **kwargs),
            run_in_background_fn=self._run_in_background,
            append_log_fn=self._append_log,
            settings=self.settings,
        )
        self._append_log("Health diagnostics opened")

    def start_recording_menu(self, initial_config=None):
        DataRecordingWindow(
            root=self.root,
            run_in_background_fn=self._run_in_background,
            append_log_fn=self._append_log,
            settings=self.settings,
            initial_config=initial_config,
            on_saved_callback=lambda result: self._register_recent_recording(result.get("samples_path")),
        )

        self._append_log("Recording setup opened")

    def rfi_mapping_action(self, profile_preset=None, auto_run=False):
        popup = newPopup(self.root, name="RFI Mapping", geometry="560x320")
        container = ttk.Frame(popup.win)
        container.pack(fill="both", expand=True, padx=12, pady=10)

        ttk.Label(container, text="RFI Mapping", font=("TkDefaultFont", 10, "bold")).pack(anchor="w")
        ttk.Label(
            container,
            text="Sweep selected center frequencies and build a quick RFI power map.",
            justify="left",
        ).pack(anchor="w", pady=(4, 10))

        devices = self._detect_rtl_sdr_devices()
        labels = [device["label"] for device in devices]

        row1 = ttk.Frame(container)
        row1.pack(fill="x", pady=(0, 8))
        ttk.Label(row1, text="Device", width=14).pack(side="left")
        device_combo = ttk.Combobox(row1, state="readonly", values=labels)
        device_combo.pack(side="left", fill="x", expand=True)
        if labels:
            device_combo.current(0)

        profiles = ["FM Broadcast", "Airband", "NOAA Weather"]
        row2 = ttk.Frame(container)
        row2.pack(fill="x", pady=(0, 8))
        ttk.Label(row2, text="Profile", width=14).pack(side="left")
        profile_combo = ttk.Combobox(row2, state="readonly", values=profiles)
        profile_combo.pack(side="left", fill="x", expand=True)
        profile_combo.current(0)
        if profile_preset in profiles:
            profile_combo.set(profile_preset)

        status_var = tk.StringVar(value="Ready")
        ttk.Label(container, textvariable=status_var).pack(anchor="w", pady=(2, 10))

        def profile_centers_hz(profile_name):
            if profile_name == "FM Broadcast":
                return [88_100_000, 98_300_000, 107_900_000]
            if profile_name == "Airband":
                return [118_000_000, 125_500_000, 136_900_000]
            return [162_400_000, 162_450_000, 162_550_000]

        def run_mapping():
            selected_label = device_combo.get().strip()
            selected_device = next((d for d in devices if d["label"] == selected_label), None)
            if selected_device is None:
                messagebox.showerror("RFI Mapping", "Please select a valid device.")
                return

            centers = profile_centers_hz(profile_combo.get().strip())
            sample_rate_hz = float(self.settings.get("capture_default_sample_rate_hz", 2_048_000))
            gain_db = float(self.settings.get("capture_default_gain_db", 20.0))
            num_samples = min(262_144, int(self.settings.get("capture_sample_cap", 2_500_000)))

            run_btn.state(["disabled"])
            status_var.set("Running RFI sweep...")

            def do_work():
                points = []
                for index, center in enumerate(centers):
                    samples = capture_rtl_sdr_samples(
                        device_index=selected_device["index"],
                        center_freq_hz=float(center),
                        sample_rate_hz=sample_rate_hz,
                        gain_db=gain_db,
                        num_samples=num_samples,
                        settings=self.settings,
                    )
                    power_db = float(10.0 * np.log10(np.mean(np.abs(samples) ** 2) + 1e-12))
                    points.append((float(center) / 1e6, power_db))
                    self.root.after(0, lambda i=index: status_var.set(f"Sweep progress: {i + 1}/{len(centers)}"))
                return points

            def on_success(points):
                status_var.set("RFI mapping complete")
                run_btn.state(["!disabled"])

                xs = [p[0] for p in points]
                ys = [p[1] for p in points]

                fig, ax = plt.subplots(figsize=(8.0, 4.5), dpi=100)
                ax.plot(xs, ys, marker="o", color="#e76f51", linewidth=1.2)
                ax.set_title(f"RFI Map - {profile_combo.get().strip()}")
                ax.set_xlabel("Center Frequency (MHz)")
                ax.set_ylabel("Average Power (dB)")
                ax.grid(alpha=0.25)
                fig.tight_layout()
                fig.show()

                self._append_log(
                    f"RFI mapping complete using {selected_device['label']} ({profile_combo.get().strip()})"
                )

            def on_error(error):
                status_var.set("RFI mapping failed")
                run_btn.state(["!disabled"])
                messagebox.showerror("RFI Mapping", f"Mapping failed:\n{error}")
                self._append_log("RFI mapping failed")

            self._run_in_background(do_work, on_success=on_success, on_error=on_error)

        controls = ttk.Frame(container)
        controls.pack(fill="x")
        run_btn = ttk.Button(controls, text="Run Mapping", command=run_mapping)
        run_btn.pack(side="left")
        ttk.Button(controls, text="Close", command=popup.win.destroy).pack(side="right")

        if auto_run:
            self.root.after(50, run_mapping)

    def settings_tool(self):
        SettingsWindow(
            root=self.root,
            settings_path="data/settings.json",
            settings_snapshot=self.settings,
            on_save_callback=self._on_settings_saved,
        )
        self._append_log("Settings opened")

    def _on_settings_saved(self, settings):
        self.settings = settings
        self.root.title(f"AH-Control v{self.settings.get('version')}")
        self._apply_runtime_settings()
        self._append_log("Settings saved")

    def _open_static_advanced_signal_view_popup(self, source_file, analysis, sample_rate_hz, center_freq_hz):
        popup = newPopup(self.root, name="Advanced Signal View", geometry="980x700")

        top_row = ttk.Frame(popup.win)
        top_row.pack(fill="x", padx=10, pady=(8, 4))

        averaged_psd_db = analysis["averaged_psd_db"]
        waterfall_db = analysis["waterfall_db"]
        freq_axis_mhz = build_frequency_axis_mhz(analysis["nfft"], sample_rate_hz, center_freq_hz)
        peak_metrics = extract_peak_metrics(averaged_psd_db, freq_axis_mhz)

        summary = (
            f"File: {os.path.basename(source_file)} | "
            f"Center: {center_freq_hz / 1e6:.6f} MHz | "
            f"Rate: {sample_rate_hz / 1e6:.3f} MS/s | "
            f"NFFT: {analysis['nfft']} | Segments: {analysis['used_segments']} | "
            f"Peak: {peak_metrics['peak_freq_mhz']:.6f} MHz ({peak_metrics['peak_power_db']:.1f} dB) | "
            f"SNR: {peak_metrics['snr_db']:.1f} dB"
        )
        ttk.Label(top_row, text=summary, justify="left", anchor="w").pack(fill="x")

        fig, axes = plt.subplots(2, 1, figsize=(10, 6.5), dpi=100)
        ax_spectrum, ax_waterfall = axes

        ax_spectrum.plot(freq_axis_mhz, averaged_psd_db, color="#0b7285", linewidth=1.1)
        ax_spectrum.set_title("Average Spectrum (FFT)")
        ax_spectrum.set_xlabel("Frequency (MHz)")
        ax_spectrum.set_ylabel("Power (dB)")
        ax_spectrum.grid(alpha=0.25)

        time_axis_s = (np.arange(waterfall_db.shape[0]) * analysis["nfft"]) / max(sample_rate_hz, 1.0)
        image = ax_waterfall.imshow(
            waterfall_db,
            aspect="auto",
            origin="lower",
            extent=[freq_axis_mhz[0], freq_axis_mhz[-1], time_axis_s[0], time_axis_s[-1] if time_axis_s.size else 0],
            cmap="magma",
        )
        ax_waterfall.set_title("Waterfall")
        ax_waterfall.set_xlabel("Frequency (MHz)")
        ax_waterfall.set_ylabel("Time (s)")
        fig.colorbar(image, ax=ax_waterfall, label="Power (dB)")
        fig.tight_layout(rect=[0, 0.04, 1, 0.95])

        toolbar_frame = ttk.Frame(popup.win)
        toolbar_frame.pack(side="bottom", fill="x", padx=10, pady=(0, 6))

        canvas = FigureCanvasTkAgg(fig, master=popup.win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=(4, 0))

        toolbar = NavigationToolbar2Tk(canvas, toolbar_frame, pack_toolbar=False)
        toolbar.update()
        toolbar.pack(side="left", fill="x")

        close_btn = ttk.Button(toolbar_frame, text="Close", command=lambda: (plt.close(fig), popup.win.destroy()))
        close_btn.pack(side="right")
        popup.win.protocol("WM_DELETE_WINDOW", lambda: (plt.close(fig), popup.win.destroy()))

    def _open_interactive_advanced_signal_view_window(self, source_file, analysis, sample_rate_hz, center_freq_hz):
        source_key = self._normalize_recording_path(source_file)
        AdvancedSignalWindow(
            root=self.root,
            source_file=source_file,
            analysis=analysis,
            sample_rate_hz=sample_rate_hz,
            center_freq_hz=center_freq_hz,
            on_export=self._open_static_advanced_signal_view_popup,
            settings=self.settings,
            annotations=self._recording_annotations.get(source_key, []),
            on_annotations_changed=self._on_recording_annotations_changed,
        )

    def _lesson_open_recording(self, step_payload=None):
        self.start_recording_menu(initial_config=step_payload or {})

    def _lesson_open_advanced_view(self, step_payload=None):
        payload = step_payload or {}
        samples_path = payload.get("samples_path")
        if not samples_path:
            samples_path = self._resolve_latest_recording_path()
        if not samples_path:
            messagebox.showwarning("Lesson Wizard", "No recordings available yet. Please record first.")
            return
        self.advanced_signal_view_action(samples_path=samples_path)

    def _lesson_compare_recordings(self, step_payload=None):
        payload = step_payload or {}
        first = payload.get("first_samples_path")
        second = payload.get("second_samples_path")
        if not first or not second:
            first, second = self._resolve_two_latest_recordings()
        if not first or not second:
            messagebox.showwarning("Lesson Wizard", "Need at least two recordings to compare.")
            return
        self.compare_recordings_action(first_path=first, second_path=second)

    def _lesson_run_rfi(self, step_payload=None):
        payload = step_payload or {}
        profile = payload.get("profile")
        auto_run = bool(payload.get("auto_run", False))
        self.rfi_mapping_action(profile_preset=profile, auto_run=auto_run)

    def lesson_wizard_action(self):
        LessonWizardWindow(
            root=self.root,
            templates_path=os.path.join("data", "lesson_templates.json"),
            on_open_recording=self._lesson_open_recording,
            on_open_advanced_view=self._lesson_open_advanced_view,
            on_compare_recordings=self._lesson_compare_recordings,
            on_run_rfi_mapping=self._lesson_run_rfi,
        )
        self._append_log("Lesson wizard opened")

    def compare_recordings_action(self, first_path=None, second_path=None):
        default_dir = os.path.join("data", "recordings")
        if not first_path:
            first_path = filedialog.askopenfilename(
                title="Select First Recording",
                initialdir=default_dir if os.path.isdir(default_dir) else None,
                filetypes=[("NumPy Recording", "*.npy"), ("All Files", "*.*")],
            )
            if not first_path:
                return

        if not second_path:
            second_path = filedialog.askopenfilename(
                title="Select Second Recording",
                initialdir=os.path.dirname(first_path),
                filetypes=[("NumPy Recording", "*.npy"), ("All Files", "*.*")],
            )
            if not second_path:
                return

        self._register_recent_recording(first_path)
        self._register_recent_recording(second_path)

        status_popup = newPopup(self.root, name="Comparison", geometry="380x120")
        ttk.Label(status_popup.win, text="Analyzing two recordings...", anchor="center").pack(fill="x", padx=12, pady=(16, 6))
        ttk.Label(status_popup.win, text=f"{os.path.basename(first_path)} vs {os.path.basename(second_path)}", anchor="center").pack(fill="x", padx=12, pady=(0, 12))

        def do_compare():
            left = analyze_recording_for_advanced_view(
                samples_path=first_path,
                nfft=int(self.settings.get("analysis_nfft", 4096)),
                max_segments=int(self.settings.get("analysis_max_segments", 350)),
                max_preview_samples=int(self.settings.get("analysis_max_preview_samples", 8_000_000)),
            )
            right = analyze_recording_for_advanced_view(
                samples_path=second_path,
                nfft=int(self.settings.get("analysis_nfft", 4096)),
                max_segments=int(self.settings.get("analysis_max_segments", 350)),
                max_preview_samples=int(self.settings.get("analysis_max_preview_samples", 8_000_000)),
            )
            return {"left": left, "right": right}

        def on_success(result):
            try:
                status_popup.win.destroy()
            except Exception:
                pass

            ComparisonWindow(
                root=self.root,
                left_file=first_path,
                right_file=second_path,
                left_result=result["left"],
                right_result=result["right"],
            )
            self._append_log(f"Comparison opened: {os.path.basename(first_path)} vs {os.path.basename(second_path)}")

        def on_error(error):
            try:
                status_popup.win.destroy()
            except Exception:
                pass
            messagebox.showerror("Compare Recordings", f"Could not compare recordings:\n{error}")
            self._append_log("Comparison failed")

        self._run_in_background(do_compare, on_success=on_success, on_error=on_error)

    def advanced_signal_view_action(self, samples_path=None):
        if not samples_path:
            default_dir = os.path.join("data", "recordings")
            samples_path = filedialog.askopenfilename(
                title="Open Recording for Advanced View",
                initialdir=default_dir if os.path.isdir(default_dir) else None,
                filetypes=[("NumPy Recording", "*.npy"), ("All Files", "*.*")],
            )

            if not samples_path:
                return

        self._register_recent_recording(samples_path)

        status_popup = newPopup(self.root, name="Advanced Signal View", geometry="380x120")
        ttk.Label(status_popup.win, text="Analyzing recording...", anchor="center").pack(fill="x", padx=12, pady=(16, 6))
        ttk.Label(status_popup.win, text=os.path.basename(samples_path), anchor="center").pack(fill="x", padx=12, pady=(0, 12))

        def analyze_recording():
            return analyze_recording_for_advanced_view(
                samples_path=samples_path,
                nfft=int(self.settings.get("analysis_nfft", 4096)),
                max_segments=int(self.settings.get("analysis_max_segments", 350)),
                max_preview_samples=int(self.settings.get("analysis_max_preview_samples", 8_000_000)),
            )

        def on_success(result):
            try:
                status_popup.win.destroy()
            except Exception:
                pass

            self._open_interactive_advanced_signal_view_window(
                source_file=samples_path,
                analysis=result["analysis"],
                sample_rate_hz=result["sample_rate_hz"],
                center_freq_hz=result["center_freq_hz"],
            )

            if not result["metadata_found"]:
                messagebox.showwarning(
                    "Advanced Signal View",
                    "Metadata file was not found. Using default sample rate and center frequency.",
                )
            elif result.get("integrity_warnings"):
                messagebox.showwarning(
                    "Advanced Signal View",
                    "Recording metadata has integrity warnings:\n\n"
                    + "\n".join(result["integrity_warnings"][:5]),
                )
                self._append_log(
                    "Advanced signal integrity warnings: "
                    + "; ".join(result["integrity_warnings"][:3])
                )
            if result["truncated"]:
                self._append_log("Advanced view used the first 8,000,000 samples for performance")

            self._append_log(f"Advanced signal view opened: {os.path.basename(samples_path)}")

        def on_error(error):
            try:
                status_popup.win.destroy()
            except Exception:
                pass
            messagebox.showerror("Advanced Signal View", f"Could not analyze recording:\n{error}")
            self._append_log("Advanced signal view failed")

        self._run_in_background(analyze_recording, on_success=on_success, on_error=on_error)
    
    def recording_browser_action(self):
        """Open the recording browser window."""
        try:
            RecordingBrowserWindow(
                self.root,
                recordings_dir="data/recordings",
                analyze_fn=self._analyze_recording_from_browser,
                append_log_fn=self._append_log,
                settings=self.settings,
            )
        except Exception as error:
            messagebox.showerror("Recording Browser", f"Could not open recording browser:\n{error}")
            self._append_log(f"Recording browser failed: {error}")

    def _analyze_recording_from_browser(self, samples_path, metadata_path=None):
        """Analyze a recording selected from the browser in advanced view."""
        def analyze_recording():
            return analyze_recording_for_advanced_view(
                samples_path=samples_path,
                nfft=int(self.settings.get("analysis_nfft", 4096)),
                max_segments=int(self.settings.get("analysis_max_segments", 350)),
                max_preview_samples=int(self.settings.get("analysis_max_preview_samples", 8_000_000)),
            )

        def on_success(result):
            self._append_log("Advanced analysis complete")
            try:
                # Extract data from result structure
                analysis = result.get("analysis", {})
                sample_rate_hz = result.get("sample_rate_hz", 2_048_000)
                center_freq_hz = result.get("center_freq_hz", 100_000_000)
                
                AdvancedSignalWindow(
                    self.root,
                    source_file=os.path.basename(samples_path),
                    analysis=analysis,
                    sample_rate_hz=sample_rate_hz,
                    center_freq_hz=center_freq_hz,
                    settings=self.settings,
                )
            except Exception as error:
                messagebox.showerror("Advanced Signal View", f"Could not display results:\n{error}")
                self._append_log("Advanced signal view failed")

        def on_error(error):
            messagebox.showerror("Advanced Signal View", f"Could not analyze recording:\n{error}")
            self._append_log("Advanced signal view failed")

        self._run_in_background(analyze_recording, on_success=on_success, on_error=on_error)

    def resource_library_action(self):
        pass

    def education_mode_action(self):
        pass

    def _read_settings(self):
        self.settings = load_settings_file("data/settings.json")
        return dict(self.settings)
        
    def obtain_local_info(self):
        try:
            local_info = obtain_local_info(
                timeout_s=int(self.settings.get("network_timeout_s", 6)),
                allow_ip_fallback=bool(self.settings.get("local_info_use_ip_fallback", True)),
            )
            if local_info is None:
                messagebox.showerror("Local Information", "Could not obtain local information.")
                return

            latitude = local_info.get("latitude")
            longitude = local_info.get("longitude")
            timezone = local_info.get("timezone")
            local_time = local_info.get("local_time")

            sidereal_and_hour_angle = compute_sidereal_time_and_hour_angle(latitude, longitude)
            sidereal_time = sidereal_and_hour_angle.get("sidereal_time")
            sun_altitude = sidereal_and_hour_angle.get("sun_altitude")
            sun_azimuth = sidereal_and_hour_angle.get("sun_azimuth")
            galactic_center_altitude = sidereal_and_hour_angle.get("galactic_center_altitude")
            galactic_center_azimuth = sidereal_and_hour_angle.get("galactic_center_azimuth")


            local_info = {
                "latitude": latitude,
                "longitude": longitude,
                "timezone": timezone,
                "local_time": local_time,
                "sidereal_time": sidereal_time,
                "sun_altitude": sun_altitude,
                "sun_azimuth": sun_azimuth,
                "galactic_center_altitude": galactic_center_altitude,
                "galactic_center_azimuth": galactic_center_azimuth,
            }

            info_text = (
                f"Latitude: {latitude:.4f}\n"
                f"Longitude: {longitude:.4f}\n"
                f"Timezone: {timezone}\n"
                f"Local Time: {local_time}\n\n"
                f"Sidereal Time: {sidereal_time}\n"
                f"Sun Altitude: {sun_altitude:.2f}°\n"
                f"Sun Azimuth: {sun_azimuth:.2f}°\n"
                f"Galactic Center Altitude: {galactic_center_altitude:.2f}°\n"
                f"Galactic Center Azimuth: {galactic_center_azimuth:.2f}°"
            )

            txt = f"Successfully obtained the following local information:\n\n{info_text}"

            popup = newPopup(self.root, name="Local Information", geometry="400x300")
            ttk.Label(popup.win, text="Local Information").pack(pady=10)

            save_btn = ttk.Button(popup.win, text="Save to File", command=lambda: self._save_local_info_to_file(local_info))
            save_btn.pack(pady=(0, 10))

            info_label = ttk.Label(popup.win, text=txt, justify="left")
            info_label.pack(padx=12, pady=12)
            self._append_log("Local information obtained")
        except Exception as error:
            messagebox.showerror("Local Information", f"Failed to obtain local information: {error}")

    def _save_local_info_to_file(self, local_info):
        output_dir = "data/local_info"
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(output_dir, f"local_info_{timestamp}.json")

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(local_info, f, indent=2)

        messagebox.showinfo("Save Local Information", f"Local information saved to\n{output_path}")

    def create_sample_data(self):
        output_dir = "data/sample_data"
        os.makedirs(output_dir, exist_ok=True)

        self.input_window = newPopup(self.root, name="Create Sample Data", geometry="400x200")
        ttk.Label(self.input_window.win, text="This will create a synthetic sample data file with two tones and noise.").pack(pady=(20, 10))
        
        self.sample_rate_entry = ttk.Entry(self.input_window.win)
        self.sample_rate_entry.insert(0, "2048000")
        ttk.Label(self.input_window.win, text="Sample Rate (Hz)").pack(pady=(10, 2))
        self.sample_rate_entry.pack(fill="x", padx=12)

        self.duration_entry = ttk.Entry(self.input_window.win)
        self.duration_entry.insert(0, "5")
        ttk.Label(self.input_window.win, text="Duration (seconds)").pack(pady=(10, 2))
        self.duration_entry.pack(fill="x", padx=12)

        def generate_data():
            try:
                sample_rate_hz = self._validate_range(
                    self._parse_float(self.sample_rate_entry.get(), "Sample Rate"),
                    "Sample Rate",
                    minimum=1_000,
                    maximum=3_200_000,
                )
                duration_s = self._validate_range(
                    self._parse_float(self.duration_entry.get(), "Duration"),
                    "Duration",
                    minimum=0.1,
                    maximum=120,
                )

                num_samples = int(sample_rate_hz * duration_s)
                time_axis = np.arange(num_samples) / sample_rate_hz

                tone1_freq = 100e3
                tone2_freq = 300e3
                tone1 = 0.5 * np.exp(2j * np.pi * tone1_freq * time_axis)
                tone2 = 0.5 * np.exp(2j * np.pi * tone2_freq * time_axis)

                noise = 0.05 * (np.random.randn(num_samples) + 1j * np.random.randn(num_samples))

                samples = tone1 + tone2 + noise

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = os.path.join(output_dir, f"synthetic_sample_{timestamp}.npy")
                np.save(output_path, samples)

                meta_data = {
                    "sample_rate_hz": sample_rate_hz,
                    "center_freq_hz": 100_000_000.0,
                    "duration_s": duration_s,
                    "num_samples": num_samples,
                    "tone1_freq_hz": tone1_freq,
                    "tone2_freq_hz": tone2_freq,
                    "noise_power": 0.05,
                    "created_at": timestamp,
                }

                # Save paired metadata next to the .npy file and keep legacy naming for compatibility.
                meta_output_path = os.path.join(output_dir, f"synthetic_sample_{timestamp}.json")
                with open(meta_output_path, "w", encoding="utf-8") as meta_file:
                    json.dump(meta_data, meta_file, indent=2)

                legacy_meta_output_path = os.path.join(output_dir, f"synthetic_sample_{timestamp}_metadata.json")
                with open(legacy_meta_output_path, "w", encoding="utf-8") as legacy_meta_file:
                    json.dump(meta_data, legacy_meta_file, indent=2)

                self.successwindow = msgPopup(
                    title="Sample Data Created",
                    message=f"Synthetic sample data created: {output_path}"
                )

                self._append_log(f"Synthetic sample data created: {output_path}")
            except ValueError as error:
                self.errorWindow = msgPopup(
                    title="Invalid Input",
                    message=str(error),
                    msgtype="error"
                )
            except Exception as error:
                self.errorWindow = msgPopup(
                    title="Create Sample Data",
                    message=f"Failed to create sample data: {error}",
                    msgtype="error"
                )
        
        generate_btn = ttk.Button(self.input_window.win, text="Generate Sample Data", command=generate_data)
        generate_btn.pack(pady=12)