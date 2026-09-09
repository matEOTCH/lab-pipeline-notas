"""Orchestration shared by every front-end.

Services take plain arguments, never prompt, never print, and return structured
results. The Flask app, the ipywidgets app and the notebook prompt flows all sit
on top of these and add nothing but input gathering and presentation.
"""

from .grades import (
    apply_absences,
    apply_grade_updates,
    configure_grade_columns,
    grade_column_templates,
    import_teammates,
    preview_absences,
)
from .groups import create_lab_groups, preview_groups
from .status import course_status, section_status
from .structure import create_structure

__all__ = [
    "apply_absences",
    "apply_grade_updates",
    "configure_grade_columns",
    "course_status",
    "create_lab_groups",
    "create_structure",
    "grade_column_templates",
    "import_teammates",
    "preview_absences",
    "preview_groups",
    "section_status",
]
