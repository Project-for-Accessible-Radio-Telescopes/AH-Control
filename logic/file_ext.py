import json
import os
from datetime import datetime


AHF_EXTENSION = ".ahf"
AHF_SCHEMA_VERSION = 2


def normalize_project_path(path):
    if not path:
        raise ValueError("Project path cannot be empty")

    root, ext = os.path.splitext(path)
    if ext.lower() == AHF_EXTENSION:
        return path
    return f"{root}{AHF_EXTENSION}"


def _clean_string_list(values):
    cleaned = []
    seen = set()
    for value in values or []:
        if not isinstance(value, str):
            continue
        text = value.strip()
        if not text:
            continue
        if text in seen:
            continue
        seen.add(text)
        cleaned.append(text)
    return cleaned


def _paths_to_relative(paths, project_dir):
    relative_paths = []
    for raw_path in _clean_string_list(paths):
        normalized = os.path.normpath(raw_path)
        if os.path.isabs(normalized):
            try:
                normalized = os.path.relpath(normalized, project_dir)
            except Exception:
                normalized = raw_path
        relative_paths.append(normalized)
    return _clean_string_list(relative_paths)


def _paths_to_absolute(paths, project_dir):
    absolute_paths = []
    for raw_path in _clean_string_list(paths):
        normalized = os.path.normpath(raw_path)
        if not os.path.isabs(normalized):
            normalized = os.path.abspath(os.path.join(project_dir, normalized))
        absolute_paths.append(normalized)
    return _clean_string_list(absolute_paths)


def build_session_payload(settings, log_entries, spreadsheet_paths):
    payload = {
        "format": "AHF",
        "schema_version": AHF_SCHEMA_VERSION,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "settings": settings or {},
        "log_entries": _clean_string_list(log_entries),
        "open_spreadsheets": _clean_string_list(spreadsheet_paths),
        "paths": {
            "open_spreadsheets": "relative_to_project",
        },
    }
    return payload


def validate_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError("Invalid AHF file: expected a JSON object")

    if payload.get("format") != "AHF":
        raise ValueError("Invalid AHF file: missing format marker")

    schema_version = payload.get("schema_version")
    if not isinstance(schema_version, int):
        raise ValueError("Invalid AHF file: schema_version must be an integer")

    if schema_version > AHF_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported AHF schema version {schema_version}. "
            f"This app supports up to version {AHF_SCHEMA_VERSION}."
        )

    if not isinstance(payload.get("settings", {}), dict):
        raise ValueError("Invalid AHF file: settings must be an object")

    if not isinstance(payload.get("log_entries", []), list):
        raise ValueError("Invalid AHF file: log_entries must be an array")

    if not isinstance(payload.get("open_spreadsheets", []), list):
        raise ValueError("Invalid AHF file: open_spreadsheets must be an array")

    for item in payload.get("log_entries", []):
        if not isinstance(item, str):
            raise ValueError("Invalid AHF file: log_entries items must be strings")

    for item in payload.get("open_spreadsheets", []):
        if not isinstance(item, str):
            raise ValueError("Invalid AHF file: open_spreadsheets items must be strings")


def write_ahf_file(path, payload):
    """Write a validated session payload to disk as .ahf JSON."""
    project_path = normalize_project_path(path)
    validate_payload(payload)

    payload_to_store = dict(payload)
    project_dir = os.path.dirname(os.path.abspath(project_path))
    payload_to_store["open_spreadsheets"] = _paths_to_relative(
        payload.get("open_spreadsheets", []),
        project_dir,
    )
    payload_to_store["log_entries"] = _clean_string_list(payload.get("log_entries", []))
    payload_to_store["schema_version"] = AHF_SCHEMA_VERSION
    payload_to_store["saved_at"] = datetime.now().isoformat(timespec="seconds")

    with open(project_path, "w", encoding="utf-8") as f:
        json.dump(payload_to_store, f, indent=2)

    return project_path


def read_ahf_file(path):
    if not path:
        raise ValueError("Project path cannot be empty")

    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    validate_payload(payload)

    project_dir = os.path.dirname(os.path.abspath(path))
    normalized_payload = dict(payload)
    normalized_payload["log_entries"] = _clean_string_list(payload.get("log_entries", []))
    normalized_payload["open_spreadsheets"] = _paths_to_absolute(
        payload.get("open_spreadsheets", []),
        project_dir,
    )
    return normalized_payload