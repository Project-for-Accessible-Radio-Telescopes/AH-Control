import json
import os

import numpy as np

from logic.util.file_helpers import find_recording_metadata_path
from logic.util.validation import validate_recording_integrity


DEFAULT_SAMPLE_RATE_HZ = 2_048_000.0
DEFAULT_CENTER_FREQ_HZ = 100_000_000.0


def _find_metadata_path(samples_path):
    return find_recording_metadata_path(samples_path)


def build_frequency_axis_mhz(nfft, sample_rate_hz, center_freq_hz):
    frequency_axis_hz = np.linspace(
        center_freq_hz - sample_rate_hz / 2.0,
        center_freq_hz + sample_rate_hz / 2.0,
        int(nfft),
        endpoint=False,
    )
    return frequency_axis_hz / 1e6


def compute_spectrum_and_waterfall(samples, nfft=4096, max_segments=350):
    samples = np.asarray(samples)
    if samples.ndim != 1:
        samples = samples.reshape(-1)

    nfft = int(nfft)
    if samples.size < nfft:
        raise ValueError(f"Need at least {nfft} samples for advanced view")

    centered = samples - np.mean(samples)
    blocks = centered.size // nfft
    if blocks <= 0:
        raise ValueError("Not enough samples after preprocessing")

    if blocks > max_segments:
        step = int(np.ceil(blocks / max_segments))
        block_indexes = range(0, blocks, step)
    else:
        block_indexes = range(blocks)

    window = np.hanning(nfft)
    spectrums = []
    for block_index in block_indexes:
        start = block_index * nfft
        segment = centered[start:start + nfft] * window
        fft_vals = np.fft.fftshift(np.fft.fft(segment, n=nfft))
        power_db = 10.0 * np.log10(np.abs(fft_vals) ** 2 + 1e-12)
        spectrums.append(power_db)

    waterfall_db = np.asarray(spectrums, dtype=np.float64)
    averaged_psd_db = np.mean(waterfall_db, axis=0)

    return {
        "waterfall_db": waterfall_db,
        "averaged_psd_db": averaged_psd_db,
        "used_segments": int(waterfall_db.shape[0]),
        "used_samples": int(waterfall_db.shape[0] * nfft),
        "nfft": nfft,
    }


def extract_peak_metrics(averaged_psd_db, freq_axis_mhz):
    peak_index = int(np.argmax(averaged_psd_db))
    peak_freq_mhz = float(freq_axis_mhz[peak_index])
    peak_power_db = float(averaged_psd_db[peak_index])
    noise_floor_db = float(np.median(averaged_psd_db))
    snr_db = peak_power_db - noise_floor_db

    return {
        "peak_index": peak_index,
        "peak_freq_mhz": peak_freq_mhz,
        "peak_power_db": peak_power_db,
        "noise_floor_db": noise_floor_db,
        "snr_db": snr_db,
    }


def analyze_recording_for_advanced_view(samples_path, nfft=4096, max_segments=350, max_preview_samples=8_000_000):
    metadata_path = _find_metadata_path(samples_path)
    integrity = validate_recording_integrity(samples_path=samples_path, metadata_path=metadata_path)
    if integrity["errors"]:
        raise ValueError("; ".join(integrity["errors"]))

    metadata = {}

    metadata_found = metadata_path is not None
    if metadata_found:
        with open(metadata_path, "r", encoding="utf-8") as metadata_file:
            metadata = json.load(metadata_file)

    sample_rate_hz = float(metadata.get("sample_rate_hz", DEFAULT_SAMPLE_RATE_HZ))
    center_freq_hz = float(metadata.get("center_freq_hz", DEFAULT_CENTER_FREQ_HZ))

    samples = np.load(samples_path)
    truncated = False
    if samples.size > max_preview_samples:
        samples = samples[:max_preview_samples]
        truncated = True

    analysis = compute_spectrum_and_waterfall(samples=samples, nfft=nfft, max_segments=max_segments)

    return {
        "analysis": analysis,
        "sample_rate_hz": sample_rate_hz,
        "center_freq_hz": center_freq_hz,
        "metadata_found": metadata_found,
        "truncated": truncated,
        "integrity_warnings": integrity["warnings"],
    }
