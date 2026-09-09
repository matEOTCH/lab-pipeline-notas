"""What exists on disk: the dashboard's view of a workspace."""

from __future__ import annotations

from pathlib import Path

from .. import naming


def section_status(course_root: Path, section: str) -> dict[str, object]:
    course_root = Path(course_root)
    lista_path = naming.lista_path(course_root, section)
    notas_path = naming.notas_path(course_root, section)
    labs = naming.labs_in(course_root, section)
    return {
        "section": section,
        "lista_path": lista_path if lista_path.exists() else None,
        "notas_path": notas_path if notas_path.exists() else None,
        "labs": labs,
        "outputs": {lab: naming.existing_lab_outputs(course_root, section, lab) for lab in labs},
    }


def course_status(course_root: Path) -> dict[str, object]:
    course_root = Path(course_root)
    sections = naming.sections_in(course_root)
    return {
        "course_root": course_root,
        "sections": sections,
        "section_status": [section_status(course_root, section) for section in sections],
    }
