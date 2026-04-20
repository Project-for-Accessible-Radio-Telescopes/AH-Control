import os
import tkinter as tk
from tkinter import ttk, messagebox
import json
from datetime import datetime

from tools.popup import newPopup
from logic.util.file_helpers import find_recording_metadata_path


class RecordingBrowserWindow:
    def __init__(self, root, recordings_dir, analyze_fn, append_log_fn, settings=None):

        self.root = root
        self.recordings_dir = recordings_dir
        self.analyze_fn = analyze_fn
        self.append_log_fn = append_log_fn
        self.settings = settings or {}
        self.selected_recording = None
        self.recording_data = {}  # Store full recording info by item_id

        # Get theme from settings
        self.theme = self.settings.get("theme", "light")
        if self.theme == "dark":
            self.bg_color = "#333333"
            self.fg_color = "#ffffff"
        else:
            self.bg_color = "#ffffff"
            self.fg_color = "#000000"

        self.popup = newPopup(self.root, name="Recording Browser", geometry="800x600")
        self.popup.win.configure(bg=self.bg_color)
        self._build_ui()
        self._load_recordings()
        self.popup.win.protocol("WM_DELETE_WINDOW", self._close)

    def _configure_styles(self):
        """Configure ttk styles based on the selected theme."""
        style = ttk.Style(self.popup.win)
        
        if self.theme == "dark":
            # Dark theme colors
            style.configure("Treeview", background="#2c2c2c", foreground="#f1f1f1", fieldbackground="#2c2c2c")
            style.configure("Treeview.Heading", background="#505050", foreground="#f1f1f1")
            style.map("Treeview", background=[("selected", "#6b6b6b")])
            style.configure("TFrame", background="#333333")
            style.configure("TLabel", background="#333333", foreground="#f1f1f1")
            style.configure("TButton", background="#505050", foreground="#f1f1f1")
            style.map("TButton", background=[("active", "#666666")])
        else:
            # Light theme colors (default)
            style.configure("Treeview", background="#ffffff", foreground="#000000", fieldbackground="#ffffff")
            style.configure("Treeview.Heading", background="#f0f0f0", foreground="#000000")
            style.map("Treeview", background=[("selected", "#0078d4")])
            style.configure("TFrame", background="#ffffff")
            style.configure("TLabel", background="#ffffff", foreground="#000000")
            style.configure("TButton", background="#f0f0f0", foreground="#000000")
            style.map("TButton", background=[("active", "#e0e0e0")])

    def _build_ui(self):
        """Build the user interface."""
        # Configure ttk styles for the theme
        self._configure_styles()
        
        body = ttk.Frame(self.popup.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)

        # Title
        ttk.Label(body, text="Recording Browser", font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
        ttk.Label(
            body,
            text="Browse and analyze saved RF recordings",
            justify="left",
        ).pack(anchor="w", pady=(4, 8))

        # Recordings list with scrollbar
        list_frame = ttk.Frame(body)
        list_frame.pack(fill="both", expand=True, pady=(8, 8))

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")

        self.recordings_tree = ttk.Treeview(
            list_frame,
            columns=("timestamp", "freq_mhz", "rate_mhz", "gain", "samples"),
            height=15,
            yscrollcommand=scrollbar.set,
        )
        scrollbar.config(command=self.recordings_tree.yview)

        # Configure columns
        self.recordings_tree.column("#0", width=200)
        self.recordings_tree.heading("#0", text="Filename")
        
        self.recordings_tree.column("timestamp", width=150)
        self.recordings_tree.heading("timestamp", text="Timestamp")
        
        self.recordings_tree.column("freq_mhz", width=100)
        self.recordings_tree.heading("freq_mhz", text="Center (MHz)")
        
        self.recordings_tree.column("rate_mhz", width=100)
        self.recordings_tree.heading("rate_mhz", text="Rate (MHz)")
        
        self.recordings_tree.column("gain", width=80)
        self.recordings_tree.heading("gain", text="Gain (dB)")
        
        self.recordings_tree.column("samples", width=100)
        self.recordings_tree.heading("samples", text="Samples")

        self.recordings_tree.pack(fill="both", expand=True)
        self.recordings_tree.bind("<<TreeviewSelect>>", self._on_recording_select)

        # Details panel
        details_frame = ttk.LabelFrame(body, text="Recording Details", padding=10)
        details_frame.pack(fill="x", pady=(8, 8))

        self.details_var = tk.StringVar(value="Select a recording to view details")
        details_text = ttk.Label(details_frame, textvariable=self.details_var, justify="left", wraplength=700)
        details_text.pack(anchor="w")

        # Button panel
        button_frame = ttk.Frame(body)
        button_frame.pack(fill="x", pady=(8, 0))

        self.analyze_btn = ttk.Button(button_frame, text="Analyze", command=self._analyze_selected)
        self.analyze_btn.pack(side="left", padx=(0, 8))
        self.analyze_btn.config(state="disabled")

        self.open_advanced_btn = ttk.Button(button_frame, text="Advanced View", command=self._open_advanced_view)
        self.open_advanced_btn.pack(side="left", padx=(0, 8))
        self.open_advanced_btn.config(state="disabled")

        self.refresh_btn = ttk.Button(button_frame, text="Refresh", command=self._load_recordings)
        self.refresh_btn.pack(side="left", padx=(0, 8))

        ttk.Button(button_frame, text="Close", command=self._close).pack(side="right")

    def find_recordings(self, directory):
        """Find all .npy recordings in directory and subdirectories.
        
        Args:
            directory: Directory to search
            
        Returns:
            List of recording dicts with samples_path and metadata_path
        """
        recordings = []

        if not os.path.exists(directory):
            return recordings

        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith(".npy"):
                    samples_path = os.path.join(root, file)
                    metadata_path = find_recording_metadata_path(samples_path)
                    recordings.append({
                        "samples_path": samples_path,
                        "metadata_path": metadata_path,
                    })

        return recordings

    def _get_info_from_recordings(self, recordings):
        info_list = []
        for rec in recordings:
            metadata = {}
            if rec["metadata_path"] and os.path.exists(rec["metadata_path"]):
                try:
                    with open(rec["metadata_path"], "r", encoding="utf-8") as f:
                        metadata = json.load(f)
                except Exception as e:
                    self.append_log_fn(f"Error loading metadata: {e}")
            
            info_list.append({
                "samples_path": rec["samples_path"],
                "metadata_path": rec["metadata_path"],
                "metadata": metadata,
            })
        
        return info_list

    def _load_recordings(self):
        """Load and display all recordings in the browser."""
        # Clear existing items
        for item in self.recordings_tree.get_children():
            self.recordings_tree.delete(item)
        self.recording_data.clear()

        # Find all recordings
        recordings = self.find_recordings(self.recordings_dir)
        info_list = self._get_info_from_recordings(recordings)

        # Sort by timestamp (newest first)
        info_list.sort(
            key=lambda x: x["metadata"].get("created_at", ""),
            reverse=True
        )

        # Add to tree
        for info in info_list:
            filename = os.path.basename(info["samples_path"])
            metadata = info["metadata"]

            timestamp = metadata.get("created_at", "unknown")
            freq_mhz = f"{metadata.get('center_freq_hz', 0) / 1e6:.1f}" if metadata.get("center_freq_hz") else "--"
            rate_mhz = f"{metadata.get('sample_rate_hz', 0) / 1e6:.2f}" if metadata.get("sample_rate_hz") else "--"
            gain = f"{metadata.get('gain_db', 0):.1f}" if metadata.get("gain_db") else "--"
            samples = f"{metadata.get('num_samples', 0):,}" if metadata.get("num_samples") else "--"

            item_id = self.recordings_tree.insert(
                "",
                "end",
                text=filename,
                values=(timestamp, freq_mhz, rate_mhz, gain, samples)
            )
            # Store full info in dictionary
            self.recording_data[item_id] = {
                "samples_path": info["samples_path"],
                "metadata_path": info["metadata_path"],
                "metadata": metadata,
            }

        self.append_log_fn(f"Loaded {len(info_list)} recording(s)")

    def _on_recording_select(self, event):
        """Handle recording selection."""
        selection = self.recordings_tree.selection()
        if not selection:
            self.selected_recording = None
            self.analyze_btn.config(state="disabled")
            self.details_var.set("Select a recording to view details")
            return

        item_id = selection[0]
        self.selected_recording = item_id

        # Get metadata from stored data
        if item_id not in self.recording_data:
            self.details_var.set("Recording data not found")
            return

        recording_info = self.recording_data[item_id]
        filename = self.recordings_tree.item(item_id, "text")
        metadata = recording_info["metadata"]

        # Build details display
        details = f"File: {filename}\n"
        if metadata:
            created_at = metadata.get("created_at", "unknown")
            center_freq = metadata.get("center_freq_hz", 0)
            sample_rate = metadata.get("sample_rate_hz", 0)
            gain = metadata.get("gain_db", 0)
            num_samples = metadata.get("num_samples", 0)
            duration = metadata.get("duration_s", 0)
            serial = metadata.get("serial", "unknown")

            details += f"Timestamp: {created_at}\n"
            details += f"Center Frequency: {center_freq / 1e6:.2f} MHz\n"
            details += f"Sample Rate: {sample_rate / 1e6:.2f} MHz\n"
            details += f"Gain: {gain} dB\n"
            details += f"Samples: {num_samples:,}\n"
            details += f"Duration: {duration:.3f} s\n"
            details += f"Device Serial: {serial}"
        else:
            details += "No metadata available"

        self.details_var.set(details)
        self.analyze_btn.config(state="normal")
        self.open_advanced_btn.config(state="normal")

    def _analyze_selected(self):
        """Analyze the selected recording (simple analysis)."""
        if not self.selected_recording:
            messagebox.showwarning("No Selection", "Please select a recording to analyze")
            return

        item_id = self.selected_recording
        recording_info = self.recording_data.get(item_id)
        if not recording_info:
            messagebox.showerror("Error", "Recording data not found")
            return

        # For now, just log the selection
        filename = self.recordings_tree.item(item_id, "text")
        self.append_log_fn(f"Analyzing: {filename}")

    def _open_advanced_view(self):
        """Open the selected recording in advanced view."""
        if not self.selected_recording:
            messagebox.showwarning("No Selection", "Please select a recording to analyze")
            return

        item_id = self.selected_recording
        recording_info = self.recording_data.get(item_id)
        if not recording_info:
            messagebox.showerror("Error", "Recording data not found")
            return

        samples_path = recording_info["samples_path"]
        metadata_path = recording_info["metadata_path"]
        filename = self.recordings_tree.item(item_id, "text")

        self.append_log_fn(f"Opening advanced view for: {filename}")
        
        # Call the analyze function from main window
        if self.analyze_fn:
            try:
                self.analyze_fn(samples_path, metadata_path)
            except Exception as error:
                messagebox.showerror("Advanced View", f"Could not open advanced view:\n{error}")
                self.append_log_fn(f"Advanced view failed: {error}")

    def _close(self):
        """Close the window."""
        self.popup.win.destroy()
