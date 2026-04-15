import json
import os
from datetime import datetime

import numpy as np


AHF_EXTENSION = ".ahf"
AHF_SCHEMA_VERSION = 2


def find_recording_metadata_path(samples_path):
    stem = os.path.splitext(samples_path)[0]
    candidates = [
        stem + ".json",
        stem + "_metadata.json",
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return None


def validate_recording_integrity(samples_path, metadata_path=None):
    warnings = []
    errors = []
    resolved_metadata_path = metadata_path or find_recording_metadata_path(samples_path)
    metadata = {}
    sample_count = None

    if not samples_path or not isinstance(samples_path, str):
        return {
            "ok": False,
            "warnings": [],
            "errors": ["samples_path is required"],
            "metadata_path": resolved_metadata_path,
            "sample_count": None,
            "metadata": metadata,
        }

    if not os.path.exists(samples_path):
        errors.append(f"Samples file not found: {samples_path}")
    elif not samples_path.lower().endswith(".npy"):
        warnings.append("Samples file extension is not .npy")
    else:
        try:
            samples = np.load(samples_path, mmap_mode="r")
            sample_count = int(samples.size)
        except Exception as error:
            errors.append(f"Could not load samples file: {error}")

    if not resolved_metadata_path:
        warnings.append("Companion metadata file was not found")
    elif not os.path.exists(resolved_metadata_path):
        warnings.append(f"Metadata file not found: {resolved_metadata_path}")
    else:
        try:
            with open(resolved_metadata_path, "r", encoding="utf-8") as metadata_file:
                metadata = json.load(metadata_file)
        except Exception as error:
            warnings.append(f"Could not parse metadata file: {error}")

    if isinstance(metadata, dict) and metadata:
        expected_fields = ["sample_rate_hz", "center_freq_hz", "gain_db", "num_samples"]
        for field in expected_fields:
            if field not in metadata:
                warnings.append(f"Metadata missing field: {field}")

        if sample_count is not None and "num_samples" in metadata:
            try:
                metadata_count = int(metadata.get("num_samples"))
                if metadata_count != sample_count:
                    warnings.append(
                        f"num_samples mismatch (metadata={metadata_count}, actual={sample_count})"
                    )
            except Exception:
                warnings.append("Metadata num_samples is not a valid integer")

        saved_samples_file = metadata.get("saved_samples_file")
        if isinstance(saved_samples_file, str) and saved_samples_file.strip():
            if os.path.basename(saved_samples_file) != os.path.basename(samples_path):
                warnings.append("Metadata saved_samples_file does not match selected samples file")

        try:
            sample_rate_hz = float(metadata.get("sample_rate_hz", 0.0))
            if sample_rate_hz <= 0:
                warnings.append("Metadata sample_rate_hz must be > 0")
        except Exception:
            warnings.append("Metadata sample_rate_hz is not numeric")

        try:
            center_freq_hz = float(metadata.get("center_freq_hz", 0.0))
            if center_freq_hz <= 0:
                warnings.append("Metadata center_freq_hz must be > 0")
        except Exception:
            warnings.append("Metadata center_freq_hz is not numeric")

    return {
        "ok": len(errors) == 0,
        "warnings": warnings,
        "errors": errors,
        "metadata_path": resolved_metadata_path,
        "sample_count": sample_count,
        "metadata": metadata,
    }


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


def _clean_annotations_payload(recording_annotations):
    cleaned = []
    for entry in recording_annotations or []:
        if not isinstance(entry, dict):
            continue
        samples_path = entry.get("samples_path")
        annotations = entry.get("annotations")
        if not isinstance(samples_path, str) or not samples_path.strip():
            continue
        if not isinstance(annotations, list):
            continue

        normalized_annotations = []
        for annotation in annotations:
            if not isinstance(annotation, dict):
                continue
            note = str(annotation.get("note", "")).strip()
            if not note:
                continue
            try:
                freq_mhz = float(annotation.get("frequency_mhz"))
                power_db = float(annotation.get("power_db"))
            except Exception:
                continue
            normalized_annotations.append(
                {
                    "frequency_mhz": freq_mhz,
                    "power_db": power_db,
                    "note": note,
                    "created_at": str(annotation.get("created_at", "")),
                }
            )

        cleaned.append(
            {
                "samples_path": samples_path,
                "annotations": normalized_annotations,
            }
        )
    return cleaned


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