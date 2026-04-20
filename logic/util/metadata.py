"""Metadata building and recording management utilities."""
import json
import os
from datetime import datetime

import numpy as np


def build_recording_metadata(
    device_index,
    serial,
    center_freq_hz,
    sample_rate_hz,
    gain_db,
    duration_s,
    num_samples,
    samples_path,
    created_at,
):
    """Build a metadata dictionary for a recording.
    
    Args:
        device_index: RTL-SDR device index
        serial: Device serial number
        center_freq_hz: Center frequency in Hz
        sample_rate_hz: Sample rate in Hz
        gain_db: Gain in dB
        duration_s: Recording duration in seconds
        num_samples: Total number of samples
        samples_path: Path to saved samples file
        created_at: Creation timestamp string
        
    Returns:
        Dict with recording metadata
    """
    return {
        "device_index": int(device_index),
        "serial": serial,
        "center_freq_hz": float(center_freq_hz),
        "sample_rate_hz": float(sample_rate_hz),
        "gain_db": float(gain_db),
        "duration_s": float(duration_s),
        "num_samples": int(num_samples),
        "saved_samples_file": samples_path,
        "created_at": created_at,
    }


def save_samples_and_metadata(
    *,
    samples,
    output_dir,
    tag,
    device_index,
    serial,
    center_freq_hz,
    sample_rate_hz,
    gain_db,
    duration_s,
    num_samples,
):
    """Save samples array and metadata to files.
    
    Creates timestamped .npy and .json files in output_dir with filenames:
    {tag}_{timestamp}_dev{device_index}.[npy|json]
    
    Args:
        samples: np.ndarray of samples to save
        output_dir: Directory to save files in (created if missing)
        tag: Filename prefix tag
        device_index: RTL-SDR device index
        serial: Device serial number
        center_freq_hz: Center frequency in Hz
        sample_rate_hz: Sample rate in Hz
        gain_db: Gain in dB
        duration_s: Recording duration in seconds
        num_samples: Total number of samples
        
    Returns:
        Dict with keys:
            - samples_path: path to .npy file
            - metadata_path: path to .json file
            - num_samples: sample count
    """
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{tag}_{timestamp}_dev{int(device_index)}"

    samples_path = os.path.join(output_dir, f"{base_name}.npy")
    metadata_path = os.path.join(output_dir, f"{base_name}.json")

    np.save(samples_path, samples)

    metadata = build_recording_metadata(
        device_index=device_index,
        serial=serial,
        center_freq_hz=center_freq_hz,
        sample_rate_hz=sample_rate_hz,
        gain_db=gain_db,
        duration_s=duration_s,
        num_samples=num_samples,
        samples_path=samples_path,
        created_at=timestamp,
    )

    with open(metadata_path, "w", encoding="utf-8") as metadata_file:
        json.dump(metadata, metadata_file, indent=2)

    return {
        "samples_path": samples_path,
        "metadata_path": metadata_path,
        "num_samples": int(num_samples),
    }
