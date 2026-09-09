from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AppState:
    workspace_root: Path
    project_root: Path | None = None
    course_root: Path | None = None
    section: str | None = None
    lab_number: int | None = None
    last_outputs: dict[str, Path] = field(default_factory=dict)
    forced_assignments: dict[str, int] = field(default_factory=dict)
    absent_codes: list[str] = field(default_factory=list)

