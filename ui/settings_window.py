# The Settings Window allows the user to change the settings, saved in data/settings.json

import json
import os

class SettingsWindow:
    def __init__(self, settings_path="data/settings.json"):
        self.settings_path = settings_path
        self.settings = self.load_settings()

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