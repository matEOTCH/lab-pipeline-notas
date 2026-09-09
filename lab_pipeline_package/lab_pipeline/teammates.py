"""Compatibility shim for notebooks that import the old module paths.

The implementation moved: the TeamMates export parser to
:mod:`lab_pipeline.teammates_csv`, Blackboard grade files to
:mod:`lab_pipeline.blackboard_grades`, the workbook to
:mod:`lab_pipeline.gradebook`, the comments sheet to
:mod:`lab_pipeline.comments_sheet`, and orchestration to
:mod:`lab_pipeline.services`.
"""

from __future__ import annotations

from .blackboard_grades import normalize_grade_value, parse_grades as parse_blackboard_grades
from .cli.grades_flow import run as run_teammates_workflow
from .comments_sheet import SHEET_NAME as COMMENTS_SHEET_NAME
from .gradebook import (
    materialize_custom_column as materialize_grade_column_name,
    materialize_custom_columns as materialize_grade_columns,
    normalize_custom_base_name as normalize_custom_grade_base_name,
)
from .naming import labs_in as list_created_labs
from .services.grades import (
    apply_absences as apply_absences_from_codes,
    apply_grade_updates as apply_grade_updates_from_params,
    configure_grade_columns as configure_grade_columns_from_params,
    import_teammates as update_notas_with_teammates_csv,
    preview_absences as preview_absence_impact,
)
from .teammates_csv import MAX_TM_SCORE

__all__ = [
    "COMMENTS_SHEET_NAME",
    "MAX_TM_SCORE",
    "apply_absences_from_codes",
    "apply_grade_updates_from_params",
    "configure_grade_columns_from_params",
    "list_created_labs",
    "materialize_grade_column_name",
    "materialize_grade_columns",
    "normalize_custom_grade_base_name",
    "normalize_grade_value",
    "parse_blackboard_grades",
    "preview_absence_impact",
    "run_teammates_workflow",
    "update_notas_with_teammates_csv",
]
