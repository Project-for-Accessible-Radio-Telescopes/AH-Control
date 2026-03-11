import os
import csv
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

from tools.popup import newPopup
from logic.sdr_advanced import build_frequency_axis_mhz, extract_peak_metrics
from tools.standardpopup import msgPopup

class AdvancedSignalWindow:
    def __init__(self, root, source_file, analysis, sample_rate_hz, center_freq_hz, on_export=None):
        self.root = root
        self.source_file = source_file
        self.analysis = analysis
        self.sample_rate_hz = float(sample_rate_hz)
        self.center_freq_hz = float(center_freq_hz)
        self.on_export = on_export

        self.popup = newPopup(self.root, name="Advanced Signal View (Interactive)", geometry="1120x760")

        self.averaged_psd_db = np.asarray(self.analysis["averaged_psd_db"], dtype=np.float64)
        self.waterfall_db = np.asarray(self.analysis["waterfall_db"], dtype=np.float64)
        self.nfft = int(self.analysis["nfft"])

        self.freq_axis_mhz = build_frequency_axis_mhz(self.nfft, self.sample_rate_hz, self.center_freq_hz)
        self.time_axis_s = (np.arange(self.waterfall_db.shape[0]) * self.nfft) / max(self.sample_rate_hz, 1.0)

        self._build_ui()
        self._render_initial_plot()
        self._pan_active = False
        self._zoom_active = False
        self._grid_enabled = True
        self._peak_markers_enabled = False
        self._peak_marker_artists = []

    def _build_ui(self):
        top_row = ttk.Frame(self.popup.win)
        top_row.pack(fill="x", padx=10, pady=(8, 4))

        peak_metrics = extract_peak_metrics(self.averaged_psd_db, self.freq_axis_mhz)
        summary = (
            f"File: {os.path.basename(self.source_file)} \n"
            f"Center: {self.center_freq_hz / 1e6:.6f} MHz \n"
            f"Rate: {self.sample_rate_hz / 1e6:.3f} MS/s \n"
            f"NFFT: {self.nfft} \n Segments: {self.analysis['used_segments']} \n "
            f"Peak: {peak_metrics['peak_freq_mhz']:.6f} MHz ({peak_metrics['peak_power_db']:.1f} dB) \n"
            f"SNR: {peak_metrics['snr_db']:.1f} dB"
        )
        # ttk.Label(top_row, text=summary, anchor="w", justify="left").pack(fill="x")
        
        self.aboveFrame = ttk.Frame(top_row)
        self.aboveFrame.pack(side="left", fill="x", expand=True)

        self.info_btn = ttk.Button(self.aboveFrame, text="Info Summary", command=lambda: msgPopup("File & Analysis Summary", summary, msgtype="info", size=(600, 300)).win)
        self.info_btn.pack(side="left", padx=(0, 10))

        ttk.Button(self.aboveFrame, text="Reset Zoom", command=self._reset_zoom).pack(side="left", padx=3)

        export_btn = ttk.Button(self.aboveFrame, text="Export View", command=self._export_view)
        export_btn.pack(side="left", padx=(10, 0))
        
        ttk.Button(self.aboveFrame, text="Close", command=self._close).pack(side="right", padx=(0, 6))

        controls = ttk.Frame(self.popup.win)
        controls.pack(fill="x", padx=10, pady=(0, 4))

        ttk.Label(controls, text="Colormap").pack(side="left")
        self.cmap_var = tk.StringVar(value="magma")
        self.cmap_combo = ttk.Combobox(
            controls,
            state="readonly",
            width=12,
            textvariable=self.cmap_var,
            values=["magma", "viridis", "plasma", "inferno", "cividis", "turbo"],
        )
        self.cmap_combo.pack(side="left", padx=(6, 10))
        self.cmap_combo.bind("<<ComboboxSelected>>", lambda _e: self._update_plot_style())

        ttk.Label(controls, text="Spectrum Smooth").pack(side="left")
        self.smooth_var = tk.IntVar(value=1)
        self.smooth_spin = ttk.Spinbox(controls, from_=1, to=51, increment=2, width=5, textvariable=self.smooth_var)
        self.smooth_spin.pack(side="left", padx=(6, 10))

        percentile_low = float(np.percentile(self.waterfall_db, 5))
        percentile_high = float(np.percentile(self.waterfall_db, 95))

        ttk.Label(controls, text="Min dB").pack(side="left")
        self.vmin_var = tk.StringVar(value=f"{percentile_low:.1f}")
        ttk.Entry(controls, textvariable=self.vmin_var, width=7).pack(side="left", padx=(4, 8))

        ttk.Label(controls, text="Max dB").pack(side="left")
        self.vmax_var = tk.StringVar(value=f"{percentile_high:.1f}")
        ttk.Entry(controls, textvariable=self.vmax_var, width=7).pack(side="left", padx=(4, 8))

        ttk.Button(controls, text="Apply", command=self._update_plot_style).pack(side="left", padx=3)
        ttk.Button(controls, text="Auto Range", command=self._auto_range).pack(side="left", padx=3)
        
        self.toolbar_frame = ttk.Frame(self.popup.win)
        self.toolbar_frame.pack(side="bottom", fill="x", padx=10, pady=(0, 6))

        self.status_var = tk.StringVar(value="Move cursor over graph for readout")
        ttk.Label(self.toolbar_frame, textvariable=self.status_var, anchor="w").pack(side="left", fill="x", expand=True)

        # Custom navigation and export menu replaces the default Matplotlib toolbar UI.
        self.menu_frame = ttk.Frame(self.popup.win)
        self.menu_frame.pack(side="bottom", fill="x", padx=10, pady=(0, 4))

        self.home_btn = ttk.Button(self.menu_frame, text="Home", command=self._home)
        self.home_btn.pack(side="left", padx=2)
        self.back_btn = ttk.Button(self.menu_frame, text="Back", command=self._back)
        self.back_btn.pack(side="left", padx=2)
        self.forward_btn = ttk.Button(self.menu_frame, text="Forward", command=self._forward)
        self.forward_btn.pack(side="left", padx=2)

        self.pan_btn = ttk.Button(self.menu_frame, text="Pan", command=self._toggle_pan)
        self.pan_btn.pack(side="left", padx=(10, 2))
        self.zoom_btn = ttk.Button(self.menu_frame, text="Zoom Box", command=self._toggle_zoom)
        self.zoom_btn.pack(side="left", padx=2)

        self.grid_btn = ttk.Button(self.menu_frame, text="Hide Grid", command=self._toggle_grid)
        self.grid_btn.pack(side="left", padx=(10, 2))
        self.peaks_btn = ttk.Button(self.menu_frame, text="Show Peaks", command=self._toggle_peak_markers)
        self.peaks_btn.pack(side="left", padx=2)

        self.save_png_btn = ttk.Button(self.menu_frame, text="Save PNG", command=self._save_png)
        self.save_png_btn.pack(side="right", padx=2)
        self.export_csv_btn = ttk.Button(self.menu_frame, text="Export Spectrum CSV", command=self._export_spectrum_csv)
        self.export_csv_btn.pack(side="right", padx=2)

    def _render_initial_plot(self):
        self.fig, axes = plt.subplots(2, 1, figsize=(11.0, 6.6), dpi=100)
        self.ax_spectrum, self.ax_waterfall = axes

        self.spectrum_line, = self.ax_spectrum.plot(
            self.freq_axis_mhz,
            self.averaged_psd_db,
            color="#0b7285",
            linewidth=1.1,
        )
        self.ax_spectrum.set_title("Average Spectrum (FFT)")
        self.ax_spectrum.set_xlabel("Frequency (MHz)")
        self.ax_spectrum.set_ylabel("Power (dB)")
        self.ax_spectrum.grid(alpha=0.25)

        self.waterfall_image = self.ax_waterfall.imshow(
            self.waterfall_db,
            aspect="auto",
            origin="lower",
            extent=[
                self.freq_axis_mhz[0],
                self.freq_axis_mhz[-1],
                self.time_axis_s[0] if self.time_axis_s.size else 0.0,
                self.time_axis_s[-1] if self.time_axis_s.size else 0.0,
            ],
            cmap=self.cmap_var.get(),
        )
        self.ax_waterfall.set_title("Waterfall")
        self.ax_waterfall.set_xlabel("Frequency (MHz)")
        self.ax_waterfall.set_ylabel("Time (s)")

        self.colorbar = self.fig.colorbar(self.waterfall_image, ax=self.ax_waterfall, label="Power (dB)")
        self.fig.tight_layout(rect=[0, 0.04, 1, 0.95])

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.popup.win)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=(4, 0))

        # Keep the backend navigation object for behavior, but do not show the classic toolbar.
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.toolbar_frame, pack_toolbar=False)
        self.toolbar.update()

        self._cid_motion = self.canvas.mpl_connect("motion_notify_event", self._on_mouse_move)
        self.popup.win.protocol("WM_DELETE_WINDOW", self._close)

    def _smoothed_spectrum(self):
        width = max(1, int(self.smooth_var.get()))
        if width <= 1:
            return self.averaged_psd_db
        if width % 2 == 0:
            width += 1
        kernel = np.ones(width, dtype=np.float64) / width
        return np.convolve(self.averaged_psd_db, kernel, mode="same")

    def _update_plot_style(self):
        try:
            vmin = float(self.vmin_var.get().strip())
            vmax = float(self.vmax_var.get().strip())
            if vmin >= vmax:
                raise ValueError
        except Exception:
            self.status_var.set("Invalid min/max dB values")
            return

        self.spectrum_line.set_ydata(self._smoothed_spectrum())
        self.ax_spectrum.relim()
        self.ax_spectrum.autoscale_view()

        self.waterfall_image.set_cmap(self.cmap_var.get())
        self.waterfall_image.set_clim(vmin=vmin, vmax=vmax)
        if self._peak_markers_enabled:
            self._draw_peak_markers()
        self.canvas.draw_idle()

    def _auto_range(self):
        percentile_low = float(np.percentile(self.waterfall_db, 5))
        percentile_high = float(np.percentile(self.waterfall_db, 95))
        self.vmin_var.set(f"{percentile_low:.1f}")
        self.vmax_var.set(f"{percentile_high:.1f}")
        self._update_plot_style()

    def _reset_zoom(self):
        self.ax_spectrum.set_xlim(self.freq_axis_mhz[0], self.freq_axis_mhz[-1])
        self.ax_waterfall.set_xlim(self.freq_axis_mhz[0], self.freq_axis_mhz[-1])

        if self.time_axis_s.size:
            self.ax_waterfall.set_ylim(self.time_axis_s[0], self.time_axis_s[-1])

        self.ax_spectrum.relim()
        self.ax_spectrum.autoscale_view(scalex=False, scaley=True)
        self.canvas.draw_idle()

    def _home(self):
        self.toolbar.home()
        self.canvas.draw_idle()

    def _back(self):
        self.toolbar.back()
        self.canvas.draw_idle()

    def _forward(self):
        self.toolbar.forward()
        self.canvas.draw_idle()

    def _toggle_pan(self):
        self.toolbar.pan()
        self._pan_active = not self._pan_active
        if self._pan_active and self._zoom_active:
            self._zoom_active = False
            self.zoom_btn.configure(text="Zoom Box")
        self.pan_btn.configure(text="Pan On" if self._pan_active else "Pan")

    def _toggle_zoom(self):
        self.toolbar.zoom()
        self._zoom_active = not self._zoom_active
        if self._zoom_active and self._pan_active:
            self._pan_active = False
            self.pan_btn.configure(text="Pan")
        self.zoom_btn.configure(text="Zoom On" if self._zoom_active else "Zoom Box")

    def _toggle_grid(self):
        self._grid_enabled = not self._grid_enabled
        self.ax_spectrum.grid(self._grid_enabled, alpha=0.25)
        self.grid_btn.configure(text="Hide Grid" if self._grid_enabled else "Show Grid")
        self.canvas.draw_idle()

    def _clear_peak_markers(self):
        for artist in self._peak_marker_artists:
            try:
                artist.remove()
            except Exception:
                continue
        self._peak_marker_artists = []

    def _draw_peak_markers(self, top_n=5):
        self._clear_peak_markers()
        yvals = np.asarray(self.spectrum_line.get_ydata(), dtype=np.float64)
        if yvals.size == 0:
            return
        indexes = np.argsort(yvals)[-top_n:][::-1]
        for idx in indexes:
            freq = float(self.freq_axis_mhz[idx])
            power = float(yvals[idx])
            marker = self.ax_spectrum.plot(freq, power, marker="o", color="#d9480f", markersize=4)[0]
            label = self.ax_spectrum.annotate(
                f"{freq:.4f} MHz",
                (freq, power),
                textcoords="offset points",
                xytext=(4, 6),
                fontsize=8,
                color="#d9480f",
            )
            self._peak_marker_artists.extend([marker, label])

    def _toggle_peak_markers(self):
        self._peak_markers_enabled = not self._peak_markers_enabled
        if self._peak_markers_enabled:
            self._draw_peak_markers()
            self.peaks_btn.configure(text="Hide Peaks")
        else:
            self._clear_peak_markers()
            self.peaks_btn.configure(text="Show Peaks")
        self.canvas.draw_idle()

    def _save_png(self):
        default_name = os.path.splitext(os.path.basename(self.source_file))[0] + "_advanced_view.png"
        output_path = filedialog.asksaveasfilename(
            parent=self.popup.win,
            title="Save Advanced View PNG",
            defaultextension=".png",
            initialfile=default_name,
            filetypes=[("PNG Image", "*.png"), ("All Files", "*.*")],
        )
        if not output_path:
            return
        try:
            self.fig.savefig(output_path, dpi=150)
            self.status_var.set(f"Saved PNG: {output_path}")
        except Exception as error:
            messagebox.showerror("Save PNG", f"Could not save image:\n{error}")

    def _export_spectrum_csv(self):
        default_name = os.path.splitext(os.path.basename(self.source_file))[0] + "_spectrum.csv"
        output_path = filedialog.asksaveasfilename(
            parent=self.popup.win,
            title="Export Spectrum CSV",
            defaultextension=".csv",
            initialfile=default_name,
            filetypes=[("CSV File", "*.csv"), ("All Files", "*.*")],
        )
        if not output_path:
            return

        yvals = np.asarray(self.spectrum_line.get_ydata(), dtype=np.float64)
        try:
            with open(output_path, "w", newline="", encoding="utf-8") as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(["frequency_mhz", "power_db"])
                for freq, power in zip(self.freq_axis_mhz, yvals):
                    writer.writerow([f"{float(freq):.9f}", f"{float(power):.6f}"])
            self.status_var.set(f"Exported CSV: {output_path}")
        except Exception as error:
            messagebox.showerror("Export Spectrum CSV", f"Could not export CSV:\n{error}")

    def _on_mouse_move(self, event):
        if event.inaxes is None or event.xdata is None or event.ydata is None:
            return

        if event.inaxes == self.ax_spectrum:
            idx = int(np.argmin(np.abs(self.freq_axis_mhz - event.xdata)))
            power_db = float(self.spectrum_line.get_ydata()[idx])
            self.status_var.set(f"Spectrum: {self.freq_axis_mhz[idx]:.6f} MHz | {power_db:.2f} dB")
        elif event.inaxes == self.ax_waterfall:
            idx = int(np.argmin(np.abs(self.freq_axis_mhz - event.xdata)))
            time_s = float(event.ydata)
            self.status_var.set(f"Waterfall: {self.freq_axis_mhz[idx]:.6f} MHz | {time_s:.3f} s")

    def _export_view(self):
        if self.on_export is not None:
            self.on_export(
                source_file=self.source_file,
                analysis=self.analysis,
                sample_rate_hz=self.sample_rate_hz,
                center_freq_hz=self.center_freq_hz,
            )

    def _close(self):
        try:
            if hasattr(self, "canvas"):
                self.canvas.mpl_disconnect(self._cid_motion)
        except Exception:
            pass
        try:
            if hasattr(self, "fig"):
                plt.close(self.fig)
        finally:
            self.popup.win.destroy()
