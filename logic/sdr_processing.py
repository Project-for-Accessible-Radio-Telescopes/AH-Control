import json
import os
from datetime import datetime

import numpy as np
from scipy import signal

from logic.util.file_helpers import find_recording_metadata_path
from logic.util.validation import validate_recording_integrity


def compute_rms_db(samples: np.ndarray, epsilon: float = 1e-12) -> float:
    """Compute RMS amplitude in dBFS-like scale for complex or real samples."""
    values = np.asarray(samples)
    if values.ndim != 1:
        values = values.reshape(-1)
    if values.size == 0:
        raise ValueError("Cannot compute RMS from empty sample array")

    rms = float(np.sqrt(np.mean(np.abs(values) ** 2)))
    return float(20.0 * np.log10(rms + float(epsilon)))


def compute_power_spectrum_welch(samples: np.ndarray, sample_rate: float, centre_freq: float, 
                                  n_per_seg: int, n_segs: int) -> tuple:
    """
    Compute power spectrum using Welch's method with FFT shift correction.
    
    The Welch method provides better frequency resolution by dividing samples
    into overlapping segments, computing FFT of each, and averaging the results.
    
    Parameters:
    -----------
    samples : np.ndarray
        Complex or real samples from SDR (or can process in chunks)
    sample_rate : float
        Sample rate in Hz
    centre_freq : float
        Center frequency of the SDR in Hz
    n_per_seg : int
        Number of samples per segment (FFT size)
    n_segs : int
        Number of segments to average over
    
    Returns:
    --------
    tuple
        (frequencies_mhz, power_spectrum)
        - frequencies_mhz : np.ndarray
            Frequency axis in MHz, centered at centre_freq
        - power_spectrum : np.ndarray
            Power spectral density (PSD) in linear scale
    
    Notes:
    ------
    The frequency range is: [-(sample_rate)/2 + centre_freq, +(sample_rate)/2 + centre_freq]
    """
    if samples.size == 0:
        raise ValueError("Cannot compute power spectrum from empty sample array")
    
    samples = np.asarray(samples)
    if samples.ndim != 1:
        samples = samples.reshape(-1)
    
    # Use scipy.signal.welch to compute power spectral density.
    # For complex SDR samples, welch returns a two-sided spectrum in wrapped
    # frequency order, so sort the bins explicitly by frequency.
    frequencies, pxx_den = signal.welch(
        samples, 
        fs=sample_rate, 
        window='hann',
        nperseg=n_per_seg, 
        noverlap=None,  # Default 50% overlap
        average='mean',
        return_onesided=False,
    )
    
    sort_index = np.argsort(frequencies)
    frequencies_mhz = (frequencies[sort_index] + centre_freq) / 1e6
    pxx_den_shifted = pxx_den[sort_index]
    
    return frequencies_mhz, pxx_den_shifted


def compute_power_spectrum_welch_from_sdr(sdr, sample_rate: float, centre_freq: float, 
                                           n_per_seg: int, n_segs: int, bias_tee: bool = True) -> tuple:
    """
    Read samples directly from SDR and compute power spectrum using Welch's method.
    
    This is a live variant that reads multiple segments from the SDR device and averages
    the resulting power spectra, providing better noise floor estimates.
    
    Parameters:
    -----------
    sdr : RtlSdr
        RTL-SDR device object (already configured with sample_rate and center_freq)
    sample_rate : float
        Sample rate in Hz (should match sdr.sample_rate)
    centre_freq : float
        Center frequency in Hz (should match sdr.center_freq)
    n_per_seg : int
        Number of samples to read per segment
    n_segs : int
        Number of segments to acquire and average
    bias_tee : bool
        Whether to enable bias tee on the device
    
    Returns:
    --------
    tuple
        (frequencies_mhz, power_spectrum_mean)
        - frequencies_mhz : np.ndarray
            Frequency axis in MHz
        - power_spectrum_mean : np.ndarray
            Averaged power spectral density (PSD)
    
    Raises:
    -------
    RuntimeError
        If SDR read fails or device disconnects
    """
    try:
        # Set bias tee if requested
        sdr.set_bias_tee(bias_tee)
        
        # Clear buffer with initial reads
        for _ in range(3):
            sdr.read_samples(n_per_seg)
        
        # Initialize accumulator for averaging (size determined on first welch call)
        pxx_den_sum = None
        frequencies = None
        
        # Read and process multiple segments
        for seg_idx in range(n_segs):
            samples = sdr.read_samples(n_per_seg)
            
            # Compute Welch PSD for this segment
            freq_seg, pxx_den = signal.welch(
                samples, 
                fs=sample_rate, 
                window='hann',
                nperseg=n_per_seg,
                noverlap=None,
                average='mean',
                return_onesided=False,
            )
            
            # Initialize accumulator on first iteration with the actual welch size.
            if pxx_den_sum is None:
                pxx_den_sum = np.zeros_like(pxx_den)
                frequencies = freq_seg
            
            pxx_den_sum += pxx_den
        
        # Average the power spectra
        pxx_den_mean = pxx_den_sum / n_segs
        
        sort_index = np.argsort(frequencies)
        frequencies_mhz = (frequencies[sort_index] + centre_freq) / 1e6
        pxx_den_mean = pxx_den_mean[sort_index]
        
        return frequencies_mhz, pxx_den_mean
    
    finally:
        # Always disable bias tee when done
        sdr.set_bias_tee(False)



