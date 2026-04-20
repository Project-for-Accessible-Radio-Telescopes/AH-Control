"""Signal processing and spectrum analysis utilities."""
import numpy as np
from scipy import signal


def compute_rms_db(samples: np.ndarray, epsilon: float = 1e-12) -> float:
    """Compute RMS amplitude in dBFS-like scale for complex or real samples.
    
    Args:
        samples: Array of complex or real samples
        epsilon: Small value to prevent log(0)
        
    Returns:
        RMS power in dB
    """
    values = np.asarray(samples)
    if values.ndim != 1:
        values = values.reshape(-1)
    if values.size == 0:
        raise ValueError("Cannot compute RMS from empty sample array")

    rms = float(np.sqrt(np.mean(np.abs(values) ** 2)))
    return float(20.0 * np.log10(rms + float(epsilon)))


def compute_power_spectrum_welch(samples: np.ndarray, sample_rate: float, centre_freq: float, 
                                  n_per_seg: int, n_segs: int) -> tuple:
    """Compute power spectrum using Welch's method with FFT shift correction.
    
    The Welch method provides better frequency resolution by dividing samples
    into overlapping segments, computing FFT of each, and averaging the results.
    
    Args:
        samples: Complex or real samples from SDR
        sample_rate: Sample rate in Hz
        centre_freq: Center frequency of the SDR in Hz
        n_per_seg: Number of samples per segment (FFT size)
        n_segs: Number of segments to average over (not used directly by scipy)
        
    Returns:
        Tuple of (frequencies_mhz, power_spectrum)
            - frequencies_mhz: Frequency axis in MHz, centered at centre_freq
            - power_spectrum: Power spectral density (PSD) in linear scale
            
    Notes:
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
    """Read samples directly from SDR and compute power spectrum using Welch's method.
    
    This is a live variant that reads multiple segments from the SDR device and averages
    the resulting power spectra, providing better noise floor estimates.
    
    Args:
        sdr: RTL-SDR device object (already configured with sample_rate and center_freq)
        sample_rate: Sample rate in Hz (should match sdr.sample_rate)
        centre_freq: Center frequency in Hz (should match sdr.center_freq)
        n_per_seg: Samples per segment (FFT size)
        n_segs: Number of segments to read and average
        bias_tee: Whether to enable bias tee (default: True)
        
    Returns:
        Tuple of (frequencies_mhz, power_spectrum)
    """
    if bias_tee:
        sdr.set_bias_tee(True)
    
    all_powers = []
    
    for _ in range(n_segs):
        samples = sdr.read_samples(n_per_seg)
        _, pxx = compute_power_spectrum_welch(samples, sample_rate, centre_freq, n_per_seg, 1)
        all_powers.append(pxx)
    
    if bias_tee:
        sdr.set_bias_tee(False)
    
    # Average the power spectra
    frequencies_mhz, _ = compute_power_spectrum_welch(
        sdr.read_samples(n_per_seg), sample_rate, centre_freq, n_per_seg, 1
    )
    averaged_power = np.mean(all_powers, axis=0)
    
    return frequencies_mhz, averaged_power


def compute_psd_db(samples: np.ndarray, nfft: int = 4096) -> np.ndarray:
    """Compute power spectral density in dB from samples.
    
    Args:
        samples: Array of samples
        nfft: FFT size
        
    Returns:
        PSD in dB scale
    """
    if samples.size == 0:
        raise ValueError("Cannot compute PSD from empty sample array")
    
    samples = np.asarray(samples)
    freqs, pxx = signal.welch(samples, fs=1.0, nperseg=nfft, return_onesided=False)
    pxx_db = 10.0 * np.log10(pxx + 1e-12)
    return np.fft.fftshift(pxx_db)


def extract_peak_features(psd_db: np.ndarray, sample_rate_hz: float, center_freq_hz: float, top_n: int = 5):
    """Extract top N peak frequency features from a PSD.
    
    Args:
        psd_db: Power spectral density in dB
        sample_rate_hz: Sample rate in Hz
        center_freq_hz: Center frequency in Hz
        top_n: Number of top peaks to return
        
    Returns:
        List of dicts with keys: frequency_mhz, power_db
    """
    if psd_db.size == 0:
        return []
    
    psd_db = np.asarray(psd_db)
    
    # Find peaks
    peaks, properties = signal.find_peaks(psd_db, height=0)
    if len(peaks) == 0:
        peaks = [np.argmax(psd_db)]
    
    # Sort by power
    heights = properties.get('peak_heights', psd_db[peaks])
    top_indices = peaks[np.argsort(heights)[-top_n:]][::-1]
    
    features = []
    for idx in top_indices:
        freq_offset = (idx - len(psd_db) // 2) * (sample_rate_hz / len(psd_db))
        frequency_mhz = (center_freq_hz + freq_offset) / 1e6
        power_db = float(psd_db[idx])
        features.append({
            "frequency_mhz": frequency_mhz,
            "power_db": power_db,
        })
    
    return features


def build_frequency_axis_mhz(nfft, sample_rate_hz, center_freq_hz):
    """Build a frequency axis in MHz for spectral analysis.
    
    Args:
        nfft: FFT size
        sample_rate_hz: Sample rate in Hz
        center_freq_hz: Center frequency in Hz
        
    Returns:
        np.ndarray of frequencies in MHz
    """
    freq_hz = np.fft.fftshift(
        np.fft.fftfreq(nfft, 1.0 / sample_rate_hz)
    )
    return (freq_hz + center_freq_hz) / 1e6
