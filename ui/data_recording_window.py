import csv
import json
import os
from datetime import datetime

import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from tools.popup import newPopup


class DataRecordingWindow:
	def __init__(
		self,
		root,
		run_in_background_fn,
		append_log_fn,
		settings=None,
		initial_config=None,
		on_saved_callback=None,
	):
		self.root = root
		self.run_in_background_fn = run_in_background_fn
		self.append_log_fn = append_log_fn
		self.settings = settings or {}
		self.initial_config = initial_config or {}
		self.on_saved_callback = on_saved_callback

		self.popup = newPopup(self.root, name="Data Recording", geometry="980x660")
		self._scan_running = False
		self._last_scan_result = None

		self._build_ui()
		self.popup.win.protocol("WM_DELETE_WINDOW", self._close)

	def _build_ui(self):
		container = ttk.Frame(self.popup.win)
		container.pack(fill="both", expand=True, padx=12, pady=10)

		ttk.Label(container, text="Frequency Scan Recording", font=("TkDefaultFont", 10, "bold")).pack(anchor="w")
		ttk.Label(
			container,
			text="Scan a frequency range, view the power plot, and save the scan data to disk.",
			justify="left",
		).pack(anchor="w", pady=(4, 8))

		form = ttk.Frame(container)
		form.pack(fill="x", pady=(0, 8))

		default_center = float(self.settings.get("capture_default_center_freq_hz", 1_450_000_000.0))
		start_default = float(self.initial_config.get("start_freq_hz", max(1_000.0, default_center - 250_000_000.0)))
		end_default = float(self.initial_config.get("end_freq_hz", default_center + 250_000_000.0))

		self.start_freq_var = tk.StringVar(value=str(int(start_default)))
		self.end_freq_var = tk.StringVar(value=str(int(end_default)))
		self.points_var = tk.StringVar(value=str(int(self.initial_config.get("num_points", 100))))
		self.sample_rate_var = tk.StringVar(value=str(float(self.initial_config.get("sample_rate_hz", 2_400_000.0))))
		self.samples_per_point_var = tk.StringVar(value=str(int(self.initial_config.get("samples_per_point", 256 * 1024))))
		self.device_index_var = tk.StringVar(value=str(int(self.initial_config.get("device_index", 0))))
		self.gain_var = tk.StringVar(value=str(self.initial_config.get("gain", "auto")))
		self.source_var = tk.StringVar(value=str(self.initial_config.get("source", "RTL-SDR")))

		row1 = ttk.Frame(form)
		row1.pack(fill="x", pady=(0, 4))
		ttk.Label(row1, text="Start Freq (Hz)", width=16).pack(side="left")
		ttk.Entry(row1, textvariable=self.start_freq_var, width=16).pack(side="left", padx=(0, 10))
		ttk.Label(row1, text="End Freq (Hz)", width=14).pack(side="left")
		ttk.Entry(row1, textvariable=self.end_freq_var, width=16).pack(side="left", padx=(0, 10))
		ttk.Label(row1, text="Points", width=8).pack(side="left")
		ttk.Entry(row1, textvariable=self.points_var, width=8).pack(side="left")

		row2 = ttk.Frame(form)
		row2.pack(fill="x", pady=(0, 4))
		ttk.Label(row2, text="Sample Rate (Hz)", width=16).pack(side="left")
		ttk.Entry(row2, textvariable=self.sample_rate_var, width=16).pack(side="left", padx=(0, 10))
		ttk.Label(row2, text="Samples/Point", width=14).pack(side="left")
		ttk.Entry(row2, textvariable=self.samples_per_point_var, width=16).pack(side="left", padx=(0, 10))
		ttk.Label(row2, text="Gain", width=8).pack(side="left")
		ttk.Entry(row2, textvariable=self.gain_var, width=8).pack(side="left")

		row3 = ttk.Frame(form)
		row3.pack(fill="x", pady=(0, 4))
		ttk.Label(row3, text="Source", width=16).pack(side="left")
		source_combo = ttk.Combobox(
			row3,
			state="readonly",
			textvariable=self.source_var,
			values=["RTL-SDR", "Virtual"],
			width=13,
		)
		source_combo.pack(side="left", padx=(0, 10))
		ttk.Label(row3, text="Device Index", width=14).pack(side="left")
		ttk.Entry(row3, textvariable=self.device_index_var, width=8).pack(side="left", padx=(0, 10))

		self.status_var = tk.StringVar(value="Status: ready")
		ttk.Label(container, textvariable=self.status_var).pack(anchor="w", pady=(2, 6))

		actions = ttk.Frame(container)
		actions.pack(fill="x", pady=(0, 8))
		self.scan_btn = ttk.Button(actions, text="Start Scan", command=self._start_scan)
		self.scan_btn.pack(side="left")
		self.save_btn = ttk.Button(actions, text="Save Scan", command=self._save_scan, state="disabled")
		self.save_btn.pack(side="left", padx=(8, 0))
		ttk.Button(actions, text="Close", command=self._close).pack(side="right")

		self.progress = ttk.Progressbar(container, mode="indeterminate")
		self.progress.pack(fill="x", pady=(0, 8))

		self.figure, self.axis = plt.subplots(figsize=(9.2, 4.5), dpi=100)
		self.axis.set_xlabel("Frequency (GHz)")
		self.axis.set_ylabel("Power (dB)")
		self.axis.set_title("RTL-SDR Frequency Scan")
		self.axis.grid(True, alpha=0.25)

		self.canvas = FigureCanvasTkAgg(self.figure, master=container)
		self.canvas.draw()
		self.canvas.get_tk_widget().pack(fill="both", expand=True)

	def _parse_scan_config(self):
		start_freq_hz = float(self.start_freq_var.get().strip())
		end_freq_hz = float(self.end_freq_var.get().strip())
		num_points = int(self.points_var.get().strip())
		sample_rate_hz = float(self.sample_rate_var.get().strip())
		samples_per_point = int(self.samples_per_point_var.get().strip())
		device_index = int(self.device_index_var.get().strip())
		source = self.source_var.get().strip() or "RTL-SDR"
		gain_raw = self.gain_var.get().strip()

		if not (start_freq_hz > 0 and end_freq_hz > 0):
			raise ValueError("Frequencies must be positive")
		if end_freq_hz <= start_freq_hz:
			raise ValueError("End frequency must be greater than start frequency")
		if num_points < 2:
			raise ValueError("Points must be at least 2")
		if sample_rate_hz < 1_000 or sample_rate_hz > 3_200_000:
			raise ValueError("Sample rate must be between 1,000 and 3,200,000 Hz")
		if samples_per_point < 8_192:
			raise ValueError("Samples per point must be at least 8192")

		max_center_freq_hz = float(self.settings.get("rtlsdr_max_center_freq_hz", 1_766_000_000.0))
		if end_freq_hz > max_center_freq_hz:
			raise ValueError(
				f"End frequency must be <= {int(max_center_freq_hz)} Hz for RTL-SDR (about 1.7 GHz)"
			)

		if gain_raw.lower() == "auto":
			gain = "auto"
		else:
			gain = float(gain_raw)

		return {
			"start_freq_hz": start_freq_hz,
			"end_freq_hz": end_freq_hz,
			"num_points": num_points,
			"sample_rate_hz": sample_rate_hz,
			"samples_per_point": samples_per_point,
			"device_index": device_index,
			"source": source,
			"gain": gain,
		}

	def _scan_virtual(self, frequencies_hz):
		center = (float(frequencies_hz[0]) + float(frequencies_hz[-1])) / 2.0
		width = max((float(frequencies_hz[-1]) - float(frequencies_hz[0])) / 8.0, 1.0)

		power_levels_db = []
		for freq_hz in frequencies_hz:
			noise_floor_db = -58.0 + np.random.normal(loc=0.0, scale=1.3)
			peak_boost_db = 16.0 * np.exp(-0.5 * ((float(freq_hz) - center) / width) ** 2)
			power_levels_db.append(float(noise_floor_db + peak_boost_db))

		return np.asarray(power_levels_db, dtype=np.float64)

	def _scan_rtlsdr(self, config, frequencies_hz):
		try:
			from rtlsdr import RtlSdr
		except Exception as error:
			raise RuntimeError("RTL-SDR dependency is unavailable. Install pyrtlsdr and librtlsdr.") from error

		sdr = None
		try:
			sdr = RtlSdr(device_index=int(config["device_index"]))
			sdr.sample_rate = float(config["sample_rate_hz"])
			sdr.gain = config["gain"]

			power_levels_db = []
			for freq in frequencies_hz:
				sdr.center_freq = int(freq)
				samples = sdr.read_samples(int(config["samples_per_point"]))
				samples_arr = np.asarray(samples, dtype=np.complex64)
				if samples_arr.size == 0:
					raise RuntimeError("RTL-SDR returned no samples")

				power_linear = np.mean(np.abs(samples_arr) ** 2)
				power_levels_db.append(float(10.0 * np.log10(float(power_linear) + 1e-12)))

			return np.asarray(power_levels_db, dtype=np.float64)
		finally:
			if sdr is not None:
				try:
					sdr.close()
				except Exception:
					pass

	def _start_scan(self):
		if self._scan_running:
			return

		try:
			config = self._parse_scan_config()
		except ValueError as error:
			messagebox.showerror("Data Recording", f"Invalid input: {error}")
			return

		frequencies_hz = np.linspace(config["start_freq_hz"], config["end_freq_hz"], config["num_points"])

		self._scan_running = True
		self.scan_btn.state(["disabled"])
		self.save_btn.state(["disabled"])
		self.progress.start(10)
		self.status_var.set("Status: scanning frequency range...")

		def do_scan():
			if config["source"].lower() == "virtual":
				power_levels_db = self._scan_virtual(frequencies_hz)
			else:
				power_levels_db = self._scan_rtlsdr(config, frequencies_hz)

			return {
				"config": config,
				"frequencies_hz": np.asarray(frequencies_hz, dtype=np.float64),
				"power_levels_db": np.asarray(power_levels_db, dtype=np.float64),
			}

		def on_success(result):
			self._last_scan_result = result
			self._render_plot(result["frequencies_hz"], result["power_levels_db"])

			self.status_var.set(
				"Status: scan complete "
				f"({result['config']['num_points']} points from "
				f"{result['config']['start_freq_hz'] / 1e9:.3f} to {result['config']['end_freq_hz'] / 1e9:.3f} GHz)"
			)
			self.save_btn.state(["!disabled"])
			self.append_log_fn(
				"Frequency scan complete "
				f"({result['config']['num_points']} pts, source={result['config']['source']})"
			)

		def on_error(error):
			self.status_var.set("Status: scan failed")
			messagebox.showerror("Data Recording", f"Scan failed: {error}")
			self.append_log_fn(f"Frequency scan failed: {error}")

		def on_finally():
			self._scan_running = False
			self.scan_btn.state(["!disabled"])
			self.progress.stop()

		self.run_in_background_fn(do_scan, on_success=on_success, on_error=on_error, on_finally=on_finally)

	def _render_plot(self, frequencies_hz, power_levels_db):
		self.axis.clear()
		self.axis.plot(frequencies_hz / 1e9, power_levels_db, color="#0b7285", linewidth=1.2)
		self.axis.set_xlabel("Frequency (GHz)")
		self.axis.set_ylabel("Power (dB)")
		self.axis.set_title("RTL-SDR Frequency Scan")
		self.axis.grid(True, alpha=0.25)
		self.figure.tight_layout()
		self.canvas.draw_idle()

	def _save_scan(self):
		if not self._last_scan_result:
			messagebox.showerror("Data Recording", "No scan is available to save yet.")
			return

		output_dir = filedialog.askdirectory(
			title="Select Output Folder",
			initialdir=os.path.join("data", "recordings"),
			mustexist=False,
		)
		if not output_dir:
			return

		os.makedirs(output_dir, exist_ok=True)

		timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
		base_name = f"frequency_scan_{timestamp}"
		samples_path = os.path.join(output_dir, f"{base_name}.npy")
		csv_path = os.path.join(output_dir, f"{base_name}.csv")
		metadata_path = os.path.join(output_dir, f"{base_name}.json")
		figure_path = os.path.join(output_dir, f"{base_name}.png")

		frequencies_hz = np.asarray(self._last_scan_result["frequencies_hz"], dtype=np.float64)
		power_levels_db = np.asarray(self._last_scan_result["power_levels_db"], dtype=np.float64)
		config = dict(self._last_scan_result["config"])

		scan_matrix = np.column_stack((frequencies_hz, power_levels_db)).astype(np.float64)
		np.save(samples_path, scan_matrix)

		with open(csv_path, "w", newline="", encoding="utf-8") as csv_file:
			writer = csv.writer(csv_file)
			writer.writerow(["frequency_hz", "power_db"])
			for freq_hz, power_db in scan_matrix:
				writer.writerow([float(freq_hz), float(power_db)])

		center_freq_hz = float((frequencies_hz[0] + frequencies_hz[-1]) / 2.0)
		gain_for_metadata = config["gain"]
		if gain_for_metadata == "auto":
			gain_for_metadata = -1.0

		metadata = {
			"recording_kind": "frequency_scan",
			"scan_start_freq_hz": float(frequencies_hz[0]),
			"scan_end_freq_hz": float(frequencies_hz[-1]),
			"scan_points": int(frequencies_hz.size),
			"sample_rate_hz": float(config["sample_rate_hz"]),
			"center_freq_hz": center_freq_hz,
			"gain_db": float(gain_for_metadata),
			"num_samples": int(scan_matrix.shape[0]),
			"saved_samples_file": samples_path,
			"csv_path": csv_path,
			"plot_png_path": figure_path,
			"source": str(config["source"]),
			"created_at": datetime.now().isoformat(timespec="seconds"),
		}

		with open(metadata_path, "w", encoding="utf-8") as metadata_file:
			json.dump(metadata, metadata_file, indent=2)

		self.figure.savefig(figure_path, dpi=130)

		self.status_var.set(f"Status: saved to {output_dir}")
		self.append_log_fn(f"Frequency scan saved: {os.path.basename(samples_path)}")

		if self.on_saved_callback is not None:
			try:
				self.on_saved_callback(
					{
						"samples_path": samples_path,
						"metadata_path": metadata_path,
						"csv_path": csv_path,
						"plot_path": figure_path,
						"scan_points": int(frequencies_hz.size),
					}
				)
			except Exception:
				pass

		messagebox.showinfo(
			"Data Recording",
			"Saved scan outputs:\n"
			f"- {os.path.basename(samples_path)}\n"
			f"- {os.path.basename(csv_path)}\n"
			f"- {os.path.basename(metadata_path)}\n"
			f"- {os.path.basename(figure_path)}",
		)

	def _close(self):
		if self._scan_running:
			messagebox.showwarning("Data Recording", "A scan is currently running. Please wait for it to finish.")
			return

		try:
			plt.close(self.figure)
		except Exception:
			pass

		self.popup.win.destroy()
