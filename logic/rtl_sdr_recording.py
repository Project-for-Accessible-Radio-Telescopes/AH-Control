import ctypes
import multiprocessing as mp
import os
import queue as queue_module

import numpy as np


_RTLSDR_CLASS = None
_RTLSDR_IMPORT_ERROR = None


def _preload_rtlsdr_native_libraries():
    if os.name != "posix":
        return

    candidates = [
        "/opt/homebrew/opt/libusb/lib/libusb-1.0.0.dylib",
        "/opt/homebrew/opt/libusb/lib/libusb-1.0.dylib",
        "/usr/local/opt/libusb/lib/libusb-1.0.0.dylib",
        "/usr/local/opt/libusb/lib/libusb-1.0.dylib",
        "/opt/homebrew/lib/libusb-1.0.0.dylib",
        "/opt/homebrew/lib/libusb-1.0.dylib",
        "/usr/local/lib/libusb-1.0.0.dylib",
        "/usr/local/lib/libusb-1.0.dylib",
        "/opt/homebrew/lib/librtlsdr.dylib",
        "/usr/local/lib/librtlsdr.dylib",
    ]

    for path in candidates:
        if not os.path.exists(path):
            continue
        try:
            ctypes.CDLL(path, mode=ctypes.RTLD_GLOBAL)
        except Exception:
            continue


def get_rtlsdr_class():
    global _RTLSDR_CLASS
    global _RTLSDR_IMPORT_ERROR

    if _RTLSDR_CLASS is not None:
        return _RTLSDR_CLASS

    try:
        _preload_rtlsdr_native_libraries()
        from rtlsdr import RtlSdr as rtl_sdr_class

        _RTLSDR_CLASS = rtl_sdr_class
        _RTLSDR_IMPORT_ERROR = None
        return _RTLSDR_CLASS
    except Exception as error:
        _RTLSDR_IMPORT_ERROR = error
        return None


def get_rtlsdr_import_error():
    return _RTLSDR_IMPORT_ERROR


def detect_rtl_sdr_devices():
    rtlsdr_class = get_rtlsdr_class()
    if rtlsdr_class is None:
        return []

    devices = []
    serials = []

    if hasattr(rtlsdr_class, "get_device_serial_addresses"):
        try:
            serials = rtlsdr_class.get_device_serial_addresses() or []
        except Exception:
            serials = []

    if serials:
        for index_guess, serial in enumerate(serials):
            index = index_guess
            if hasattr(rtlsdr_class, "get_device_index_by_serial"):
                try:
                    index = rtlsdr_class.get_device_index_by_serial(serial)
                except Exception:
                    index = index_guess
            devices.append(
                {
                    "index": int(index),
                    "serial": str(serial),
                    "label": f"Device {index} (serial: {serial})",
                }
            )
        return devices

    if hasattr(rtlsdr_class, "get_device_count"):
        try:
            count = int(rtlsdr_class.get_device_count())
            for index in range(count):
                devices.append(
                    {
                        "index": index,
                        "serial": "unknown",
                        "label": f"Device {index}",
                    }
                )
        except Exception:
            return []

    return devices


def _compute_rms_db(samples, epsilon=1e-12):
    values = np.asarray(samples)
    if values.ndim != 1:
        values = values.reshape(-1)
    if values.size == 0:
        return float("nan")

    rms = float(np.sqrt(np.mean(np.abs(values) ** 2)))
    return float(20.0 * np.log10(rms + float(epsilon)))


