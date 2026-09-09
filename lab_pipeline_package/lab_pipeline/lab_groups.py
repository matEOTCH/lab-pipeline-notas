"""Compatibility shim for notebooks that import the old module paths.

The implementation moved: shuffling to :mod:`lab_pipeline.grouping`, generated
files to :mod:`lab_pipeline.outputs`, paths to :mod:`lab_pipeline.naming`, and
orchestration to :mod:`lab_pipeline.services`.
"""

from __future__ import annotations

from .cli.groups_flow import run as run_lab_group_workflow
from .colab import workspace_root
from .grouping import (
    build_group_lookup,
    shuffle_groups as shuffle_groups_with_forced_assignments,
    validate_forced_assignments,
    validate_group_count,
)
from .naming import (
    course_roots_in as list_course_roots,
    lista_files_in as list_section_files,
    projects_in as list_projects,
    section_from_lista_path as section_from_list_path,
)
from .outputs import (
    download as download_outputs,
    split_blackboard_name,
    write_blackboard_csvs as generate_blackboard_csvs,
    write_bundle_zip as create_lab_output_zip,
    write_groups_pdf as generate_groups_pdf,
)
from .rosters import parse_student_list
from .services.groups import create_lab_groups as create_lab_groups_from_params

__all__ = [
    "build_group_lookup",
    "create_lab_groups_from_params",
    "create_lab_output_zip",
    "download_outputs",
    "generate_blackboard_csvs",
    "generate_groups_pdf",
    "list_course_roots",
    "list_projects",
    "list_section_files",
    "parse_student_list",
    "run_lab_group_workflow",
    "section_from_list_path",
    "shuffle_groups_with_forced_assignments",
    "split_blackboard_name",
    "validate_forced_assignments",
    "validate_group_count",
    "workspace_root",
]
