import tkinter as tk
from tkinter import ttk, messagebox

from logic.settings_manager import merge_settings, save_settings_file


class SettingsWindow:
    def __init__(self, root, settings_path="data/settings.json", settings_snapshot=None, on_save_callback=None):
        self.root = root
        self.settings_path = settings_path
        self.on_save_callback = on_save_callback
        self.settings = merge_settings(settings_snapshot or {})

        self.window = tk.Toplevel(self.root)
        self.window.title("AH-Control | Settings")
        self.window.geometry("560x460")

        self._build_ui()

    def _build_ui(self):
        container = ttk.Frame(self.window, padding=12)
        container.pack(fill="both", expand=True)

        ttk.Label(container, text="Settings", font=("TkDefaultFont", 10, "bold")).pack(anchor="w")
        ttk.Label(
            container,
            text="Adjust visual preferences and advanced SDR behavior.",
            justify="left",
        ).pack(anchor="w", pady=(4, 8))

        notebook = ttk.Notebook(container)
        notebook.pack(fill="both", expand=True)

        style_tab = ttk.Frame(notebook, padding=10)
        advanced_tab = ttk.Frame(notebook, padding=10)
        notebook.add(style_tab, text="Style")
        notebook.add(advanced_tab, text="Advanced")

        self.theme_var = tk.StringVar(value=str(self.settings["theme"]))
        self.font_size_var = tk.IntVar(value=int(self.settings["font_size"]))

        self.sample_rate_var = tk.DoubleVar(value=float(self.settings["capture_default_sample_rate_hz"]))
        self.center_freq_var = tk.DoubleVar(value=float(self.settings["capture_default_center_freq_hz"]))
        self.gain_var = tk.DoubleVar(value=float(self.settings["capture_default_gain_db"]))
        self.record_duration_var = tk.DoubleVar(value=float(self.settings["capture_default_duration_s"]))
        self.capture_cap_var = tk.IntVar(value=int(self.settings["capture_sample_cap"]))

        self.analysis_nfft_var = tk.IntVar(value=int(self.settings["analysis_nfft"]))
        self.analysis_segments_var = tk.IntVar(value=int(self.settings["analysis_max_segments"]))
        self.analysis_preview_var = tk.IntVar(value=int(self.settings["analysis_max_preview_samples"]))

        self.quick_default_duration_var = tk.DoubleVar(value=float(self.settings["quick_check_default_duration_s"]))
        self.quick_max_duration_var = tk.DoubleVar(value=float(self.settings["quick_check_max_duration_s"]))

        self.network_timeout_var = tk.IntVar(value=int(self.settings["network_timeout_s"]))
        self.ip_fallback_var = tk.BooleanVar(value=bool(self.settings["local_info_use_ip_fallback"]))

        self._build_style_tab(style_tab)
        self._build_advanced_tab(advanced_tab)

        actions = ttk.Frame(container)
        actions.pack(fill="x", pady=(10, 0))
        ttk.Button(actions, text="Close", command=self.window.destroy).pack(side="right")
        ttk.Button(actions, text="Save", command=self.on_save).pack(side="right", padx=(0, 6))

    def _row(self, parent, label_text, widget):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(0, 6))
        ttk.Label(row, text=label_text, width=33).pack(side="left")
        widget.pack(side="right", fill="x", expand=True)

    def _build_style_tab(self, parent):
        self._row(parent, "Theme", ttk.Combobox(parent, state="readonly", textvariable=self.theme_var, values=["light", "dark"]))
        self._row(parent, "UI Font Size", ttk.Spinbox(parent, from_=8, to=20, increment=1, textvariable=self.font_size_var, width=8))

    def _build_advanced_tab(self, parent):
        self._row(parent, "Default Sample Rate (Hz)", ttk.Entry(parent, textvariable=self.sample_rate_var))
        self._row(parent, "Default Center Frequency (Hz)", ttk.Entry(parent, textvariable=self.center_freq_var))
        self._row(parent, "Default Gain (dB)", ttk.Entry(parent, textvariable=self.gain_var))
        self._row(parent, "Default Recording Duration (s)", ttk.Entry(parent, textvariable=self.record_duration_var))
        self._row(parent, "Capture Sample Cap", ttk.Entry(parent, textvariable=self.capture_cap_var))

        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=6)

        self._row(parent, "Analysis NFFT", ttk.Entry(parent, textvariable=self.analysis_nfft_var))
        self._row(parent, "Analysis Max Segments", ttk.Entry(parent, textvariable=self.analysis_segments_var))
        self._row(parent, "Analysis Max Preview Samples", ttk.Entry(parent, textvariable=self.analysis_preview_var))

        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=6)

        self._row(parent, "Quick Check Default Duration (s)", ttk.Entry(parent, textvariable=self.quick_default_duration_var))
        self._row(parent, "Quick Check Max Duration (s)", ttk.Entry(parent, textvariable=self.quick_max_duration_var))
        self._row(parent, "Network Timeout (s)", ttk.Entry(parent, textvariable=self.network_timeout_var))

        bool_row = ttk.Frame(parent)
        bool_row.pack(fill="x", pady=(0, 6))
        ttk.Checkbutton(
            bool_row,
            text="Use IP geolocation fallback for Local Information",
            variable=self.ip_fallback_var,
        ).pack(anchor="w")

    def _collect_settings(self):
        return {
            "theme": self.theme_var.get(),
            "font_size": int(self.font_size_var.get()),
            "capture_default_sample_rate_hz": float(self.sample_rate_var.get()),
            "capture_default_center_freq_hz": float(self.center_freq_var.get()),
            "capture_default_gain_db": float(self.gain_var.get()),
            "capture_default_duration_s": float(self.record_duration_var.get()),
            "capture_sample_cap": int(self.capture_cap_var.get()),
            "analysis_nfft": int(self.analysis_nfft_var.get()),
            "analysis_max_segments": int(self.analysis_segments_var.get()),
            "analysis_max_preview_samples": int(self.analysis_preview_var.get()),
            "quick_check_default_duration_s": float(self.quick_default_duration_var.get()),
            "quick_check_max_duration_s": float(self.quick_max_duration_var.get()),
            "network_timeout_s": int(self.network_timeout_var.get()),
            "local_info_use_ip_fallback": bool(self.ip_fallback_var.get()),
            "language": self.settings.get("language", "en"),
            "version": self.settings.get("version", "0.1.0"),
        }

    def on_save(self):
        try:
            new_settings = merge_settings(self._collect_settings())
            saved = save_settings_file(new_settings, settings_path=self.settings_path)
            self.settings = saved
            if self.on_save_callback is not None:
                self.on_save_callback(saved)
            messagebox.showinfo("Settings", "Settings saved")
        except Exception as error:
            messagebox.showerror("Settings", f"Could not save settings:\n{error}")
