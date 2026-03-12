import json
import os
from datetime import datetime

import numpy as np


def _build_recording_metadata(
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
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{tag}_{timestamp}_dev{int(device_index)}"

    samples_path = os.path.join(output_dir, f"{base_name}.npy")
    metadata_path = os.path.join(output_dir, f"{base_name}.json")

    np.save(samples_path, samples)

    metadata = _build_recording_metadata(
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
