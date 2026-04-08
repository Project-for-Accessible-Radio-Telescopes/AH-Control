"""
Real WiFi network scanning module.
Detects actual WiFi networks on the system and maps them to frequency/power spectrum.
"""

import subprocess
import platform
import numpy as np
from typing import List, Dict, Optional


# WiFi channel to frequency mapping (MHz)
WIFI_2_4GHZ_CHANNELS = {
    1: 2412, 2: 2417, 3: 2422, 4: 2427, 5: 2432, 6: 2437, 7: 2442,
    8: 2447, 9: 2452, 10: 2457, 11: 2462, 12: 2467, 13: 2472, 14: 2484
}

WIFI_5GHZ_CHANNELS = {
    36: 5180, 40: 5200, 44: 5220, 48: 5240,
    52: 5260, 56: 5280, 60: 5300, 64: 5320,
    100: 5500, 104: 5520, 108: 5540, 112: 5560, 116: 5580, 120: 5600, 124: 5620, 128: 5640,
    132: 5660, 136: 5680, 140: 5700, 144: 5720,
    149: 5745, 153: 5765, 157: 5785, 161: 5805, 165: 5825, 169: 5845, 173: 5865, 177: 5885
}


def scan_wifi_networks() -> List[Dict]:
    """
    Scan for WiFi networks using system commands.
    Returns list of networks with SSID, BSSID, signal strength, channel.
    """
    system = platform.system()
    
    if system == "Darwin":
        return _scan_wifi_macos()
    elif system == "Linux":
        return _scan_wifi_linux()
    elif system == "Windows":
        return _scan_wifi_windows()
    else:
        raise RuntimeError(f"WiFi scanning not supported on {system}")


