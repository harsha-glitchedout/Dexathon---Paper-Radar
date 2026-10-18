"""Loads the syllabus JSON and gives helper lookups."""
import json


def load_syllabus(path_or_file):
    """Accepts a file path or an uploaded file object (Streamlit)."""
    if hasattr(path_or_file, "read"):
        data = json.load(path_or_file)
    else:
        with open(path_or_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    if "units" not in data or not data["units"]:
        raise ValueError("Syllabus JSON needs a non-empty 'units' object.")
    return data


def topic_to_unit(syllabus):
    """{'Linked lists': 'Unit 2 - Linear Structures', ...}"""
    mapping = {}
    for unit, topics in syllabus["units"].items():
        for t in topics:
            mapping[t] = unit
    return mapping
