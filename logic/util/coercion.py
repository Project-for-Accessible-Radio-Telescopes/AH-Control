"""Type coercion and conversion utilities."""
import os
import sys


def coerce_bool(value, default):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"0", "false", "no", "off"}:
            return False
    return default


def coerce_int(value, default, min_value=None, max_value=None):
    try:
        parsed = int(value)
    except Exception:
        return default
    if min_value is not None and parsed < min_value:
        return default
    if max_value is not None and parsed > max_value:
        return default
    return parsed


def coerce_float(value, default, min_value=None, max_value=None):
    try:
        parsed = float(value)
    except Exception:
        return default
    if min_value is not None and parsed < min_value:
        return default
    if max_value is not None and parsed > max_value:
        return default
    return parsed


def resolve_settings_path(settings_path=None):
    if settings_path is None:
        return _default_settings_path()

    if os.path.isabs(settings_path):
        return settings_path

    if getattr(sys, "frozen", False) and settings_path.replace("\\", "/") == "data/settings.json":
        return _default_settings_path()

    return settings_path


def _default_settings_path():
    if getattr(sys, "frozen", False):
        app_support = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "PARTApp")
        return os.path.join(app_support, "settings.json")
    return os.path.join("data", "settings.json")
