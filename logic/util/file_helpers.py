import json
import os


def find_recording_metadata_path(samples_path):
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
    if not path:
        raise ValueError("Project path cannot be empty")

    root, ext = os.path.splitext(path)
    if ext.lower() == ahf_extension:
        return path
    return f"{root}{ahf_extension}"


def clean_string_list(values):
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
    absolute_paths = []
    for raw_path in clean_string_list(paths):
        normalized = os.path.normpath(raw_path)
        if not os.path.isabs(normalized):
            normalized = os.path.abspath(os.path.join(project_dir, normalized))
        absolute_paths.append(normalized)
    return clean_string_list(absolute_paths)

def retrievejson_from(key, file_name, folderpath):
    if not os.path.isdir(folderpath):
        return ValueError(f"Path does not exist! {folderpath}")
    
    filepath = os.path.join(folderpath, file_name)

    if not os.path.isfile(filepath):
        return ValueError(f"Check the file name: {file_name}")
    
    if not file_name.endswith('.json'):
        return ValueError(f"File is not JSON. Suggest you try calling retrievefile_from instead")
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if key in data:
            return data[key]
        else:
            return ValueError(f"Key does not exist.")
    except Exception as e:
        return ValueError(f"Error reading JSON file: {e}")
    