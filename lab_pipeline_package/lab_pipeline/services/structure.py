"""Creating a course's folder structure, Lista and Notas from a roster CSV."""

from __future__ import annotations

from pathlib import Path

from .. import naming, rosters, settings
from ..common import clean_text


def create_structure(
    workspace_root: Path,
    project_name: str,
    course_cycle_name: str,
    section: str,
    email_domain: str,
    csv_path: Path,
    overwrite: bool = False,
) -> dict[str, object]:
    """Create the course folders, the clean Lista, and the Notas workbook."""
    workspace_root = Path(workspace_root)
    project_name = clean_text(project_name)
    course_cycle_name = clean_text(course_cycle_name)
    section = clean_text(section)
    email_domain = clean_text(email_domain).removeprefix("@")
    csv_path = Path(csv_path)
    warnings: list[str] = []

    for value, message in (
        (project_name, "El nombre del proyecto no puede estar vacio."),
        (course_cycle_name, "El nombre del curso/ciclo no puede estar vacio."),
        (section, "La seccion no puede estar vacia."),
        (email_domain, "El dominio institucional no puede estar vacio."),
    ):
        if not value:
            raise ValueError(message)
    if not csv_path.exists():
        raise FileNotFoundError(f"No se encontro el CSV: {csv_path}")

    project_root = workspace_root / project_name
    course_root = project_root / course_cycle_name
    folders = naming.create_base_structure(course_root)

    list_path = naming.lista_path(course_root, section)
    notas_path = naming.notas_path(course_root, section)
    existing = [path for path in (list_path, notas_path) if path.exists()]
    if existing and not overwrite:
        raise FileExistsError(
            f"Ya existen archivos para esta seccion: {', '.join(path.name for path in existing)}"
        )
    if existing:
        warnings.append("Se reemplazaron archivos existentes de Lista/Notas.")

    store = settings.project_settings(project_root)
    saved = store.load()
    saved["email_domain"] = email_domain
    store.save(saved)

    students = rosters.read_blackboard_roster(csv_path)
    if not students:
        raise ValueError("El CSV no contiene estudiantes validos.")
    clean_rows = rosters.build_clean_list(students, email_domain)
    rosters.save_students_workbook(clean_rows, list_path)
    rosters.save_students_workbook(clean_rows, notas_path)

    return {
        "project_root": project_root,
        "course_root": course_root,
        "folders": folders,
        "section": section,
        "email_domain": email_domain,
        "source_csv": csv_path,
        "list_path": list_path,
        "notas_path": notas_path,
        "students": clean_rows,
        "warnings": warnings,
        "created": True,
    }


def preview_roster(csv_path: Path, email_domain: str) -> list[dict[str, str]]:
    """What ``create_structure`` would write, without writing anything."""
    return rosters.build_clean_list(rosters.read_blackboard_roster(Path(csv_path)), email_domain)


def saved_email_domain(project_root: Path) -> str:
    return clean_text(settings.project_settings(project_root).load().get("email_domain"))
