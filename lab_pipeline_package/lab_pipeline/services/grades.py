"""Applying TeamMates results, custom grade columns and absences to Notas.

Everything here goes through a single open/mutate/save of the workbook. The
previous implementation opened and saved it three times per request, which left
the file half-updated whenever a later stage raised.
"""

from __future__ import annotations

from pathlib import Path

from .. import blackboard_grades, comments_sheet, gradebook, settings, teammates_csv
from ..common import clean_text, normalize_student_code


VALID_METHODS = ("1", "2", "3")
METHOD_BLACKBOARD_FILE, METHOD_MANUAL_STUDENT, METHOD_MANUAL_GROUP = VALID_METHODS


# --- column templates ---------------------------------------------------------


def normalize_templates(templates: list[dict] | None) -> list[dict[str, str]]:
    normalized = []
    for template in templates or []:
        base_name = gradebook.normalize_custom_base_name(template.get("base_name", ""))
        method = str(template.get("method", "")).strip()
        if method not in VALID_METHODS:
            raise ValueError("Metodo de carga invalido. Use 1, 2 o 3.")
        normalized.append({"base_name": base_name, "method": method})
    return normalized


def grade_column_templates(course_root: Path, section: str) -> list[dict[str, str]]:
    """The per-section templates remembered from a previous run."""
    store = settings.grade_settings(course_root)
    saved = store.section(store.load(), section)
    return saved.get("custom_grade_columns", [])


def configure_grade_columns(
    course_root: Path,
    section: str,
    lab_number: int,
    templates: list[dict] | None,
) -> dict[str, object]:
    """Persist the section's grade-column templates."""
    course_root = Path(course_root)
    section = clean_text(section)
    lab_number = int(lab_number)
    normalized = normalize_templates(templates)

    store = settings.grade_settings(course_root)
    saved = store.load()
    store.section(saved, section)["custom_grade_columns"] = normalized
    store.save(saved)

    return {
        "course_root": course_root,
        "section": section,
        "lab_number": lab_number,
        "templates": normalized,
        "materialized_columns": gradebook.materialize_custom_columns(normalized, lab_number),
        "saved": True,
    }


def _payload_for(mapping: dict | None, index: int, template: dict, column_name: str):
    """Find this column's payload however the caller happened to key it.

    Callers key by position, by the raw base name, by the normalized base name,
    or by the materialized column name. Accepting all four keeps the browser
    from having to reproduce the server's name-materialization rules.
    """
    if not mapping:
        return None
    for key in (str(index), index, column_name, template.get("base_name", "")):
        if key in mapping:
            return mapping[key]
    return None


def _normalize_student_grades(raw: dict | None) -> dict[str, object]:
    grades = {}
    for code, value in (raw or {}).items():
        grade = blackboard_grades.normalize_grade_value(value)
        if grade is not None:
            grades[normalize_student_code(code)] = grade
    return grades


def _normalize_group_grades(raw: dict | None) -> dict[int, object]:
    grades = {}
    for group_number, value in (raw or {}).items():
        grade = blackboard_grades.normalize_grade_value(value)
        if grade is None:
            continue
        try:
            grades[int(group_number)] = grade
        except (TypeError, ValueError):
            continue
    return grades


# --- the workbook passes ------------------------------------------------------


def _import_teammates(book: gradebook.Gradebook, export, lab_number: int, positions: dict[str, int]) -> dict:
    tm_col = positions[gradebook.tm_percentage_column(lab_number)]
    resp_col = positions[gradebook.responded_column(lab_number)]
    updated_tm = 0
    missing_scores = []

    for student in book.students:
        score = export.scores.find(student)
        if score:
            gradebook.write_tm_percentage(book.ws, student, tm_col, score["tm_percentage"])
            updated_tm += 1
        else:
            missing_scores.append(student)
        book.ws.cell(row=student["row"], column=resp_col).value = "Si" if export.responded(student) else "No"

    comments_sheet.update(book.wb, book.students, lab_number, export.q2_comments, export.q3_comments)

    return {
        "students": len(book.students),
        "updated_tm": updated_tm,
        "updated_resp": len(book.students),
        "missing_scores": missing_scores,
    }


def _apply_custom_columns(
    book: gradebook.Gradebook,
    templates: list[dict],
    columns: list[str],
    positions: dict[str, int],
    lab_number: int,
    uploaded_files: dict | None,
    manual_student_grades: dict | None,
    manual_group_grades: dict | None,
) -> dict[str, int]:
    group_lookup = book.group_lookup(lab_number)
    updates = {}

    for index, (template, column_name) in enumerate(zip(templates, columns)):
        method = template["method"]

        if method == METHOD_BLACKBOARD_FILE:
            payload = _payload_for(uploaded_files, index, template, column_name)
            score_column = None
            path = payload
            if isinstance(payload, dict):
                path = payload.get("path")
                score_column = payload.get("score_column")
            if not path:
                raise ValueError(f"Falta archivo Blackboard para {column_name}.")
            grades = blackboard_grades.parse_grades(Path(path), score_column=score_column)

        elif method == METHOD_MANUAL_STUDENT:
            grades = _normalize_student_grades(
                _payload_for(manual_student_grades, index, template, column_name)
            )

        else:  # METHOD_MANUAL_GROUP
            by_group = _normalize_group_grades(
                _payload_for(manual_group_grades, index, template, column_name)
            )
            if not by_group:
                grades = {}
            elif not group_lookup:
                raise ValueError(
                    f"No encontre {gradebook.group_column(lab_number)}; primero genere grupos."
                )
            else:
                grades = {
                    code: by_group[group_number]
                    for code, group_number in group_lookup.items()
                    if group_number in by_group
                }

        updates[column_name] = gradebook.apply_grades_by_code(
            book.ws, book.students, positions[column_name], grades
        )

    return updates