def _scan_wifi_macos() -> List[Dict]:
    """Scan WiFi on macOS using airport command."""
    try:
        airport_path = '/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport'
        result = subprocess.run(
            [airport_path, '-s'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        networks = []
        for line in result.stdout.strip().split('\n')[1:]:
            parts = line.split()
            if len(parts) >= 7:
                try:
                    networks.append({
                        'ssid': parts[0],
                        'bssid': parts[1],
                        'rssi_dbm': int(parts[2]),  # Signal strength dBm (negative value)
                        'channel': int(parts[3]),
                        'security': ' '.join(parts[6:]).strip()
                    })
                except (ValueError, IndexError):
                    continue
        
        return networks
    except FileNotFoundError:
        raise RuntimeError("airport command not found. Try using Linux or Windows.")
    except subprocess.TimeoutExpired:
        raise RuntimeError("WiFi scan timed out")
    except Exception as e:
        raise RuntimeError(f"macOS WiFi scan failed: {e}")


def _scan_wifi_linux() -> List[Dict]:
    """Scan WiFi on Linux using nmcli or iwlist."""
    try:
        # Try nmcli first (NetworkManager)
        result = subprocess.run(
            ['nmcli', 'dev', 'wifi', 'list'],
            capture_output=True,
            text=True,
            timeout=15
        )
        
        if result.returncode == 0:
            networks = []
            for line in result.stdout.strip().split('\n')[1:]:
                parts = line.split()
                if len(parts) >= 8:
                    try:
                        # Signal strength is percentage (0-100), convert to dBm estimate
                        signal_percent = int(parts[5])
                        rssi_dbm = -100 + (signal_percent * 0.4)  # Convert to approximate dBm
                        
                        networks.append({
                            'ssid': parts[0],
                            'bssid': parts[1],
                            'rssi_dbm': int(rssi_dbm),
                            'channel': int(parts[3]),
                            'security': ' '.join(parts[7:]).strip()
                        })
                    except (ValueError, IndexError):
                        continue
            
            return networks
        else:
            raise RuntimeError("nmcli command failed")
    
    except FileNotFoundError:
        # Fall back to iw command
        try:
            result = subprocess.run(
                ['sudo', 'iw', 'dev'],
                capture_output=True,
                text=True,
                timeout=10
            )
            # This is more complex to parse, return empty for now
            raise RuntimeError("iw scanning requires monitor mode and root access")
        except Exception as e:
            raise RuntimeError(f"Linux WiFi scan failed: {e}")


def _scan_wifi_windows() -> List[Dict]:
    """Scan WiFi on Windows using netsh."""
    try:
        result = subprocess.run(
            ['netsh', 'wlan', 'show', 'networks', 'mode=Bssid'],
            capture_output=True,
            text=True,
            timeout=15
        )
        
        networks = []
        lines = result.stdout.split('\n')
        current_ssid = None
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            if line.startswith('SSID'):
                parts = line.split(':')
                if len(parts) >= 2:
                    current_ssid = parts[1].strip()
            
            if 'Signal' in line and current_ssid:
                parts = line.split(':')
                if len(parts) >= 2:
                    try:
                        signal_percent = int(parts[1].strip().rstrip('%'))
                        rssi_dbm = -100 + (signal_percent * 0.4)
                        
                        networks.append({
                            'ssid': current_ssid,
                            'bssid': 'unknown',
                            'rssi_dbm': int(rssi_dbm),
                            'channel': 0,  # Channel info not easily available
                            'security': 'unknown'
                        })
                        current_ssid = None
                    except ValueError:
                        pass
        
        return networks
    except FileNotFoundError:
        raise RuntimeError("netsh command not found")
    except Exception as e:
        raise RuntimeError(f"Windows WiFi scan failed: {e}")


def convert_networks_to_spectrum(networks: List[Dict], sample_rate: float, 
                                  center_freq: float, nfft: int) -> tuple:
    """
    Convert scanned WiFi networks to simulated power spectrum.
    
    Parameters:
    -----------
    networks : List[Dict]
        List of networks from scan_wifi_networks()
    sample_rate : float
        Sample rate in Hz
    center_freq : float
        Center frequency in Hz
    nfft : int
        FFT size / number of frequency bins
    
    Returns:
    --------
    tuple
        (frequencies_mhz, power_spectrum)
    """
    from scipy.fft import fftshift
    from scipy import signal
    
    # Initialize spectrum with thermal noise floor
    noise_floor_dbm = -90.0
    noise_linear = 10 ** (noise_floor_dbm / 20)
    
    samples = noise_linear * (np.random.randn(nfft) + 1j * np.random.randn(nfft))
    
    # Add peaks for detected networks with enhanced visibility
    for network in networks:
        # Get frequency from channel
        freq_hz = None
        if network.get('channel'):
            channel = network['channel']
            if channel <= 14:
                freq_hz = WIFI_2_4GHZ_CHANNELS.get(channel) * 1_000_000  # Convert MHz to Hz
            else:
                freq_hz = WIFI_5GHZ_CHANNELS.get(channel) * 1_000_000
        
        # If no channel, default to 2.4 GHz
        if not freq_hz:
            freq_hz = 2_450_000_000
        
        # Check if frequency is within observing band
        if abs(freq_hz - center_freq) > sample_rate / 2:
            continue
        
        # Get signal strength
        rssi_dbm = network.get('rssi_dbm', -80)
        
        # Convert dBm to linear power (this is the actual power detected)
        # Stronger signal = lower dBm (more negative means weaker)
        # Signal range typically -30 (strong) to -100 (weak) dBm
        signal_strength_linear = 10 ** (rssi_dbm / 10)  # Convert dBm to linear
        
        # Amplify for visibility
        amplitude = np.sqrt(signal_strength_linear) * 5  # 5x amplification for visibility
        
        # Calculate position in sample array
        freq_offset = freq_hz - center_freq
        bin_normalized = freq_offset / sample_rate
        bin_index = int((bin_normalized + 0.5) * nfft)
        
        if 0 <= bin_index < nfft:
            # Create wider, more visible peaks (WiFi channels are ~20-40 MHz wide)
            peak_width = max(20, nfft // 50)  # Increased width
            start = max(0, bin_index - peak_width)
            end = min(nfft, bin_index + peak_width)
            
            # Create sharp Gaussian peak
            peak_pos = np.arange(start, end, dtype=float)
            sigma = peak_width / 2.5
            gaussian = np.exp(-((peak_pos - bin_index) ** 2) / (2 * sigma ** 2))
            
            # Add WiFi-like modulation (realistic, not pure sine)
            phase = np.random.rand(end - start) * 2 * np.pi
            modulation = np.exp(1j * phase)
            
            samples[start:end] += amplitude * gaussian * modulation
    
    # Compute Welch PSD with improved resolution
    frequencies, pxx = signal.welch(
        samples, 
        fs=sample_rate, 
        nperseg=nfft,
        window='hann'
    )
    
    # Convert to dBm for better visualization of peaks
    pxx_dbm = 10 * np.log10(pxx + 1e-12)
    
    frequencies_mhz = (frequencies + center_freq) / 1e6
    
    # Apply fftshift to center the spectrum
    frequencies_mhz = fftshift(frequencies_mhz)
    pxx_dbm = fftshift(pxx_dbm)
    
    return frequencies_mhz, pxx_dbm


def networks_to_dataframe(networks: List[Dict]) -> str:
    """Convert network list to pretty-printed table."""
    if not networks:
        return "No WiFi networks detected"
    
    lines = ["WiFi Networks Detected:"]
    lines.append("-" * 80)
    lines.append(f"{'SSID':<32} {'BSSID':<17} {'Channel':<8} {'Signal (dBm)':<15}")
    lines.append("-" * 80)
    
    for net in networks:
        ssid = net.get('ssid', 'Hidden')[:32]
        bssid = net.get('bssid', 'unknown')
        channel = str(net.get('channel', '?'))
        rssi = str(net.get('rssi_dbm', '?'))
        
        lines.append(f"{ssid:<32} {bssid:<17} {channel:<8} {rssi:<15}")
    
    return '\n'.join(lines)
