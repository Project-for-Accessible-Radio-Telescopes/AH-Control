from logic.util.file_helpers import retrievejson_from
import os

def get_call_settings():
    path = os.path.join(os.path.dirname(__file__), "../../data")
    return path

def get_theme():
    return retrievejson_from("theme", "settings.json", get_call_settings())