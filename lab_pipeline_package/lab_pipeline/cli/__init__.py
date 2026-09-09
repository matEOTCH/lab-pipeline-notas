"""Interactive notebook workflows: prompt for input, then call a service."""

from .grades_flow import run as run_teammates_workflow
from .groups_flow import run as run_lab_group_workflow
from .structure_flow import run as run_structure_workflow

__all__ = ["run_structure_workflow", "run_lab_group_workflow", "run_teammates_workflow"]
