"""Small JSON settings files kept next to the project or course folder.

Three of these exist, one per concern, and they all used to carry their own
copy of load/save. They share one implementation now.
"""

from __future__ import annotations

import json
from pathlib import Path


PROJECT_SETTINGS_FILENAME = ".lab_pipeline_settings.json"
LAB_GROUP_SETTINGS_FILENAME = ".lab_group_settings.json"
GRADE_SETTINGS_FILENAME = ".grade_upload_settings.json"


class JsonSettings:
    """A JSON dict on disk. Missing or corrupt files read as ``{}``."""

    def __init__(self, folder: Path, filename: str):
        self.folder = Path(folder)
        self.path = self.folder / filename

    def load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        return data if isinstance(data, dict) else {}

    def save(self, settings: dict) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")

    def section(self, settings: dict, section: str) -> dict:
        """The per-section sub-dict, created in place if absent."""
        return settings.setdefault("sections", {}).setdefault(str(section), {})


def project_settings(project_root: Path) -> JsonSettings:
    return JsonSettings(project_root, PROJECT_SETTINGS_FILENAME)


def lab_group_settings(course_root: Path) -> JsonSettings:
    return JsonSettings(course_root, LAB_GROUP_SETTINGS_FILENAME)


def grade_settings(course_root: Path) -> JsonSettings:
    return JsonSettings(course_root, GRADE_SETTINGS_FILENAME)
