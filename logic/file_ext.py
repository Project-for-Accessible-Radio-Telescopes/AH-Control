import json
import os
from datetime import datetime

import numpy as np

from logic.util.file_helpers import (
    find_recording_metadata_path,
    normalize_project_path,
    clean_string_list,
    paths_to_relative,
    paths_to_absolute,
)
from logic.util.validation import validate_recording_integrity
from logic.util.data_cleaning import clean_annotations_payload


AHF_EXTENSION = ".ahf"
AHF_SCHEMA_VERSION = 2


def _clean_string_list(values):
    return clean_string_list(values)


def _paths_to_relative(paths, project_dir):
    return paths_to_relative(paths, project_dir)


def _paths_to_absolute(paths, project_dir):
    return paths_to_absolute(paths, project_dir)


def _clean_annotations_payload(recording_annotations):
    return clean_annotations_payload(recording_annotations)



def _annotations_to_relative(recording_annotations, project_dir):
    converted = []
    for entry in _clean_annotations_payload(recording_annotations):
        samples_path = os.path.normpath(entry["samples_path"])
        if os.path.isabs(samples_path):
            try:
                samples_path = os.path.relpath(samples_path, project_dir)
            except Exception:
                samples_path = entry["samples_path"]
        converted.append(
            {
                "samples_path": samples_path,
                "annotations": entry["annotations"],
            }
        )
    return converted


def _annotations_to_absolute(recording_annotations, project_dir):
    converted = []
    for entry in _clean_annotations_payload(recording_annotations):
        samples_path = os.path.normpath(entry["samples_path"])
        if not os.path.isabs(samples_path):
            samples_path = os.path.abspath(os.path.join(project_dir, samples_path))
        converted.append(
            {
                "samples_path": samples_path,
                "annotations": entry["annotations"],
            }
        )
    return converted


def build_session_payload(settings, log_entries, spreadsheet_paths, recording_annotations=None):
    payload = {
        "format": "AHF",
        "schema_version": AHF_SCHEMA_VERSION,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "settings": settings or {},
        "log_entries": _clean_string_list(log_entries),
        "open_spreadsheets": _clean_string_list(spreadsheet_paths),
        "recording_annotations": _clean_annotations_payload(recording_annotations),
        "paths": {
            "open_spreadsheets": "relative_to_project",
            "recording_annotations": "relative_to_project",
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

    if not isinstance(payload.get("recording_annotations", []), list):
        raise ValueError("Invalid AHF file: recording_annotations must be an array")

    for item in payload.get("log_entries", []):
        if not isinstance(item, str):
            raise ValueError("Invalid AHF file: log_entries items must be strings")

    for item in payload.get("open_spreadsheets", []):
        if not isinstance(item, str):
            raise ValueError("Invalid AHF file: open_spreadsheets items must be strings")

    for item in payload.get("recording_annotations", []):
        if not isinstance(item, dict):
            raise ValueError("Invalid AHF file: recording_annotations items must be objects")
        if not isinstance(item.get("samples_path"), str):
            raise ValueError("Invalid AHF file: recording_annotations.samples_path must be a string")
        if not isinstance(item.get("annotations", []), list):
            raise ValueError("Invalid AHF file: recording_annotations.annotations must be an array")


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
    payload_to_store["recording_annotations"] = _annotations_to_relative(
        payload.get("recording_annotations", []),
        project_dir,
    )
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
    normalized_payload["recording_annotations"] = _annotations_to_absolute(
        payload.get("recording_annotations", []),
        project_dir,
    )
    return normalized_payload