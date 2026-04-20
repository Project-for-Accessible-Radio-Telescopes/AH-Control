"""File and path operation utilities."""
import os


def find_recording_metadata_path(samples_path):
    """Find the metadata JSON file associated with a samples file.
    
    Args:
        samples_path: Path to .npy samples file
        
    Returns:
        Path to metadata file if found, None otherwise
    """
    stem = os.path.splitext(samples_path)[0]
    candidates = [
        stem + ".json",
        stem + "_metadata.json",
    ]
    if stem.endswith("_spectrum"):
        base_stem = stem[: -len("_spectrum")]
        candidates.extend(
            [
                base_stem + ".json",
                base_stem + "_metadata.json",
            ]
        )
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return None


def normalize_project_path(path, ahf_extension=".ahf"):
    """Normalize a path to ensure it has the correct AHF extension.
    
    Args:
        path: Project file path
        ahf_extension: Expected extension (default: ".ahf")
        
    Returns:
        Path with correct extension
        
    Raises:
        ValueError: If path is empty
    """
    if not path:
        raise ValueError("Project path cannot be empty")

    root, ext = os.path.splitext(path)
    if ext.lower() == ahf_extension:
        return path
    return f"{root}{ahf_extension}"


def clean_string_list(values):
    """Clean and deduplicate a list of strings.
    
    Args:
        values: List of values (may contain non-strings)
        
    Returns:
        Cleaned list of unique non-empty strings
    """
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


def paths_to_relative(paths, project_dir):
    """Convert absolute paths to relative paths within a project directory.
    
    Args:
        paths: List of file paths
        project_dir: Project root directory
        
    Returns:
        List of relative paths
    """
    relative_paths = []
    for raw_path in clean_string_list(paths):
        normalized = os.path.normpath(raw_path)
        if os.path.isabs(normalized):
            try:
                normalized = os.path.relpath(normalized, project_dir)
            except Exception:
                normalized = raw_path
        relative_paths.append(normalized)
    return clean_string_list(relative_paths)


def paths_to_absolute(paths, project_dir):
    """Convert relative paths to absolute paths within a project directory.
    
    Args:
        paths: List of file paths
        project_dir: Project root directory
        
    Returns:
        List of absolute paths
    """
    absolute_paths = []
    for raw_path in clean_string_list(paths):
        normalized = os.path.normpath(raw_path)
        if not os.path.isabs(normalized):
            normalized = os.path.abspath(os.path.join(project_dir, normalized))
        absolute_paths.append(normalized)
    return clean_string_list(absolute_paths)
