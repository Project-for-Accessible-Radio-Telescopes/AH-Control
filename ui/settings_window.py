# The Settings Window allows the user to change the settings, saved in data/settings.json

import json
import os
import tkinter as tk
from tkinter import ttk

class SettingsWindow:
    def __init__(self, settings_path="data/settings.json"):
        self.settings_path = settings_path
        self.settings = self.load_settings()

        self.window = tk.Toplevel()
        self.window.title("Settings")
        self.window.geometry("400x300")
        self.create_widgets()
        
    def create_widgets(self):
        # Sample Rate
        ttk.Label(self.window, text="Sample Rate (Hz):").pack(pady=5)
        self.sample_rate_var = tk.DoubleVar(value=self.settings["sample_rate"])
        ttk.Entry(self.window, textvariable=self.sample_rate_var).pack(pady=5)

        # Center Frequency
        ttk.Label(self.window, text="Center Frequency (Hz):").pack(pady=5)
        self.center_freq_var = tk.DoubleVar(value=self.settings["center_freq"])
        ttk.Entry(self.window, textvariable=self.center_freq_var).pack(pady=5)

        # Gain
        ttk.Label(self.window, text="Gain (dB):").pack(pady=5)
        self.gain_var = tk.DoubleVar(value=self.settings["gain"])
        ttk.Entry(self.window, textvariable=self.gain_var).pack(pady=5)

        # Record Duration
        ttk.Label(self.window, text="Record Duration (s):").pack(pady=5)
        self.record_duration_var = tk.DoubleVar(value=self.settings["record_duration"])
        ttk.Entry(self.window, textvariable=self.record_duration_var).pack(pady=5)

        # Save Button
        ttk.Button(self.window, text="Save", command=self.on_save).pack(pady=20)

    def load_settings(self):
        if os.path.exists(self.settings_path):
            with open(self.settings_path, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            return {
                "sample_rate": 2.4e6,
                "center_freq": 100e6,
                "gain": 40,
                "record_duration": 10,
            }

    def save_settings(self):
        with open(self.settings_path, "w", encoding="utf-8") as f:
            json.dump(self.settings, f, indent=2)

    def update_setting(self, key, value):
        if key in self.settings:
            self.settings[key] = value
            self.save_settings()
        else:
            raise KeyError(f"Setting '{key}' not found in settings.")