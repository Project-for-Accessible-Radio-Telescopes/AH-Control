import os
from tkinter import ttk

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

from logic.sdr_advanced import build_frequency_axis_mhz, extract_peak_metrics
from tools.popup import newPopup


class ComparisonWindow:
    def __init__(self, root, left_file, right_file, left_result, right_result):
        self.root = root
        self.left_file = left_file
        self.right_file = right_file
        self.left_result = left_result
        self.right_result = right_result

        self.popup = newPopup(self.root, name="Recording Comparison", geometry="1140x800")
        self._build_ui()

    def _build_ui(self):
        header = ttk.Frame(self.popup.win)
        header.pack(fill="x", padx=10, pady=(8, 4))

        left_analysis = self.left_result["analysis"]
        right_analysis = self.right_result["analysis"]

        left_freq = build_frequency_axis_mhz(
            left_analysis["nfft"],
            float(self.left_result["sample_rate_hz"]),
            float(self.left_result["center_freq_hz"]),
        )
        right_freq = build_frequency_axis_mhz(
            right_analysis["nfft"],
            float(self.right_result["sample_rate_hz"]),
            float(self.right_result["center_freq_hz"]),
        )

        left_spectrum = np.asarray(left_analysis["averaged_psd_db"], dtype=np.float64)
        right_spectrum = np.asarray(right_analysis["averaged_psd_db"], dtype=np.float64)

        left_peak = extract_peak_metrics(left_spectrum, left_freq)
        right_peak = extract_peak_metrics(right_spectrum, right_freq)

        summary = (
            f"A: {os.path.basename(self.left_file)} | Peak {left_peak['peak_freq_mhz']:.6f} MHz | SNR {left_peak['snr_db']:.2f} dB\n"
            f"B: {os.path.basename(self.right_file)} | Peak {right_peak['peak_freq_mhz']:.6f} MHz | SNR {right_peak['snr_db']:.2f} dB\n"
            f"Delta: Peak shift {(right_peak['peak_freq_mhz'] - left_peak['peak_freq_mhz']) * 1e3:.3f} kHz | "
            f"SNR delta {(right_peak['snr_db'] - left_peak['snr_db']):.2f} dB"
        )
        ttk.Label(header, text=summary, justify="left").pack(side="left", fill="x", expand=True)
        ttk.Button(header, text="Close", command=self._close).pack(side="right")

        fig, axes = plt.subplots(3, 1, figsize=(11.0, 7.0), dpi=100)
        ax_a, ax_b, ax_delta = axes

        ax_a.plot(left_freq, left_spectrum, color="#1d3557", linewidth=1.1)
        ax_a.set_title(f"A: {os.path.basename(self.left_file)}")
        ax_a.set_ylabel("Power (dB)")
        ax_a.grid(alpha=0.25)

        ax_b.plot(right_freq, right_spectrum, color="#457b9d", linewidth=1.1)
        ax_b.set_title(f"B: {os.path.basename(self.right_file)}")
        ax_b.set_ylabel("Power (dB)")
        ax_b.grid(alpha=0.25)

        common_bins = min(left_spectrum.size, right_spectrum.size)
        common_freq = left_freq[:common_bins]
        delta = right_spectrum[:common_bins] - left_spectrum[:common_bins]

        ax_delta.plot(common_freq, delta, color="#e76f51", linewidth=1.1)
        ax_delta.set_title("B - A Spectrum Delta")
        ax_delta.set_xlabel("Frequency (MHz)")
        ax_delta.set_ylabel("Delta (dB)")
        ax_delta.grid(alpha=0.25)

        fig.tight_layout(rect=[0, 0.04, 1, 0.96])

        toolbar_frame = ttk.Frame(self.popup.win)
        toolbar_frame.pack(side="bottom", fill="x", padx=10, pady=(0, 6))

        self.canvas = FigureCanvasTkAgg(fig, master=self.popup.win)
        self.fig = fig
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=(4, 0))

        self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame, pack_toolbar=False)
        self.toolbar.update()
        self.toolbar.pack(side="left", fill="x")

        self.popup.win.protocol("WM_DELETE_WINDOW", self._close)

    def _close(self):
        try:
            if hasattr(self, "fig"):
                plt.close(self.fig)
        finally:
            self.popup.win.destroy()
