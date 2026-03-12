import tkinter as tk
from tkinter import ttk, messagebox

from tools.popup import newPopup
from logic.recording_metadata import save_samples_and_metadata


class DataRecordingWindow:
    def __init__(self, root, detect_devices_fn, read_samples_fn, run_in_background_fn, append_log_fn, settings=None):
        self.root = root
        self.detect_devices_fn = detect_devices_fn
        self.read_samples_fn = read_samples_fn
        self.run_in_background_fn = run_in_background_fn
        self.append_log_fn = append_log_fn
        self.settings = settings or {}

        self.popup = newPopup(self.root, name="Data Recording", geometry="560x430")
        self.devices = []
        self._recording_active = False

        self._build_ui()
        self._refresh_devices()

    def _build_ui(self):
        body = ttk.Frame(self.popup.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)

        ttk.Label(body, text="Data Recording", font=("TkDefaultFont", 10, "bold")).pack(anchor="w")
        ttk.Label(
            body,
            text="Capture and save RTL-SDR IQ samples with metadata.",
            justify="left",
        ).pack(anchor="w", pady=(4, 8))

        row1 = ttk.Frame(body)
        row1.pack(fill="x", pady=(0, 6))
        ttk.Label(row1, text="Device").pack(side="left")
        self.device_combo = ttk.Combobox(row1, state="readonly", width=42)
        self.device_combo.pack(side="left", padx=(8, 8), fill="x", expand=True)
        self.refresh_btn = ttk.Button(row1, text="Refresh", command=self._refresh_devices)
        self.refresh_btn.pack(side="right")

        row2 = ttk.Frame(body)
        row2.pack(fill="x", pady=(0, 4))

        ttk.Label(row2, text="Center (Hz)").pack(side="left")
        self.center_var = tk.StringVar(value=str(int(self.settings.get("capture_default_center_freq_hz", 100000000))))
        ttk.Entry(row2, textvariable=self.center_var, width=14).pack(side="left", padx=(6, 12))

        ttk.Label(row2, text="Rate (Hz)").pack(side="left")
        self.rate_var = tk.StringVar(value=str(int(self.settings.get("capture_default_sample_rate_hz", 2048000))))
        ttk.Entry(row2, textvariable=self.rate_var, width=12).pack(side="left", padx=(6, 12))

        ttk.Label(row2, text="Gain (dB)").pack(side="left")
        self.gain_var = tk.StringVar(value=str(float(self.settings.get("capture_default_gain_db", 20.0))))
        ttk.Entry(row2, textvariable=self.gain_var, width=8).pack(side="left")

        row3 = ttk.Frame(body)
        row3.pack(fill="x", pady=(0, 8))
        ttk.Label(row3, text="Duration (s)").pack(side="left")
        self.duration_var = tk.StringVar(value=str(float(self.settings.get("capture_default_duration_s", 2.0))))
        ttk.Entry(row3, textvariable=self.duration_var, width=8).pack(side="left", padx=(6, 12))

        ttk.Label(row3, text="Tag").pack(side="left")
        self.tag_var = tk.StringVar(value="capture")
        ttk.Entry(row3, textvariable=self.tag_var, width=18).pack(side="left", padx=(6, 0))

        self.estimate_var = tk.StringVar(value="Estimate: --")
        ttk.Label(body, textvariable=self.estimate_var).pack(anchor="w", pady=(2, 0))

        self.status_var = tk.StringVar(value="Status: ready")
        ttk.Label(body, textvariable=self.status_var).pack(anchor="w", pady=(4, 0))

        self.saved_path_var = tk.StringVar(value="Saved file: --")
        ttk.Label(body, textvariable=self.saved_path_var, wraplength=530, justify="left").pack(anchor="w", pady=(2, 0))

        ttk.Separator(body, orient="horizontal").pack(fill="x", pady=10)

        controls = ttk.Frame(body)
        controls.pack(fill="x")

        self.start_btn = ttk.Button(controls, text="Start Recording", command=self._start_recording)
        self.start_btn.pack(side="right")
        ttk.Button(controls, text="Close", command=self.popup.win.destroy).pack(side="right", padx=(0, 6))

        for var in [self.rate_var, self.duration_var]:
            var.trace_add("write", lambda *_: self._update_estimate())
        self._update_estimate()

    def _refresh_devices(self):
        self.devices = self.detect_devices_fn() or []

        if not self.devices:
            self.device_combo["values"] = ["No device detected"]
            self.device_combo.current(0)
            self.status_var.set("Status: no RTL-SDR devices detected")
            return

        labels = [device["label"] for device in self.devices]
        self.device_combo["values"] = labels
        self.device_combo.current(0)
        self.status_var.set(f"Status: {len(self.devices)} device(s) available")

    def _update_estimate(self):
        try:
            sample_rate_hz = float(self.rate_var.get().strip())
            duration_s = float(self.duration_var.get().strip())
            if sample_rate_hz <= 0 or duration_s <= 0:
                raise ValueError
            estimated_num_samples = int(sample_rate_hz * duration_s)
            estimated_mb = (estimated_num_samples * 16) / (1024.0 * 1024.0)
            self.estimate_var.set(f"Estimate: {estimated_num_samples:,} samples | {estimated_mb:.1f} MB")
        except Exception:
            self.estimate_var.set("Estimate: invalid sample rate/duration")

    def _parse_inputs(self):
        selected_label = self.device_combo.get().strip()
        selected_device = next((d for d in self.devices if d["label"] == selected_label), None)
        if selected_device is None:
            raise ValueError("Please select a valid RTL-SDR device")

        center_freq_hz = float(self.center_var.get().strip())
        sample_rate_hz = float(self.rate_var.get().strip())
        gain_db = float(self.gain_var.get().strip())
        duration_s = float(self.duration_var.get().strip())

        if center_freq_hz < 1_000 or center_freq_hz > 3_000_000_000:
            raise ValueError("Center frequency must be between 1,000 and 3,000,000,000 Hz")
        if sample_rate_hz < 1_000 or sample_rate_hz > 3_200_000:
            raise ValueError("Sample rate must be between 1,000 and 3,200,000 Hz")
        if gain_db < -10 or gain_db > 60:
            raise ValueError("Gain must be between -10 and 60 dB")
        if duration_s < 0.1 or duration_s > 120:
            raise ValueError("Duration must be between 0.1 and 120 seconds")

        tag = "".join(ch if (ch.isalnum() or ch in "_-" ) else "_" for ch in self.tag_var.get().strip())
        tag = tag.strip("_") or "capture"

        requested_samples = int(sample_rate_hz * duration_s)
        sample_cap = int(self.settings.get("capture_sample_cap", 2_500_000))
        capped_samples = min(requested_samples, sample_cap)

        return {
            "device": selected_device,
            "center_freq_hz": center_freq_hz,
            "sample_rate_hz": sample_rate_hz,
            "gain_db": gain_db,
            "duration_s": duration_s,
            "tag": tag,
            "requested_samples": requested_samples,
            "num_samples": capped_samples,
        }

    def _start_recording(self):
        if self._recording_active:
            return

        try:
            config = self._parse_inputs()
        except ValueError as error:
            messagebox.showerror("Data Recording", str(error))
            return

        if config["num_samples"] < config["requested_samples"]:
            messagebox.showwarning(
                "Data Recording",
                "Sample request is large. Capture will be limited to 2,500,000 samples for responsiveness.",
            )

        self._recording_active = True
        self.start_btn.state(["disabled"])
        self.refresh_btn.state(["disabled"])
        self.status_var.set("Status: running capture...")

        def do_recording():
            samples = self.read_samples_fn(
                device_index=config["device"]["index"],
                center_freq_hz=config["center_freq_hz"],
                sample_rate_hz=config["sample_rate_hz"],
                gain_db=config["gain_db"],
                num_samples=config["num_samples"],
            )

            result = save_samples_and_metadata(
                samples=samples,
                output_dir="data/recordings",
                tag=config["tag"],
                device_index=config["device"]["index"],
                serial=config["device"].get("serial", "unknown"),
                center_freq_hz=config["center_freq_hz"],
                sample_rate_hz=config["sample_rate_hz"],
                gain_db=config["gain_db"],
                duration_s=config["duration_s"],
                num_samples=config["num_samples"],
            )
            return result

        def on_success(result):
            saved_path = result["samples_path"]
            self.status_var.set("Status: capture complete")
            self.saved_path_var.set(f"Saved file: {saved_path}")
            self.append_log_fn(f"Recording saved ({result['num_samples']} samples)")
            messagebox.showinfo("Data Recording", f"Recording saved to\n{saved_path}")

        def on_error(error):
            self.status_var.set("Status: capture failed")
            messagebox.showerror("Data Recording", f"Recording failed:\n{error}")
            self.append_log_fn("Recording failed")

        def on_finally():
            self._recording_active = False
            self.start_btn.state(["!disabled"])
            self.refresh_btn.state(["!disabled"])

        self.run_in_background_fn(do_recording, on_success=on_success, on_error=on_error, on_finally=on_finally)
