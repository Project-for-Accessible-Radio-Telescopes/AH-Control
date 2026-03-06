import json
import os
from datetime import datetime


AHF_EXTENSION = ".ahf"
AHF_SCHEMA_VERSION = 1


def normalize_project_path(path):
    if not path:
        raise ValueError("Project path cannot be empty")

    root, ext = os.path.splitext(path)
    if ext.lower() == AHF_EXTENSION:
        return path
    return f"{root}{AHF_EXTENSION}"


def build_session_payload(settings, log_entries, spreadsheet_paths):
    payload = {
        "format": "AHF",
        "schema_version": AHF_SCHEMA_VERSION,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "settings": settings or {},
        "log_entries": list(log_entries or []),
        "open_spreadsheets": list(spreadsheet_paths or []),
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


def write_ahf_file(path, payload):
    """Write a validated session payload to disk as .ahf JSON."""
    project_path = normalize_project_path(path)
    validate_payload(payload)

    with open(project_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    return project_path


def read_ahf_file(path):
    if not path:
        raise ValueError("Project path cannot be empty")

    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    validate_payload(payload)
    return payload