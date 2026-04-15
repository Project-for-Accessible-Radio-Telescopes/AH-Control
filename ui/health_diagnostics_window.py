import tkinter as tk
from tkinter import ttk, messagebox

from tools.popup import newPopup
from logic.health_diagnostics import collect_system_health, analyze_capture_health


class HealthDiagnosticsWindow:
    def __init__(self, root, detect_devices_fn, read_samples_fn, run_in_background_fn, append_log_fn, settings=None):
        self.root = root
        self.detect_devices_fn = detect_devices_fn
        self.read_samples_fn = read_samples_fn
        self.run_in_background_fn = run_in_background_fn
        self.append_log_fn = append_log_fn
        self.settings = settings or {}

        self.popup = newPopup(self.root, name="Health Diagnostics", geometry="560x460")
        self._system_after_id = None
        self._test_running = False

        self._build_ui()
        self._refresh_devices()
        self._refresh_system_health()

        self.popup.win.protocol("WM_DELETE_WINDOW", self._close)

    def _build_ui(self):
        body = ttk.Frame(self.popup.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)

        ttk.Label(body, text="Health Diagnostics", font=("TkDefaultFont", 10, "bold")).pack(anchor="w")
        ttk.Label(
            body,
            text="Monitor system load and run a quick RTL-SDR capture health check.",
            justify="left",
        ).pack(anchor="w", pady=(4, 8))

        ttk.Label(body, text="System Health", font=("TkDefaultFont", 10, "bold")).pack(anchor="w")

        self.cpu_var = tk.StringVar(value="CPU: --")
        self.mem_var = tk.StringVar(value="Memory: --")
        self.proc_mem_var = tk.StringVar(value="Process RSS: --")
        self.load_var = tk.StringVar(value="Load(1m): --")

        ttk.Label(body, textvariable=self.cpu_var).pack(anchor="w", pady=(4, 0))
        ttk.Label(body, textvariable=self.mem_var).pack(anchor="w")
        ttk.Label(body, textvariable=self.proc_mem_var).pack(anchor="w")
        ttk.Label(body, textvariable=self.load_var).pack(anchor="w")

        ttk.Separator(body, orient="horizontal").pack(fill="x", pady=10)

        ttk.Label(body, text="SDR Quick Health Check", font=("TkDefaultFont", 10, "bold")).pack(anchor="w")

        row1 = ttk.Frame(body)
        row1.pack(fill="x", pady=(6, 4))
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
        ttk.Entry(row2, textvariable=self.gain_var, width=8).pack(side="left", padx=(6, 0))

        row3 = ttk.Frame(body)
        row3.pack(fill="x", pady=(0, 8))
        ttk.Label(row3, text="Duration (s)").pack(side="left")
        self.duration_var = tk.StringVar(value=str(float(self.settings.get("quick_check_default_duration_s", 0.35))))
        ttk.Entry(row3, textvariable=self.duration_var, width=8).pack(side="left", padx=(6, 12))

        self.run_btn = ttk.Button(row3, text="Run Quick Check", command=self._run_quick_check)
        self.run_btn.pack(side="left")

        self.status_var = tk.StringVar(value="Status: ready")
        ttk.Label(body, textvariable=self.status_var).pack(anchor="w", pady=(4, 0))

        self.capture_var = tk.StringVar(value="Capture: not run")
        self.clip_var = tk.StringVar(value="Clipping: --")
        self.drop_var = tk.StringVar(value="Dropped samples: --")
        self.max_abs_var = tk.StringVar(value="Max amplitude: --")
        self.dc_var = tk.StringVar(value="DC offset: --")
        self.warn_var = tk.StringVar(value="Warnings: none")

        ttk.Label(body, textvariable=self.capture_var).pack(anchor="w", pady=(6, 0))
        ttk.Label(body, textvariable=self.clip_var).pack(anchor="w")
        ttk.Label(body, textvariable=self.drop_var).pack(anchor="w")
        ttk.Label(body, textvariable=self.max_abs_var).pack(anchor="w")
        ttk.Label(body, textvariable=self.dc_var).pack(anchor="w")
        ttk.Label(body, textvariable=self.warn_var, wraplength=520).pack(anchor="w", pady=(2, 0))

    def _refresh_devices(self):
        devices = self.detect_devices_fn()
        self.devices = devices

        if not devices:
            self.device_combo["values"] = ["No device detected"]
            self.device_combo.current(0)
            self.status_var.set("Status: no RTL-SDR devices detected")
            return

        labels = [device["label"] for device in devices]
        self.device_combo["values"] = labels
        self.device_combo.current(0)
        self.status_var.set(f"Status: {len(devices)} device(s) available")

    def _refresh_system_health(self):
        health = collect_system_health()

        cpu_percent = health.get("cpu_percent")
        memory_percent = health.get("memory_percent")
        memory_used_mb = health.get("memory_used_mb")
        memory_total_mb = health.get("memory_total_mb")
        process_mem_mb = health.get("process_mem_mb")
        load_1m = health.get("load_1m")

        self.cpu_var.set(f"CPU: {cpu_percent:.1f}%" if cpu_percent is not None else "CPU: unavailable")
        if memory_percent is not None and memory_used_mb is not None and memory_total_mb is not None:
            self.mem_var.set(f"Memory: {memory_percent:.1f}% ({memory_used_mb:.0f}/{memory_total_mb:.0f} MB)")
        else:
            self.mem_var.set("Memory: unavailable")

        self.proc_mem_var.set(
            f"Process RSS: {process_mem_mb:.1f} MB" if process_mem_mb is not None else "Process RSS: unavailable"
        )
        self.load_var.set(f"Load(1m): {load_1m:.2f}" if load_1m is not None else "Load(1m): unavailable")

        self._system_after_id = self.popup.win.after(2000, self._refresh_system_health)

    def _run_quick_check(self):
        if self._test_running:
            return

        selected_label = self.device_combo.get().strip()
        selected_device = next((device for device in getattr(self, "devices", []) if device["label"] == selected_label), None)
        if selected_device is None:
            messagebox.showerror("Health Diagnostics", "No SDR device selected.")
            return

        try:
            center_freq_hz = float(self.center_var.get().strip())
            sample_rate_hz = float(self.rate_var.get().strip())
            gain_db = float(self.gain_var.get().strip())
            duration_s = float(self.duration_var.get().strip())

            if center_freq_hz < 1_000:
                raise ValueError("Center frequency out of range")

            max_center_freq_hz = float(self.settings.get("rtlsdr_max_center_freq_hz", 1_766_000_000.0))
            if center_freq_hz > max_center_freq_hz:
                raise ValueError(
                    f"Center frequency must be <= {int(max_center_freq_hz)} Hz for RTL-SDR (about 1.7 GHz)"
                )

            if sample_rate_hz < 1_000 or sample_rate_hz > 3_200_000:
                raise ValueError("Sample rate out of range")
            max_duration = float(self.settings.get("quick_check_max_duration_s", 2.0))
            if duration_s <= 0.0 or duration_s > max_duration:
                raise ValueError(f"Duration must be > 0 and <= {max_duration}")
        except ValueError as error:
            messagebox.showerror("Health Diagnostics", f"Invalid input: {error}")
            return

        requested_samples = int(sample_rate_hz * duration_s)
        self._test_running = True
        self.run_btn.state(["disabled"])
        self.status_var.set("Status: running quick check...")

        def do_test():
            samples = self.read_samples_fn(
                device_index=selected_device["index"],
                center_freq_hz=center_freq_hz,
                sample_rate_hz=sample_rate_hz,
                gain_db=gain_db,
                num_samples=requested_samples,
            )
            return analyze_capture_health(samples=samples, requested_samples=requested_samples)

        def on_success(result):
            self.capture_var.set(
                f"Capture: {result['status']} ({result['actual_samples']}/{result['requested_samples']} samples)"
            )
            self.clip_var.set(f"Clipping: {result['clipping_ratio'] * 100.0:.2f}%")
            self.drop_var.set(
                f"Dropped samples: {result['dropped_samples']} ({result['drop_ratio'] * 100.0:.3f}%)"
            )
            self.max_abs_var.set(f"Max amplitude: {result['max_abs']:.3f}")
            self.dc_var.set(f"DC offset: {result['dc_offset']:.4f}")

            warnings = result["warnings"]
            self.warn_var.set("Warnings: " + ("; ".join(warnings) if warnings else "none"))
            self.status_var.set("Status: quick check complete")

            self.append_log_fn(
                "Health quick check finished "
                f"(clip={result['clipping_ratio'] * 100.0:.2f}%, drop={result['drop_ratio'] * 100.0:.3f}%)"
            )

        def on_error(error):
            self.status_var.set("Status: quick check failed")
            self.warn_var.set(f"Warnings: capture failed ({error})")
            messagebox.showerror("Health Diagnostics", f"Quick check failed: {error}")
            self.append_log_fn("Health quick check failed")

        def on_finally():
            self._test_running = False
            self.run_btn.state(["!disabled"])

        self.run_in_background_fn(do_test, on_success=on_success, on_error=on_error, on_finally=on_finally)

    def _close(self):
        if self._system_after_id is not None:
            try:
                self.popup.win.after_cancel(self._system_after_id)
            except Exception:
                pass
            self._system_after_id = None
        self.popup.win.destroy()