def _compute_psd_db(samples: np.ndarray, nfft: int = 4096) -> np.ndarray:
    samples = np.asarray(samples)
    if samples.ndim != 1:
        samples = samples.reshape(-1)

    if samples.size < nfft:
        raise ValueError(f"Not enough samples for FFT size {nfft}")

    centered = samples - np.mean(samples)
    window = np.hanning(nfft)
    blocks = centered.size // nfft

    if blocks == 0:
        raise ValueError("Not enough samples after preprocessing")

    power_accumulator = np.zeros(nfft, dtype=np.float64)

    for block_index in range(blocks):
        start = block_index * nfft
        segment = centered[start:start + nfft] * window
        spectrum = np.fft.fftshift(np.fft.fft(segment, n=nfft))
        power_accumulator += np.abs(spectrum) ** 2

    averaged_power = power_accumulator / blocks
    return 10.0 * np.log10(averaged_power + 1e-12)


def _extract_peak_features(psd_db: np.ndarray, sample_rate_hz: float, center_freq_hz: float, top_n: int = 5):
    noise_floor_db = float(np.median(psd_db))
    threshold_db = noise_floor_db + 8.0
    candidate_indexes = np.where(psd_db >= threshold_db)[0]

    nfft = psd_db.size
    frequency_axis_hz = np.linspace(
        center_freq_hz - sample_rate_hz / 2.0,
        center_freq_hz + sample_rate_hz / 2.0,
        nfft,
        endpoint=False,
    )

    if candidate_indexes.size == 0:
        return {
            "noise_floor_db": noise_floor_db,
            "threshold_db": threshold_db,
            "peak_count": 0,
            "peaks": [],
        }

    sorted_indexes = candidate_indexes[np.argsort(psd_db[candidate_indexes])[::-1]]
    unique_indexes = []

    min_spacing = max(3, nfft // 200)
    for index in sorted_indexes:
        if all(abs(int(index) - int(existing)) >= min_spacing for existing in unique_indexes):
            unique_indexes.append(int(index))
        if len(unique_indexes) >= top_n:
            break

    peaks = []
    for index in unique_indexes:
        peaks.append(
            {
                "bin": int(index),
                "frequency_hz": float(frequency_axis_hz[index]),
                "power_db": float(psd_db[index]),
                "snr_db": float(psd_db[index] - noise_floor_db),
            }
        )

    return {
        "noise_floor_db": noise_floor_db,
        "threshold_db": threshold_db,
        "peak_count": len(peaks),
        "peaks": peaks,
    }


def process_recording(samples_path: str, metadata_path: str, output_dir: str, nfft: int = 4096):
    integrity = validate_recording_integrity(samples_path=samples_path, metadata_path=metadata_path)
    if integrity["errors"]:
        raise ValueError("; ".join(integrity["errors"]))

    with open(metadata_path, "r", encoding="utf-8") as metadata_file:
        metadata = json.load(metadata_file)

    samples = np.load(samples_path)

    sample_rate_hz = float(metadata.get("sample_rate_hz", 2_048_000))
    center_freq_hz = float(metadata.get("center_freq_hz", 100_000_000))

    psd_db = _compute_psd_db(samples, nfft=nfft)
    peak_features = _extract_peak_features(psd_db, sample_rate_hz, center_freq_hz)

    avg_power_linear = float(np.mean(np.abs(samples) ** 2))
    rms_amplitude = float(np.sqrt(np.mean(np.abs(samples) ** 2)))
    rms_db = compute_rms_db(samples)

    result = {
        "source_samples": samples_path,
        "source_metadata": metadata_path,
        "processed_at": datetime.now().isoformat(timespec="seconds"),
        "sample_count": int(samples.size),
        "nfft": int(nfft),
        "avg_power_linear": avg_power_linear,
        "rms_amplitude": rms_amplitude,
        "rms_db": rms_db,
        "sample_rate_hz": sample_rate_hz,
        "center_freq_hz": center_freq_hz,
        "gain_db": metadata.get("gain_db"),
        "duration_s": metadata.get("duration_s"),
        "device_index": metadata.get("device_index"),
        "serial": metadata.get("serial"),
        "spectrum": {
            "max_power_db": float(np.max(psd_db)),
            "min_power_db": float(np.min(psd_db)),
            "mean_power_db": float(np.mean(psd_db)),
        },
        "signal_detection": peak_features,
        "integrity_warnings": integrity["warnings"],
    }

    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(samples_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}_processed.json")

    with open(output_path, "w", encoding="utf-8") as out_file:
        json.dump(result, out_file, indent=2)

    return output_path, result


def process_all_recordings(recordings_dir: str = "data/recordings", output_subdir: str = "processed", nfft: int = 4096):
    if not os.path.isdir(recordings_dir):
        return {"processed": [], "skipped": [], "errors": [f"Directory not found: {recordings_dir}"]}

    output_dir = os.path.join(recordings_dir, output_subdir)

    processed = []
    skipped = []
    errors = []

    for filename in sorted(os.listdir(recordings_dir)):
        if not filename.endswith(".npy"):
            continue

        samples_path = os.path.join(recordings_dir, filename)
        metadata_path = find_recording_metadata_path(samples_path)

        if not metadata_path or not os.path.exists(metadata_path):
            skipped.append(f"Missing metadata for {filename}")
            continue

        integrity = validate_recording_integrity(samples_path=samples_path, metadata_path=metadata_path)
        if integrity["errors"]:
            skipped.append(f"Integrity errors for {filename}: {'; '.join(integrity['errors'])}")
            continue
        if integrity["warnings"]:
            skipped.append(f"Integrity warnings for {filename}: {'; '.join(integrity['warnings'])}")

        try:
            output_path, _ = process_recording(
                samples_path=samples_path,
                metadata_path=metadata_path,
                output_dir=output_dir,
                nfft=nfft,
            )
            processed.append(output_path)
        except Exception as error:
            errors.append(f"{filename}: {error}")

    return {
        "processed": processed,
        "skipped": skipped,
        "errors": errors,
        "output_dir": output_dir,
    }
