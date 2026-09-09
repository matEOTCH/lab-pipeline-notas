"""Generating lab groups and their outputs for one section."""

from __future__ import annotations

import shutil
from pathlib import Path

from .. import gradebook, grouping, naming, outputs, rosters, settings
from ..common import clean_text


def preview_groups(
    students: list[dict],
    group_count: int,
    forced_assignments: dict[str, int] | None = None,
    seed: int | None = None,
) -> list[list[dict]]:
    """Shuffle without touching disk, so the UI can show the result first."""
    group_count = grouping.validate_group_count(group_count)
    forced = grouping.validate_forced_assignments(students, group_count, forced_assignments)
    return grouping.shuffle_groups(students, group_count, forced, seed)


def section_people(course_root: Path, section: str) -> dict[str, str]:
    """The professor / jefe de practica remembered for this section."""
    store = settings.lab_group_settings(course_root)
    saved = store.section(store.load(), section)
    return {
        "professor": clean_text(saved.get("professor")),
        "jefe": clean_text(saved.get("jefe_practica")),
    }


def remember_section_people(course_root: Path, section: str, professor: str, jefe: str) -> None:
    store = settings.lab_group_settings(course_root)
    saved = store.load()
    section_settings = store.section(saved, section)
    section_settings["professor"] = professor
    section_settings["jefe_practica"] = jefe
    store.save(saved)


def _ensure_notas_exists(lista_path: Path, notas_path: Path) -> bool:
    """Seed Notas from the Lista when a section predates the Notas workbook."""
    if notas_path.exists():
        return False
    notas_path.parent.mkdir(parents=True, exist_ok=True)
    suffix = lista_path.suffix.lower()
    if suffix == ".xlsx":
        shutil.copy(lista_path, notas_path)
        return True
    _, students = rosters.parse_student_list(lista_path)
    rows = [
        {"Nro.": index, "Codigo": student["code"], "Nombre Completo": student["name"], "Email": ""}
        for index, student in enumerate(students, start=1)
    ]
    rosters.save_students_workbook(rows, notas_path)
    return True


def create_lab_groups(
    course_root: Path,
    section: str,
    professor: str,
    jefe: str,
    lab_number: int,
    lab_name: str = "",
    group_count: int = grouping.MAX_GROUPS,
    forced_assignments: dict[str, int] | None = None,
    seed: int | None = None,
    download: bool = False,
    self_enroll: str = "N",
) -> dict[str, object]:
    """Shuffle groups, record them in Notas, and write the PDF/CSVs/ZIP."""
    course_root = Path(course_root)
    section = clean_text(section)
    professor = clean_text(professor)
    jefe = clean_text(jefe)
    lab_number = int(lab_number)
    group_count = grouping.validate_group_count(group_count)
    lab_name = clean_text(lab_name) or f"Laboratorio {lab_number}"
    warnings: list[str] = []

    for value, message in (
        (section, "La seccion no puede estar vacia."),
        (professor, "El profesor no puede estar vacio."),
        (jefe, "El jefe de practica no puede estar vacio."),
    ):
        if not value:
            raise ValueError(message)
    if lab_number < 1:
        raise ValueError("El numero de laboratorio debe ser positivo.")

    lista_path = naming.lista_path(course_root, section)
    if not lista_path.exists():
        raise FileNotFoundError(f"No encontre la lista de la seccion: {lista_path}")

    parsed_section, students = rosters.parse_student_list(lista_path)
    if parsed_section and parsed_section != section:
        warnings.append(f"La lista parece pertenecer a la seccion {parsed_section}.")
    if not students:
        raise ValueError("La lista no tiene estudiantes validos.")

    forced = grouping.validate_forced_assignments(students, group_count, forced_assignments)
    groups = grouping.shuffle_groups(students, group_count, forced, seed)

    remember_section_people(course_root, section, professor, jefe)

    notas_path = naming.notas_path(course_root, section)
    if _ensure_notas_exists(lista_path, notas_path):
        warnings.append("El archivo de Notas no existia; se creo desde la Lista.")

    with gradebook.Gradebook(notas_path) as book:
        group_col, created_columns = gradebook.ensure_group_column(book.ws, book.header_row, lab_number)
        book.refresh_students()
        updated_count, unmatched_codes = gradebook.write_group_numbers(
            book.ws, book.students, group_col, grouping.build_group_lookup(groups)
        )

    paths = naming.lab_output_paths(course_root, section, lab_number)
    naming.lab_folder(course_root, section, lab_number).mkdir(parents=True, exist_ok=True)

    outputs.write_groups_pdf(
        groups=groups,
        section=section,
        professor=professor,
        jefe=jefe,
        lab_number=lab_number,
        out_path=paths["pdf"],
    )
    outputs.write_blackboard_csvs(
        groups=groups,
        section=section,
        lab_number=lab_number,
        groups_out=paths["groups_csv"],
        members_out=paths["members_csv"],
        self_enroll=self_enroll,
    )
    outputs.write_bundle_zip([paths["groups_csv"], paths["members_csv"], paths["pdf"]], paths["zip"])
    if download:
        outputs.download([paths["zip"]])

    return {
        "section": section,
        "course_root": course_root,
        "professor": professor,
        "jefe": jefe,
        "lab_number": lab_number,
        "lab_name": lab_name,
        "students_count": len(students),
        "groups": groups,
        "group_sizes": [len(group) for group in groups],
        "forced_assignments": forced,
        "notas_path": notas_path,
        "notas_result": {
            "updated_count": updated_count,
            "created_columns": created_columns,
            "unmatched_codes": unmatched_codes,
        },
        "pdf_path": paths["pdf"],
        "groups_csv": paths["groups_csv"],
        "members_csv": paths["members_csv"],
        "zip_path": paths["zip"],
        "warnings": warnings,
        "success": True,
    }
