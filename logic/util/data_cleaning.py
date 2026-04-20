"""Data cleaning and normalization utilities."""
from logic.util.file_helpers import clean_string_list


def clean_annotations_payload(recording_annotations):
    """Clean and validate recording annotations payload.
    
    Ensures all annotations have valid structure and required fields.
    
    Args:
        recording_annotations: List of annotation dicts to validate
        
    Returns:
        Cleaned list of validated annotation dicts with keys:
            - samples_path: path to samples file
            - annotations: list of annotation dicts
    """
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
