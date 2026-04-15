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
from logic.sdr_processing import compute_power_spectrum_welch_from_sdr
from logic.rtl_sdr_recording import get_rtlsdr_class, detect_rtl_sdr_devices
from logic.wifi_scanner import scan_wifi_networks, convert_networks_to_spectrum, networks_to_dataframe


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

		self.popup = newPopup(self.root, name="Power Spectrum Analysis", geometry="980x720")
		self._acquisition_running = False
		self._last_spectrum_result = None
		self._available_devices = []

		self._build_ui()
		self.popup.win.protocol("WM_DELETE_WINDOW", self._close)

	def _build_ui(self):
		container = ttk.Frame(self.popup.win)
		container.pack(fill="both", expand=True, padx=12, pady=10)

		ttk.Label(container, text="Power Spectrum Analysis (Welch Method)", font=("TkDefaultFont", 10, "bold")).pack(anchor="w")
		ttk.Label(
			container,
			text="Acquire samples and compute power spectrum using Welch's method for improved frequency resolution.",
			justify="left",
		).pack(anchor="w", pady=(4, 8))

		form = ttk.Frame(container)
		form.pack(fill="x", pady=(0, 8))

		default_center = float(self.settings.get("capture_default_center_freq_hz", 1_450_000_000.0))

		self.center_freq_var = tk.StringVar(value=str(int(self.initial_config.get("center_freq_hz", default_center))))
		self.sample_rate_var = tk.StringVar(value=str(float(self.initial_config.get("sample_rate_hz", 2_400_000.0))))
		self.n_per_seg_var = tk.StringVar(value=str(int(self.initial_config.get("n_per_seg", 4096))))
		self.n_segs_var = tk.StringVar(value=str(int(self.initial_config.get("n_segs", 10))))
		self.gain_var = tk.StringVar(value=str(self.initial_config.get("gain", "32")))
		self.source_var = tk.StringVar(value=str(self.initial_config.get("source", "RTL-SDR")))

		row1 = ttk.Frame(form)
		row1.pack(fill="x", pady=(0, 4))
		ttk.Label(row1, text="Center Freq (Hz)", width=16).pack(side="left")
		ttk.Entry(row1, textvariable=self.center_freq_var, width=16).pack(side="left", padx=(0, 10))
		ttk.Label(row1, text="Sample Rate (Hz)", width=14).pack(side="left")
		ttk.Entry(row1, textvariable=self.sample_rate_var, width=16).pack(side="left", padx=(0, 10))
		ttk.Label(row1, text="Gain (dB)", width=8).pack(side="left")
		ttk.Entry(row1, textvariable=self.gain_var, width=8).pack(side="left")

		row2 = ttk.Frame(form)
		row2.pack(fill="x", pady=(0, 4))
		ttk.Label(row2, text="Samples/Segment", width=16).pack(side="left")
		ttk.Entry(row2, textvariable=self.n_per_seg_var, width=16).pack(side="left", padx=(0, 10))
		ttk.Label(row2, text="Num Segments", width=14).pack(side="left")
		ttk.Entry(row2, textvariable=self.n_segs_var, width=16).pack(side="left", padx=(0, 10))
		ttk.Label(row2, text="Source", width=8).pack(side="left")
		source_combo = ttk.Combobox(
			row2,
			state="readonly",
			textvariable=self.source_var,
			values=["RTL-SDR", "Virtual"],
			width=8,
		)
		source_combo.pack(side="left", padx=(0, 10))
		source_combo.bind("<<ComboboxSelected>>", self._on_source_changed)

		self.device_frame = ttk.Frame(form)
		self.device_frame.pack(fill="x", pady=(0, 4))
		self.device_label = ttk.Label(self.device_frame, text="Device", width=16)
		self.device_label.pack(side="left")
		self.device_combo = ttk.Combobox(self.device_frame, state="readonly", width=40)
		self.device_combo.pack(side="left", padx=(0, 10))
		
		# Show device frame and detect devices if RTL-SDR is default source
		if self.source_var.get() == "RTL-SDR":
			self.device_frame.pack(fill="x", pady=(0, 4))
			self._detect_and_populate_devices()
		else:
			self.device_frame.pack_forget()

		self.status_var = tk.StringVar(value="Status: ready")
		ttk.Label(container, textvariable=self.status_var).pack(anchor="w", pady=(2, 6))

		actions = ttk.Frame(container)
		actions.pack(fill="x", pady=(0, 8))
		self.acquire_btn = ttk.Button(actions, text="Compute Spectrum", command=self._start_acquisition)
		self.acquire_btn.pack(side="left")
		self.save_btn = ttk.Button(actions, text="Save Spectrum", command=self._save_spectrum, state="disabled")
		self.save_btn.pack(side="left", padx=(8, 0))
		ttk.Button(actions, text="Close", command=self._close).pack(side="right")

		self.progress = ttk.Progressbar(container, mode="indeterminate")
		self.progress.pack(fill="x", pady=(0, 8))

		self.figure, self.axis = plt.subplots(figsize=(9.2, 5), dpi=100)
		self.axis.set_xlabel("Frequency (MHz)")
		self.axis.set_ylabel("Power (dBm)")
		self.axis.set_title("Power Spectrum (Welch Method)")
		self.axis.grid(True, alpha=0.25)

		self.canvas = FigureCanvasTkAgg(self.figure, master=container)
		self.canvas.draw()
		self.canvas.get_tk_widget().pack(fill="both", expand=True)

	def _on_source_changed(self, event=None):
		"""Handle source selection change. Detect devices only for RTL-SDR."""
		source = self.source_var.get()
		
		if source == "RTL-SDR":
			# Show device frame and detect devices
			self.device_frame.pack(fill="x", pady=(0, 4), after=self.device_frame.master.winfo_children()[-2] if self.device_frame.master.winfo_children() else None)
			self._detect_and_populate_devices()
		else:
			# Hide device frame for Virtual source
			self.device_frame.pack_forget()
			self.append_log_fn(f"Source changed to {source} (WiFi frequency scanning)")

	def _detect_and_populate_devices(self):
		"""Detect RTL-SDR devices and populate device dropdown."""
		try:
			self._available_devices = detect_rtl_sdr_devices()
			if len(self._available_devices) > 0:
				device_labels = [dev["label"] for dev in self._available_devices]
				self.device_combo["values"] = device_labels
				self.device_combo.current(0)
				self.append_log_fn(f"Detected {len(self._available_devices)} RTL-SDR device(s)")
			else:
				self.device_combo["values"] = ["No devices detected"]
				self.device_combo.current(0)
				self.append_log_fn("No RTL-SDR devices detected")
		except Exception as err:
			self.device_combo["values"] = [f"Error: {str(err)[:30]}..."]
			self.device_combo.current(0)
			self.append_log_fn(f"Device detection error: {err}")

	def _parse_spectrum_config(self):
		center_freq_hz = float(self.center_freq_var.get().strip())
		sample_rate_hz = float(self.sample_rate_var.get().strip())
		n_per_seg = int(self.n_per_seg_var.get().strip())
		n_segs = int(self.n_segs_var.get().strip())
		source = self.source_var.get().strip() or "RTL-SDR"
		gain_raw = self.gain_var.get().strip()

		if not center_freq_hz > 0:
			raise ValueError("Center frequency must be positive")
		if sample_rate_hz < 1_000 or sample_rate_hz > 3_200_000:
			raise ValueError("Sample rate must be between 1,000 and 3,200,000 Hz")
		if n_per_seg < 256:
			raise ValueError("Samples per segment must be at least 256")
		if n_segs < 1:
			raise ValueError("Number of segments must be at least 1")

		# Only enforce frequency limit for RTL-SDR source
		if source.lower() == "rtl-sdr":
			max_center_freq_hz = float(self.settings.get("rtlsdr_max_center_freq_hz", 1_766_000_000.0))
			if center_freq_hz > max_center_freq_hz:
				raise ValueError(
					f"Center frequency must be <= {int(max_center_freq_hz)} Hz for RTL-SDR (about 1.7 GHz)"
				)

		try:
			gain = float(gain_raw)
		except ValueError:
			gain = 32.0

		device_index = 0
		if len(self._available_devices) > 0:
			device_label = self.device_combo.get()
			for dev in self._available_devices:
				if dev["label"] == device_label:
					device_index = dev["index"]
					break

		return {
			"center_freq_hz": center_freq_hz,
			"sample_rate_hz": sample_rate_hz,
			"n_per_seg": n_per_seg,
			"n_segs": n_segs,
			"device_index": device_index,
			"source": source,
			"gain": gain,
		}

	def _generate_virtual_spectrum(self, sample_rate, center_freq, n_per_seg):
		"""Generate WiFi frequency spectrum using real network scanning."""
		try:
			# Attempt real WiFi scanning
			networks = scan_wifi_networks()
			self.append_log_fn(f"Real WiFi scan: detected {len(networks)} network(s)")
			
			# Log detected networks
			self.append_log_fn(networks_to_dataframe(networks))
			
			# Convert to spectrum
			frequencies_mhz, pxx = convert_networks_to_spectrum(
				networks, sample_rate, center_freq, n_per_seg
			)
			
			return frequencies_mhz, pxx
		
		except Exception as err:
			# Fall back to synthetic spectrum if real scanning fails
			self.append_log_fn(f"Real WiFi scan failed: {err}. Using synthetic spectrum.")
			return self._generate_synthetic_spectrum(sample_rate, center_freq, n_per_seg)

	def _generate_synthetic_spectrum(self, sample_rate, center_freq, n_per_seg):
		"""Generate synthetic WiFi frequency spectrum (fallback)."""
		samples = np.random.randn(n_per_seg) + 1j * np.random.randn(n_per_seg)
		
		# Add strong WiFi channel peaks for visibility
		wifi_peaks = [
			(2_412_000_000, -50),  # 2.4 GHz Channel 1, strong signal
			(2_437_000_000, -55),  # 2.4 GHz Channel 6, medium signal
			(2_462_000_000, -62),  # 2.4 GHz Channel 11, weaker signal
			(5_180_000_000, -45),  # 5 GHz Channel 36, strong signal
			(5_240_000_000, -60),  # 5 GHz Channel 48, medium signal
			(5_500_000_000, -70),  # 5 GHz Channel 100, weak signal
			(5_745_000_000, -58),  # 5 GHz Channel 149, medium signal
		]
		
		# Add peaks that fall within the current frequency band
		for peak_freq, rssi_dbm in wifi_peaks:
			if abs(peak_freq - center_freq) < sample_rate / 2:
				# Calculate offset in sample space
				freq_offset = peak_freq - center_freq
				bin_normalized = freq_offset / sample_rate
				bin_index = int((bin_normalized + 0.5) * n_per_seg)
				
				if 0 <= bin_index < n_per_seg:
					# Convert dBm to amplitude
					amplitude = np.sqrt(10 ** (rssi_dbm / 10)) * 3  # 3x amplification
					peak_width = max(20, n_per_seg // 50)  # Wider peaks
					start = max(0, bin_index - peak_width)
					end = min(n_per_seg, bin_index + peak_width)
					
					peak_pos = np.arange(start, end, dtype=float)
					sigma = peak_width / 2.5
					gaussian = np.exp(-((peak_pos - bin_index) ** 2) / (2 * sigma ** 2))
					
					samples[start:end] += amplitude * gaussian * np.exp(1j * np.random.randn(end - start))
		
		from scipy.fft import fftshift
		from scipy import signal
		
		frequencies, pxx = signal.welch(samples, fs=sample_rate, nperseg=n_per_seg, window='hann')
		
		# Convert to dBm for better visibility
		pxx_dbm = 10 * np.log10(pxx + 1e-12)
		
		frequencies_mhz = (frequencies + center_freq) / 1e6
		frequencies_mhz = fftshift(frequencies_mhz)
		pxx_dbm = fftshift(pxx_dbm)
		
		return frequencies_mhz, pxx_dbm

	def _acquire_sdr_spectrum(self, config):
		"""Acquire spectrum from RTL-SDR device using Welch method."""
		try:
			from rtlsdr import RtlSdr
		except Exception as error:
			raise RuntimeError("RTL-SDR dependency unavailable. Install pyrtlsdr and librtlsdr.") from error

		sdr = None
		try:
			sdr = RtlSdr(device_index=int(config["device_index"]))
			sdr.sample_rate = float(config["sample_rate_hz"])
			sdr.center_freq = int(config["center_freq_hz"])
			sdr.gain = float(config["gain"])

			# Compute spectrum using Welch method from SDR
			frequencies_mhz, pxx = compute_power_spectrum_welch_from_sdr(
				sdr,
				sample_rate=float(config["sample_rate_hz"]),
				centre_freq=int(config["center_freq_hz"]),
				n_per_seg=int(config["n_per_seg"]),
				n_segs=int(config["n_segs"]),
				bias_tee=False
			)
			
			return frequencies_mhz, pxx

		finally:
			if sdr is not None:
				try:
					sdr.close()
				except Exception:
					pass

	def _start_acquisition(self):
		if self._acquisition_running:
			return

		try:
			config = self._parse_spectrum_config()
		except ValueError as error:
			messagebox.showerror("Power Spectrum Analysis", f"Invalid input: {error}")
			return

		self._acquisition_running = True
		self.acquire_btn.state(["disabled"])
		self.save_btn.state(["disabled"])
		self.progress.start(10)
		self.status_var.set("Status: computing spectrum...")

		def do_acquisition():
			if config["source"].lower() == "virtual":
				frequencies_mhz, pxx = self._generate_virtual_spectrum(
					config["sample_rate_hz"],
					config["center_freq_hz"],
					config["n_per_seg"]
				)
			else:
				frequencies_mhz, pxx = self._acquire_sdr_spectrum(config)

			return {
				"config": config,
				"frequencies_mhz": np.asarray(frequencies_mhz, dtype=np.float64),
				"pxx": np.asarray(pxx, dtype=np.float64),
			}

		def on_success(result):
			self._last_spectrum_result = result
			self._render_plot(result["frequencies_mhz"], result["pxx"])

			freq_range = (result["frequencies_mhz"].max() - result["frequencies_mhz"].min())
			self.status_var.set(
				"Status: spectrum computed "
				f"({result['config']['n_segs']} segments, "
				f"range: {freq_range:.3f} MHz)"
			)
			self.save_btn.state(["!disabled"])
			self.append_log_fn(
				"Spectrum computed: "
				f"{result['config']['n_segs']} segments @ "
				f"{result['config']['sample_rate_hz']/1e6:.2f} MS/s"
			)

		def on_error(error):
			self.status_var.set("Status: spectrum failed")
			messagebox.showerror("Power Spectrum Analysis", f"Acquisition failed: {error}")
			self.append_log_fn(f"Spectrum acquisition failed: {error}")

		def on_finally():
			self._acquisition_running = False
			self.acquire_btn.state(["!disabled"])
			self.progress.stop()

		self.run_in_background_fn(do_acquisition, on_success=on_success, on_error=on_error, on_finally=on_finally)

	def _render_plot(self, frequencies_mhz, pxx):
		self.axis.clear()
		self.axis.plot(frequencies_mhz, pxx, color="#0b7285", linewidth=1.0)
		self.axis.set_xlabel("Frequency (MHz)")
		self.axis.set_ylabel("Power (dBm)")
		self.axis.set_title("Power Spectrum (Welch Method)")
		self.axis.grid(True, alpha=0.25)
		self.figure.tight_layout()
		self.canvas.draw_idle()

	def _save_spectrum(self):
		if not self._last_spectrum_result:
			messagebox.showerror("Power Spectrum Analysis", "No spectrum available to save yet.")
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
		base_name = f"spectrum_{timestamp}"
		spectrum_path = os.path.join(output_dir, f"{base_name}_spectrum.npy")
		csv_path = os.path.join(output_dir, f"{base_name}_spectrum.csv")
		metadata_path = os.path.join(output_dir, f"{base_name}_metadata.json")
		figure_path = os.path.join(output_dir, f"{base_name}_spectrum.png")

		frequencies_mhz = np.asarray(self._last_spectrum_result["frequencies_mhz"], dtype=np.float64)
		pxx = np.asarray(self._last_spectrum_result["pxx"], dtype=np.float64)
		config = dict(self._last_spectrum_result["config"])

		spectrum_matrix = np.column_stack((frequencies_mhz, pxx)).astype(np.float64)
		np.save(spectrum_path, spectrum_matrix)

		with open(csv_path, "w", newline="", encoding="utf-8") as csv_file:
			writer = csv.writer(csv_file)
			writer.writerow(["frequency_mhz", "power_dbm"])
			for freq_mhz, power in spectrum_matrix:
				writer.writerow([float(freq_mhz), float(power)])

		metadata = {
			"recording_kind": "welch_power_spectrum",
			"center_freq_hz": float(config["center_freq_hz"]),
			"sample_rate_hz": float(config["sample_rate_hz"]),
			"n_per_seg": int(config["n_per_seg"]),
			"n_segs": int(config["n_segs"]),
			"gain_db": float(config["gain"]),
			"frequency_range_mhz": [float(frequencies_mhz.min()), float(frequencies_mhz.max())],
			"power_range_dbm": [float(pxx.min()), float(pxx.max())],
			"spectrum_file": spectrum_path,
			"csv_path": csv_path,
			"plot_png_path": figure_path,
			"source": str(config["source"]),
			"created_at": datetime.now().isoformat(timespec="seconds"),
		}

		with open(metadata_path, "w", encoding="utf-8") as metadata_file:
			json.dump(metadata, metadata_file, indent=2)

		self.figure.savefig(figure_path, dpi=130)

		self.status_var.set(f"Status: saved to {output_dir}")
		self.append_log_fn(f"Spectrum saved: {os.path.basename(spectrum_path)}")

		if self.on_saved_callback is not None:
			try:
				self.on_saved_callback(
					{
						"spectrum_path": spectrum_path,
						"metadata_path": metadata_path,
						"csv_path": csv_path,
						"plot_path": figure_path,
						"center_freq_hz": config["center_freq_hz"],
						"sample_rate_hz": config["sample_rate_hz"],
					}
				)
			except Exception:
				pass

		messagebox.showinfo(
			"Power Spectrum Analysis",
			"Saved spectrum outputs:\n"
			f"- {os.path.basename(spectrum_path)}\n"
			f"- {os.path.basename(csv_path)}\n"
			f"- {os.path.basename(metadata_path)}\n"
			f"- {os.path.basename(figure_path)}",
		)

	def _close(self):
		if self._acquisition_running:
			messagebox.showwarning("Power Spectrum Analysis", "Acquisition in progress. Please wait.")
			return

		try:
			plt.close(self.figure)
		except Exception:
			pass

		self.popup.win.destroy()
