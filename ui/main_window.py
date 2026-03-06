import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from tkinter import filedialog
import json
import os
import ctypes
from datetime import datetime
from tools.graphs.graphing import plot_basic_graph
from ui.settings_window import SettingsWindow
import webbrowser
from logic.file_ext import build_session_payload, write_ahf_file, read_ahf_file

import numpy as np
from logic.sdr_processing import process_all_recordings

from tools.cmenu import CustomMenu
from tools import cbuttons
from tools.spreadsheet import SpreadsheetWindow
from tools.popup import newPopup
from tools.standardpopup import msgPopup

from logic.local_info import obtain_local_info, compute_sidereal_time_and_hour_angle

class MainWindow:
    def __init__(self, root):
        self.root = root
        self.root.geometry("500x300")
        self._rtlsdr_cls = None
        self._rtlsdr_import_error = None
        self._spreadsheet_windows = []

        # Use CustomMenu manager for popup menus
        self.menu = CustomMenu(self.root)

        settings = self._read_settings()

        self.root.title(f"AH-Control v{settings.get('version')}")

        self._create_menu_bar(theme=settings.get("theme", "light"))
        self._create_content(theme=settings.get("theme", "light"))
        self._bind_log_clear_handlers()

    def _bind_log_clear_handlers(self):
        self.root.bind_class("Button", "<Button-1>", self._clear_log_selection, add="+")
        self.root.bind_class("TButton", "<Button-1>", self._clear_log_selection, add="+")

    def _clear_log_selection(self, _event=None):
        if not hasattr(self, "log_text"):
            return
        try:
            self.log_text.tag_remove("sel", "1.0", "end")
        except Exception:
            return

    def _preload_rtlsdr_native_libraries(self):
        if os.name != "posix":
            return

        candidates = [
            "/opt/homebrew/opt/libusb/lib/libusb-1.0.0.dylib",
            "/opt/homebrew/opt/libusb/lib/libusb-1.0.dylib",
            "/usr/local/opt/libusb/lib/libusb-1.0.0.dylib",
            "/usr/local/opt/libusb/lib/libusb-1.0.dylib",
            "/opt/homebrew/lib/libusb-1.0.0.dylib",
            "/opt/homebrew/lib/libusb-1.0.dylib",
            "/usr/local/lib/libusb-1.0.0.dylib",
            "/usr/local/lib/libusb-1.0.dylib",
            "/opt/homebrew/lib/librtlsdr.dylib",
            "/usr/local/lib/librtlsdr.dylib",
        ]

        for path in candidates:
            if not os.path.exists(path):
                continue
            try:
                ctypes.CDLL(path, mode=ctypes.RTLD_GLOBAL)
            except Exception:
                continue

    def _get_rtlsdr_class(self):
        if self._rtlsdr_cls is not None:
            return self._rtlsdr_cls

        try:
            self._preload_rtlsdr_native_libraries()
            from rtlsdr import RtlSdr as rtl_sdr_class

            self._rtlsdr_cls = rtl_sdr_class
            self._rtlsdr_import_error = None
            return self._rtlsdr_cls
        except Exception as error:
            self._rtlsdr_import_error = error
            return None

    def _show_rtlsdr_dependency_error(self):
        error_text = str(self._rtlsdr_import_error) if self._rtlsdr_import_error else "RTL-SDR dependency unavailable"
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

        # Full-width menu bar background
        self.menu_bar = tk.Frame(self.root, bg=menu_bg, height=24)
        self.menu_bar.pack(fill="x")

        # Divider under the menu bar to create a crisp bottom border
        self._menu_divider = tk.Frame(self.root, height=1, bg=menu_fg)
        self._menu_divider.pack(fill="x")
        # Create menu buttons using centralized helper in `tools.cbuttons`
        self.file_btn = cbuttons.make_button(self.menu_bar, text="File")
        self.file_btn.pack(side="left", padx=4)
        self.file_btn.configure(command=lambda: self.menu.show_menu(self.file_btn, [
            ("New Project", self.new_project),
            ("Save Project", self.save_project),
            ("Open Project", self.open_project),
            ("New Spreadsheet", self.on_new),
            ("Open Spreadsheet", self.on_open),
            ("Exit", self.root.quit),
        ]))

        self.help_btn = cbuttons.make_button(self.menu_bar, text="Help")
        self.help_btn.pack(side="left")
        self.help_btn.configure(command=lambda: self.menu.show_menu(self.help_btn, [
            ("About", self.on_about),
            ("Documentation", lambda: webbrowser.open("https://parttelescopes.web.app/documentation.html")),
        ]))

        self.tools_btn = cbuttons.make_button(self.menu_bar, text="Tools")
        self.tools_btn.pack(side="left", padx=4)
        self.tools_btn.configure(command=lambda: self.menu.show_menu(self.tools_btn, [
            ("Calibration", self.calibration_tool),
            ("Settings", self.settings_tool),
            ("Local Information", lambda: self.obtain_local_info()),
            ("Create Sample Graph", lambda: plot_basic_graph(self.root, x=[1, 2, 3], y=[1, 4, 9], title="Sample Graph", xlabel="X", ylabel="Y")),
        ]))

        self.record_btn = cbuttons.make_button(self.menu_bar, text="Record")
        self.record_btn.pack(side="left")
        self.record_btn.configure(command=lambda: self.menu.show_menu(self.record_btn, [
            ("Begin Data Recording", self.start_recording_menu),
            ("Process Recordings", self.process_recordings_action),
            ("Info", lambda: msgPopup("Recording Tools", "Use the 'Begin Data Recording' option to capture data from a connected RTL-SDR device. Use the 'Process Recordings' option to process all existing recordings in the data/recordings directory and generate spectrograms and metadata in the processed subdirectory.")),
        ]))

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
        )
        self.log_scrollbar = ttk.Scrollbar(self.log_container, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=self.log_scrollbar.set)
        self.log_text.tag_configure("log_entry", spacing1=2, spacing2=1, spacing3=10)

        self.log_text.pack(side="left", fill="both", expand=True)
        self.log_scrollbar.pack(side="right", fill="y")

        self.log_text.configure(state="disabled")
        self.log_text.configure(font=("TkDefaultFont", 10), spacing1=2, spacing3=2)

    def _append_log(self, text):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{text}\n", "log_entry")
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
        with open("data/settings.json", "w", encoding="utf-8") as settings_file:
            json.dump(settings, settings_file, indent=2)

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

            for csv_path in payload.get("open_spreadsheets", []):
                if not isinstance(csv_path, str) or not csv_path.strip():
                    continue
                if os.path.exists(csv_path):
                    sheet = SpreadsheetWindow(self.root, file_path=csv_path)
                    self._spreadsheet_windows.append(sheet)
                else:
                    self._append_log(f"Missing spreadsheet in project: {csv_path}")

            self._clear_log()
            for line in payload.get("log_entries", []):
                if isinstance(line, str):
                    self._append_log(line)

            self._append_log(f"Project opened: {project_path}")
            messagebox.showinfo("Open Project", f"Project loaded from\n{project_path}")
        except Exception as error:
            messagebox.showerror("Open Project", f"Could not open project:\n{error}")

    def on_about(self):
        settings = self._read_settings()
        version = settings.get("version", "0.1.0")
        self._append_log(f"Welcome to AH Control v{version}! This application is intended to be a simple data collection and analysis tool to complement the PART Access Horizon telescope, but it can be used with any RTL-SDR device. To get started, connect your RTL-SDR that is linked to your antenna to this device and use the 'Record' menu to capture data. Use the 'Tools' menu for calibration and settings. If you want to load an existing project, or create a new one to save your data, click on the 'File' menu. Settings can be changed under tools. For further documentation, visit the Help menu. Happy exploring! - The PART Team")

    def _detect_rtl_sdr_devices(self):
        rtlsdr_class = self._get_rtlsdr_class()
        if rtlsdr_class is None:
            return []

        devices = []
        serials = []

        if hasattr(rtlsdr_class, "get_device_serial_addresses"):
            try:
                serials = rtlsdr_class.get_device_serial_addresses() or []
            except Exception:
                serials = []

        if serials:
            for index_guess, serial in enumerate(serials):
                index = index_guess
                if hasattr(rtlsdr_class, "get_device_index_by_serial"):
                    try:
                        index = rtlsdr_class.get_device_index_by_serial(serial)
                    except Exception:
                        index = index_guess
                devices.append({
                    "index": int(index),
                    "serial": str(serial),
                    "label": f"Device {index} (serial: {serial})",
                })
            return devices

        if hasattr(rtlsdr_class, "get_device_count"):
            try:
                count = int(rtlsdr_class.get_device_count())
                for index in range(count):
                    devices.append({
                        "index": index,
                        "serial": "unknown",
                        "label": f"Device {index}",
                    })
            except Exception:
                return []

        return devices

    def _build_device_selector(self, parent):
        devices = self._detect_rtl_sdr_devices()
        if not devices:
            return devices, None

        labels = [device["label"] for device in devices]
        selector = ttk.Combobox(parent, values=labels, state="readonly")
        selector.current(0)
        return devices, selector

    def _read_sdr_samples(self, device_index, center_freq_hz, sample_rate_hz, gain_db, num_samples):
        rtlsdr_class = self._get_rtlsdr_class()
        if rtlsdr_class is None:
            raise RuntimeError("RTL-SDR library is unavailable")

        sdr = rtlsdr_class(device_index=device_index)
        try:
            sdr.sample_rate = sample_rate_hz
            sdr.center_freq = center_freq_hz
            sdr.gain = gain_db
            samples = sdr.read_samples(num_samples)
            return samples
        finally:
            sdr.close()

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

        def run_calibration():
            selected_label = device_selector.get()
            selected_device = next((d for d in devices if d["label"] == selected_label), None)
            if selected_device is None:
                messagebox.showerror("Calibration", "Please select a device.")
                return

            try:
                center_freq_hz = float(center_freq_entry.get().strip())
                sample_rate_hz = float(sample_rate_entry.get().strip())
                gain_db = float(gain_entry.get().strip())
                samples = self._read_sdr_samples(
                    device_index=selected_device["index"],
                    center_freq_hz=center_freq_hz,
                    sample_rate_hz=sample_rate_hz,
                    gain_db=gain_db,
                    num_samples=262144,
                )
                avg_power = float(np.mean(np.abs(samples) ** 2))
                status_text = f"Calibration OK | Avg power: {avg_power:.6f}"
                status_label.config(text=status_text)
                self._append_log(f"Calibration complete: device {selected_device['index']}")
            except ValueError:
                messagebox.showerror("Calibration", "Invalid numeric parameters.")
            except Exception as error:
                messagebox.showerror("Calibration", f"Calibration failed: {error}")
                status_label.config(text="Calibration failed")
                self._append_log("Calibration failed")

        ttk.Button(popup.win, text="Run Calibration", command=run_calibration).pack(pady=(2, 12))
        self._append_log("Calibration tool opened")

    def start_recording_menu(self):
        if self._get_rtlsdr_class() is None:
            self._show_rtlsdr_dependency_error()
            self._append_log("Recording unavailable: missing RTL-SDR dependency")
            return

        popup = newPopup(self.root, name="Start Recording", geometry="520x430")

        ttk.Label(popup.win, text="Detected RTL-SDR Devices").pack(pady=(10, 2))
        devices, device_selector = self._build_device_selector(popup.win)

        if device_selector is None:
            ttk.Label(popup.win, text="No RTL-SDR device detected.").pack(pady=6)
            ttk.Button(
                popup.win,
                text="Retry Detection",
                command= lambda: (popup.win.destroy(), self.start_recording_menu()),
            ).pack(pady=8)
            self._append_log("Recording: no SDR device detected")
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

        ttk.Label(popup.win, text="Duration (seconds)").pack(pady=(8, 2))
        duration_entry = ttk.Entry(popup.win)
        duration_entry.insert(0, "2")
        duration_entry.pack(fill="x", padx=12)

        ttk.Label(popup.win, text="Output Tag (optional)").pack(pady=(8, 2))
        output_tag_entry = ttk.Entry(popup.win)
        output_tag_entry.insert(0, "capture")
        output_tag_entry.pack(fill="x", padx=12)

        status_label = ttk.Label(popup.win, text="Ready")
        status_label.pack(pady=10)

        def begin_recording():
            selected_label = device_selector.get()
            selected_device = next((d for d in devices if d["label"] == selected_label), None)
            if selected_device is None:
                messagebox.showerror("Record", "Please select a device.")
                return

            try:
                center_freq_hz = float(center_freq_entry.get().strip())
                sample_rate_hz = float(sample_rate_entry.get().strip())
                gain_db = float(gain_entry.get().strip())
                duration_s = float(duration_entry.get().strip())
                if duration_s <= 0:
                    raise ValueError("Duration must be greater than 0")

                num_samples = int(sample_rate_hz * duration_s)
                if num_samples > 2_500_000:
                    messagebox.showwarning(
                        "Record",
                        "Sample size was large. Limited capture to 2,500,000 samples for responsiveness.",
                    )
                    num_samples = 2_500_000

                samples = self._read_sdr_samples(
                    device_index=selected_device["index"],
                    center_freq_hz=center_freq_hz,
                    sample_rate_hz=sample_rate_hz,
                    gain_db=gain_db,
                    num_samples=num_samples,
                )

                output_dir = os.path.join("data", "recordings")
                os.makedirs(output_dir, exist_ok=True)

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                tag = output_tag_entry.get().strip() or "capture"
                base_name = f"{tag}_{timestamp}_dev{selected_device['index']}"

                samples_path = os.path.join(output_dir, f"{base_name}.npy")
                metadata_path = os.path.join(output_dir, f"{base_name}.json")

                np.save(samples_path, samples)
                metadata = {
                    "device_index": selected_device["index"],
                    "serial": selected_device["serial"],
                    "center_freq_hz": center_freq_hz,
                    "sample_rate_hz": sample_rate_hz,
                    "gain_db": gain_db,
                    "duration_s": duration_s,
                    "num_samples": int(num_samples),
                    "saved_samples_file": samples_path,
                    "created_at": timestamp,
                }
                with open(metadata_path, "w", encoding="utf-8") as metadata_file:
                    json.dump(metadata, metadata_file, indent=2)

                status_label.config(text=f"Saved: {samples_path}")
                self._append_log(f"Recording saved ({num_samples} samples)")
                messagebox.showinfo("Record", f"Recording saved to\n{samples_path}")
            except ValueError:
                messagebox.showerror("Record", "Invalid numeric parameters.")
            except Exception as error:
                messagebox.showerror("Record", f"Recording failed: {error}")
                status_label.config(text="Recording failed")
                self._append_log("Recording failed")

        controls = ttk.Frame(popup.win)
        controls.pack(pady=(2, 12))

        ttk.Button(controls, text="Refresh Devices", command=self.start_recording_menu).pack(side="left", padx=6)
        ttk.Button(controls, text="Start Recording", command=begin_recording).pack(side="left", padx=6)

        self._append_log("Recording setup opened")

    def settings_tool(self):
        popup = SettingsWindow()

        popup_window = newPopup(self.root, name="Settings", geometry="400x300")
        ttk.Label(popup_window.win, text="Settings").pack(pady=10)

        self._append_log("Settings opened")

    def process_recordings_action(self):
        try:
            result = process_all_recordings(recordings_dir="data/recordings", output_subdir="processed", nfft=4096)

            processed_count = len(result.get("processed", []))
            skipped_count = len(result.get("skipped", []))
            error_count = len(result.get("errors", []))
            output_dir = result.get("output_dir", "data/recordings/processed")

            summary_lines = [
                f"Processed: {processed_count}",
                f"Skipped: {skipped_count}",
                f"Errors: {error_count}",
                f"Output: {output_dir}",
            ]

            if error_count > 0:
                summary_lines.append("")
                summary_lines.append("First error:")
                summary_lines.append(result["errors"][0])

            messagebox.showinfo("Process Recordings", "\n".join(summary_lines))
            self._append_log(f"Processed recordings: {processed_count}")
        except Exception as error:
            messagebox.showerror("Process Recordings", f"Processing failed: {error}")
            self._append_log("Processing failed")
    
    def _read_settings(self):
        try:
            with open("data/settings.json", "r") as f:
                settings = json.load(f)
                return settings
        except Exception as e:
            print(f"Error reading settings: {e}")
            return {}
        
    def obtain_local_info(self):
        try:
            local_info = obtain_local_info()
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