def _rtlsdr_capture_worker(
    device_index,
    center_freq_hz,
    sample_rate_hz,
    gain_db,
    total_samples,
    chunk_size,
    result_queue,
):
    sdr = None
    try:
        from rtlsdr import RtlSdr as rtl_sdr_class

        requested_samples = int(total_samples)
        active_chunk_size = max(8_192, int(chunk_size))

        sdr = rtl_sdr_class(device_index=int(device_index))
        sdr.sample_rate = float(sample_rate_hz)
        sdr.center_freq = float(center_freq_hz)
        sdr.gain = float(gain_db)

        if hasattr(sdr, "reset_buffer"):
            try:
                sdr.reset_buffer()
            except Exception:
                pass

        chunks = []
        collected = 0
        consecutive_overflows = 0
        max_consecutive_overflows = 8

        while collected < requested_samples:
            remaining = requested_samples - collected
            read_now = min(active_chunk_size, remaining)

            try:
                part = sdr.read_samples(read_now)
                consecutive_overflows = 0
            except Exception as read_error:
                read_error_text = str(read_error).lower()
                is_overflow = "overflow" in read_error_text or "libusb_error_overflow" in read_error_text
                if not is_overflow:
                    raise

                consecutive_overflows += 1
                active_chunk_size = max(8_192, active_chunk_size // 2)
                if hasattr(sdr, "reset_buffer"):
                    try:
                        sdr.reset_buffer()
                    except Exception:
                        pass

                if consecutive_overflows <= max_consecutive_overflows:
                    continue

                raise RuntimeError(
                    "RTL-SDR USB overflow persisted during capture. "
                    "Try a lower sample rate and a direct USB port."
                ) from read_error

            if part is None:
                continue

            arr = np.asarray(part, dtype=np.complex64)
            if arr.size == 0:
                continue

            chunks.append(arr)
            collected += int(arr.size)

        if not chunks:
            raise RuntimeError("No samples were read from RTL-SDR")

        samples = np.concatenate(chunks)
        if samples.size > requested_samples:
            samples = samples[:requested_samples]

        result_queue.put(
            {
                "ok": True,
                "samples": np.asarray(samples, dtype=np.complex64),
            }
        )
    except Exception as error:
        result_queue.put(
            {
                "ok": False,
                "error": str(error),
            }
        )
    finally:
        if sdr is not None:
            try:
                sdr.close()
            except Exception:
                pass


def capture_rtl_sdr_samples(
    device_index,
    center_freq_hz,
    sample_rate_hz,
    gain_db,
    num_samples,
    *,
    settings=None,
    chunk_size=None,
    on_progress=None,
):
    if get_rtlsdr_class() is None:
        raise RuntimeError("RTL-SDR library is unavailable")

    cfg = settings or {}
    max_center_freq_hz = float(cfg.get("rtlsdr_max_center_freq_hz", 1_766_000_000.0))
    if float(center_freq_hz) > max_center_freq_hz:
        raise RuntimeError(
            "Center frequency is above supported RTL-SDR tuner range. "
            f"Use <= {int(max_center_freq_hz)} Hz (about 1.7 GHz)."
        )

    total_samples = int(num_samples)
    active_chunk_size = int(chunk_size or min(131_072, total_samples))
    if active_chunk_size <= 0:
        active_chunk_size = total_samples
    active_chunk_size = max(8_192, active_chunk_size)

    fallback_rates = [float(sample_rate_hz)]
    minimum_fallback_rate_hz = 1_000_000.0
    for candidate_rate in [float(sample_rate_hz) / 2.0, float(sample_rate_hz) / 4.0]:
        if candidate_rate >= minimum_fallback_rate_hz and candidate_rate not in fallback_rates:
            fallback_rates.append(candidate_rate)

    attempt_errors = []
    last_failure = "Unknown capture error"

    for attempt_rate_hz in fallback_rates:
        context = mp.get_context("spawn")
        result_queue = context.Queue(maxsize=1)
        process = context.Process(
            target=_rtlsdr_capture_worker,
            args=(
                int(device_index),
                float(center_freq_hz),
                float(attempt_rate_hz),
                float(gain_db),
                int(total_samples),
                int(active_chunk_size),
                result_queue,
            ),
            daemon=True,
        )

        expected_seconds = max(8.0, (float(total_samples) / max(float(attempt_rate_hz), 1.0)) * 4.0)
        process.start()
        process.join(timeout=expected_seconds)

        if process.is_alive():
            process.terminate()
            process.join(timeout=2.0)
            last_failure = "Capture worker timed out"
            attempt_errors.append(f"{int(attempt_rate_hz)} Hz: {last_failure}")
            continue

        if process.exitcode not in (0, None):
            last_failure = f"Capture worker crashed with exit code {process.exitcode}"
            attempt_errors.append(f"{int(attempt_rate_hz)} Hz: {last_failure}")
            continue

        try:
            result = result_queue.get_nowait()
        except queue_module.Empty:
            last_failure = "Capture worker produced no result"
            attempt_errors.append(f"{int(attempt_rate_hz)} Hz: {last_failure}")
            continue

        if result.get("ok"):
            samples = np.asarray(result.get("samples", []), dtype=np.complex64)
            if samples.size == 0:
                last_failure = "Capture worker returned empty data"
                attempt_errors.append(f"{int(attempt_rate_hz)} Hz: {last_failure}")
                continue

            if on_progress is not None:
                try:
                    on_progress(
                        {
                            "samples_collected": int(samples.size),
                            "samples_total": int(total_samples),
                            "chunk_rms_db": _compute_rms_db(samples),
                        }
                    )
                except Exception:
                    pass

            return samples

        error_text = str(result.get("error", "RTL-SDR capture failed"))
        lowered_error = error_text.lower()
        if "-9" in error_text or "i2c" in lowered_error:
            raise RuntimeError(
                "RTL-SDR communication failed (I2C/USB error -9). "
                "Try unplugging/replugging the dongle, use a direct USB port, "
                "close other SDR apps, and retry."
            )

        last_failure = error_text or "RTL-SDR capture failed"
        attempt_errors.append(f"{int(attempt_rate_hz)} Hz: {error_text}")

    summary = " | ".join(attempt_errors[:3]) if attempt_errors else last_failure
    raise RuntimeError(
        "RTL-SDR capture failed after retries. "
        f"Attempt summary: {summary}"
    )
