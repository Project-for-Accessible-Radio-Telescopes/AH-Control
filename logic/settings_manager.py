import json
import os


DEFAULT_SETTINGS = {
    "version": "0.1.0",
    "language": "en",
    "theme": "light",
    "font_size": 10,
    "capture_default_sample_rate_hz": 2_048_000.0,
    "capture_default_center_freq_hz": 100_000_000.0,
    "capture_default_gain_db": 20.0,
    "capture_default_duration_s": 2.0,
    "capture_sample_cap": 2_500_000,
    "analysis_nfft": 4096,
    "analysis_max_segments": 350,
    "analysis_max_preview_samples": 8_000_000,
    "analysis_show_frequency_overlays": False,
    "quick_check_default_duration_s": 0.35,
    "quick_check_max_duration_s": 2.0,
    "network_timeout_s": 6,
    "local_info_use_ip_fallback": True,
}


def _coerce_bool(value, default):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"0", "false", "no", "off"}:
            return False
    return default


def _coerce_int(value, default, min_value=None, max_value=None):
    try:
        parsed = int(value)
    except Exception:
        return default
    if min_value is not None and parsed < min_value:
        return default
    if max_value is not None and parsed > max_value:
        return default
    return parsed


def _coerce_float(value, default, min_value=None, max_value=None):
    try:
        parsed = float(value)
    except Exception:
        return default
    if min_value is not None and parsed < min_value:
        return default
    if max_value is not None and parsed > max_value:
        return default
    return parsed


def merge_settings(raw_settings):
    merged = dict(DEFAULT_SETTINGS)
    if isinstance(raw_settings, dict):
        merged.update(raw_settings)

    merged["theme"] = str(merged.get("theme", DEFAULT_SETTINGS["theme"])).lower()
    if merged["theme"] not in {"light", "dark"}:
        merged["theme"] = DEFAULT_SETTINGS["theme"]

    merged["font_size"] = _coerce_int(merged.get("font_size"), DEFAULT_SETTINGS["font_size"], 8, 20)

    merged["capture_default_sample_rate_hz"] = _coerce_float(
        merged.get("capture_default_sample_rate_hz"),
        DEFAULT_SETTINGS["capture_default_sample_rate_hz"],
        1_000,
        3_200_000,
    )
    merged["capture_default_center_freq_hz"] = _coerce_float(
        merged.get("capture_default_center_freq_hz"),
        DEFAULT_SETTINGS["capture_default_center_freq_hz"],
        1_000,
        3_000_000_000,
    )
    merged["capture_default_gain_db"] = _coerce_float(
        merged.get("capture_default_gain_db"),
        DEFAULT_SETTINGS["capture_default_gain_db"],
        -10,
        60,
    )
    merged["capture_default_duration_s"] = _coerce_float(
        merged.get("capture_default_duration_s"),
        DEFAULT_SETTINGS["capture_default_duration_s"],
        0.1,
        120,
    )
    merged["capture_sample_cap"] = _coerce_int(
        merged.get("capture_sample_cap"),
        DEFAULT_SETTINGS["capture_sample_cap"],
        1000,
        20_000_000,
    )

    merged["analysis_nfft"] = _coerce_int(merged.get("analysis_nfft"), DEFAULT_SETTINGS["analysis_nfft"], 256, 32768)
    merged["analysis_max_segments"] = _coerce_int(
        merged.get("analysis_max_segments"),
        DEFAULT_SETTINGS["analysis_max_segments"],
        10,
        5000,
    )
    merged["analysis_max_preview_samples"] = _coerce_int(
        merged.get("analysis_max_preview_samples"),
        DEFAULT_SETTINGS["analysis_max_preview_samples"],
        100_000,
        100_000_000,
    )
    merged["analysis_show_frequency_overlays"] = _coerce_bool(
        merged.get("analysis_show_frequency_overlays"),
        DEFAULT_SETTINGS["analysis_show_frequency_overlays"],
    )

    merged["quick_check_default_duration_s"] = _coerce_float(
        merged.get("quick_check_default_duration_s"),
        DEFAULT_SETTINGS["quick_check_default_duration_s"],
        0.05,
        5.0,
    )
    merged["quick_check_max_duration_s"] = _coerce_float(
        merged.get("quick_check_max_duration_s"),
        DEFAULT_SETTINGS["quick_check_max_duration_s"],
        0.1,
        10.0,
    )

    merged["network_timeout_s"] = _coerce_int(
        merged.get("network_timeout_s"),
        DEFAULT_SETTINGS["network_timeout_s"],
        2,
        30,
    )
    merged["local_info_use_ip_fallback"] = _coerce_bool(
        merged.get("local_info_use_ip_fallback"),
        DEFAULT_SETTINGS["local_info_use_ip_fallback"],
    )

    merged["version"] = str(merged.get("version", DEFAULT_SETTINGS["version"]))
    merged["language"] = str(merged.get("language", DEFAULT_SETTINGS["language"]))

    return merged


def load_settings_file(settings_path="data/settings.json"):
    raw = {}
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception:
            raw = {}

    merged = merge_settings(raw)
    save_settings_file(merged, settings_path=settings_path)
    return merged


def save_settings_file(settings, settings_path="data/settings.json"):
    merged = merge_settings(settings)
    os.makedirs(os.path.dirname(settings_path) or ".", exist_ok=True)
    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2)
    return merged
