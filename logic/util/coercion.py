"""Type coercion and conversion utilities."""
import os
import sys


def coerce_bool(value, default):
    """Coerce a value to boolean.
    
    Args:
        value: Value to coerce (bool, str, or other)
        default: Default value if coercion fails
        
    Returns:
        Boolean value
    """
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
    """Coerce a value to integer with optional bounds checking.
    
    Args:
        value: Value to coerce
        default: Default value if coercion fails or bounds violated
        min_value: Minimum allowed value (optional)
        max_value: Maximum allowed value (optional)
        
    Returns:
        Integer value
    """
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
    """Coerce a value to float with optional bounds checking.
    
    Args:
        value: Value to coerce
        default: Default value if coercion fails or bounds violated
        min_value: Minimum allowed value (optional)
        max_value: Maximum allowed value (optional)
        
    Returns:
        Float value
    """
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
    """Resolve the settings file path, handling frozen app scenarios.
    
    Args:
        settings_path: User-provided settings path (optional)
        
    Returns:
        Absolute path to settings file
    """
    if settings_path is None:
        return _default_settings_path()

    if os.path.isabs(settings_path):
        return settings_path

    if getattr(sys, "frozen", False) and settings_path.replace("\\", "/") == "data/settings.json":
        return _default_settings_path()

    return settings_path


def _default_settings_path():
    """Get the default settings path based on environment (dev vs frozen app)."""
    if getattr(sys, "frozen", False):
        app_support = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "PARTApp")
        return os.path.join(app_support, "settings.json")
    return os.path.join("data", "settings.json")
