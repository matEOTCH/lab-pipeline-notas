"""Compatibility shim for notebooks that import the old module paths.

The implementation moved: paths to :mod:`lab_pipeline.naming`, roster parsing to
:mod:`lab_pipeline.rosters`, orchestration to :mod:`lab_pipeline.services`, and
the prompt flow to :mod:`lab_pipeline.cli`.
"""

from __future__ import annotations

from .cli.structure_flow import run as run_structure_workflow
from .colab import workspace_root as default_mydrive
from .naming import (
    DEFAULT_FOLDERS,
    LISTA_SUFFIX,
    NOTAS_SUFFIX,
    create_base_structure,
    sections_in as list_existing_sections,
    split_course_cycle,
)
from .rosters import (
    build_clean_list,
    read_blackboard_roster as read_blackboard_csv,
    save_students_workbook,
)
from .services.structure import create_structure as create_structure_from_params

__all__ = [
    "DEFAULT_FOLDERS",
    "LISTA_SUFFIX",
    "NOTAS_SUFFIX",
    "build_clean_list",
    "create_base_structure",
    "create_structure_from_params",
    "default_mydrive",
    "list_existing_sections",
    "read_blackboard_csv",
    "run_structure_workflow",
    "save_students_workbook",
    "split_course_cycle",
]
