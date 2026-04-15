import numpy as np
from rtlsdr import RtlSdr

import matplotlib.pyplot as plt

def scan_frequency_range(start_freq, end_freq, num_samples=100):
    """
    Connect to RTL-SDR and create a frequency graph for the specified range.
    
    Args:
        start_freq: Start frequency in Hz
        end_freq: End frequency in Hz
        num_samples: Number of frequency points to sample
    """
    sdr = RtlSdr()
    
    # Set SDR parameters
    sdr.sample_rate = 2.4e6  # 2.4 MHz sample rate
    sdr.gain = 'auto'
    
    frequencies = np.linspace(start_freq, end_freq, num_samples)
    power_levels = []
        
    for freq in frequencies:
        sdr.center_freq = int(freq)
        # Capture samples and compute power
        samples = sdr.read_samples(256 * 1024)
        power = np.mean(np.abs(samples) ** 2)
        power_levels.append(10 * np.log10(power))
        
    sdr.close()
    
    # Plot results
    plt.figure(figsize=(12, 6))
    plt.plot(frequencies / 1e9, power_levels)
    plt.xlabel('Frequency (GHz)')
    plt.ylabel('Power (dB)')
    plt.title('RTL-SDR Frequency Scan: 1.2 - 1.7 GHz')
    plt.grid(True)
    plt.show()

if __name__ == "__main__":
    scan_frequency_range(1.2e9, 1.7e9)