def _apply_absences(
    book: gradebook.Gradebook,
    absent_codes: list[str] | None,
    positions: dict[str, int],
    lab_number: int,
    custom_columns: list[str],
) -> dict[str, object]:
    wanted = {normalize_student_code(code) for code in (absent_codes or []) if normalize_student_code(code)}
    by_code = book.by_code
    absent_students = []
    changed_cells = []

    for code in sorted(wanted):
        student = by_code.get(code)
        if not student:
            continue
        absent_students.append(student)
        changed_cells.extend(gradebook.mark_absent(book.ws, student, positions, lab_number, custom_columns))

    found = {student["code"] for student in absent_students}
    return {
        "absences_updated": len(absent_students),
        "absent_students": absent_students,
        "not_found_codes": sorted(wanted - found),
        "changed_cells": changed_cells,
        "notas_path": book.path,
    }


# --- public entry points ------------------------------------------------------


def apply_grade_updates(
    notas_path: Path,
    lab_number: int,
    custom_grade_templates: list[dict] | None = None,
    uploaded_files: dict | None = None,
    manual_student_grades: dict | None = None,
    manual_group_grades: dict | None = None,
    teammates_csv_path: Path | None = None,
    absent_codes: list[str] | None = None,
) -> dict[str, object]:
    """Apply TeamMates results, custom grades and absences in one pass."""
    notas_path = Path(notas_path)
    lab_number = int(lab_number)
    templates = normalize_templates(custom_grade_templates)
    custom_columns = gradebook.materialize_custom_columns(templates, lab_number)

    export = teammates_csv.TeammatesExport.from_path(Path(teammates_csv_path)) if teammates_csv_path else None

    with gradebook.Gradebook(notas_path) as book:
        positions, created_columns = book.ensure_columns(lab_number, custom_columns)
        book.refresh_students()

        tm_result = _import_teammates(book, export, lab_number, positions) if export else None
        custom_updates = _apply_custom_columns(
            book, templates, custom_columns, positions, lab_number,
            uploaded_files, manual_student_grades, manual_group_grades,
        )
        absence_result = _apply_absences(book, absent_codes, positions, lab_number, custom_columns)
        student_count = len(book.students)

    if tm_result is not None:
        tm_result["notas_path"] = notas_path
        tm_result["lab_number"] = lab_number
        tm_result["created_columns"] = created_columns

    return {
        "notas_path": notas_path,
        "lab_number": lab_number,
        "students": student_count,
        "tm_result": tm_result,
        "custom_updates": custom_updates,
        "absences": absence_result,
        "created_columns": created_columns,
        "success": True,
    }


def import_teammates(
    notas_path: Path,
    csv_path: Path,
    lab_number: int,
    custom_grade_columns: list[str] | None = None,
) -> dict[str, object]:
    """TeamMates results only, for callers that have nothing else to write."""
    notas_path = Path(notas_path)
    lab_number = int(lab_number)
    export = teammates_csv.TeammatesExport.from_path(Path(csv_path))

    with gradebook.Gradebook(notas_path) as book:
        positions, created_columns = book.ensure_columns(lab_number, custom_grade_columns or [])
        book.refresh_students()
        result = _import_teammates(book, export, lab_number, positions)

    result.update({"notas_path": notas_path, "lab_number": lab_number, "created_columns": created_columns})
    return result


def apply_absences(
    notas_path: Path,
    lab_number: int,
    absent_codes: list[str],
    custom_grade_columns: list[str] | None = None,
) -> dict[str, object]:
    """Mark students absent: zeroes across the lab's columns, TM_Resp? = No."""
    notas_path = Path(notas_path)
    lab_number = int(lab_number)
    custom_columns = list(custom_grade_columns or [])

    if not any(normalize_student_code(code) for code in absent_codes or []):
        return {
            "absences_updated": 0,
            "absent_students": [],
            "not_found_codes": [],
            "changed_cells": [],
            "notas_path": notas_path,
        }

    with gradebook.Gradebook(notas_path) as book:
        positions, _ = book.ensure_columns(lab_number, custom_columns)
        book.refresh_students()
        return _apply_absences(book, absent_codes, positions, lab_number, custom_columns)


def preview_absences(
    notas_path: Path,
    lab_number: int,
    absent_codes: list[str],
    custom_grade_columns: list[str] | None = None,
) -> dict[str, object]:
    """What ``apply_absences`` would change, without writing anything."""
    lab_number = int(lab_number)
    custom_columns = list(custom_grade_columns or [])
    changes = gradebook.absence_changes(lab_number, custom_columns)

    book = gradebook.Gradebook(Path(notas_path), read_only=True)
    by_code = book.by_code
    previews = []
    not_found = []

    for raw_code in absent_codes or []:
        code = normalize_student_code(raw_code)
        student = by_code.get(code)
        if not student:
            not_found.append(code)
            continue
        previews.append({
            "code": code,
            "name": student["name"],
            "changes": [{"column": column, "value": value} for column, value in changes],
        })

    return {
        "students": previews,
        "not_found_codes": not_found,
        "target_columns": [column for column, _ in changes],
    }

