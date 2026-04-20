"""Validation utilities for recordings and metadata."""
import json
import os

import numpy as np


def validate_recording_integrity(samples_path, metadata_path=None, find_metadata_func=None):
    if find_metadata_func is None:
        from logic.util.file_helpers import find_recording_metadata_path
        find_metadata_func = find_recording_metadata_path
    
    warnings = []
    errors = []
    resolved_metadata_path = metadata_path or find_metadata_func(samples_path)
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
