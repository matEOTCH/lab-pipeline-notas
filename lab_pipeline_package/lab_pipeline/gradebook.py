"""The Notas workbook: student rows and the per-lab column block.

One lab contributes a contiguous block of columns to the gradebook, anchored on
``Grupo_LabN``::

    Grupo_LabN | <custom columns...> | %TMN | TMN_Resp? | Nota_LabN

This module owns that layout: where the block goes, what the columns are called,
what colour their headers are, and how values get written into them. It used to
exist in three partial copies (``common``, ``teammates``, ``lab_groups``).
"""

from __future__ import annotations

import re
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .common import (
    clean_text,
    copy_column_style,
    delete_row_and_renumber,
    find_col_ws,
    find_header_row_ws,
    find_last_real_header_col,
    normalize_header,
    normalize_student_code,
    row_as_dict,
)


GROUP_COLOR = "C060C0"
GRADE_COLOR = "FFFF00"
RESPONDED_COLOR = "FF5B6B"
DEFAULT_COLOR = "39A9DB"

_GRADE_COL_RE = re.compile(r"^Nota_Lab(\d+)$")

CODE_ALIASES = ["Codigo", "Code", "Student ID"]
NAME_ALIASES = ["Nombre Completo", "Apellidos y Nombres", "Name"]
EMAIL_ALIASES = ["Correo", "Email", "Recipient Email"]
NRO_ALIASES = ["Nro.", "Nro", "Nr", "Numero"]

ABSENT_TM_PERCENTAGE = 0
ABSENT_GRADE = 0
ABSENT_RESPONDED = "No"
TM_NUMBER_FORMAT = "0.00%"


# --- column names -------------------------------------------------------------


def group_column(lab_number: int) -> str:
    return f"Grupo_Lab{int(lab_number)}"


def tm_percentage_column(lab_number: int) -> str:
    return f"%TM{int(lab_number)}"


def responded_column(lab_number: int) -> str:
    return f"TM{int(lab_number)}_Resp?"


def grade_column(lab_number: int) -> str:
    return f"Nota_Lab{int(lab_number)}"


def standard_columns(lab_number: int) -> list[str]:
    """The columns every lab gets, in block order, excluding the group anchor."""
    return [tm_percentage_column(lab_number), responded_column(lab_number), grade_column(lab_number)]


def block_columns(lab_number: int, custom_columns: list[str] | None = None) -> list[str]:
    return list(custom_columns or []) + standard_columns(lab_number)


def column_aliases(name: str, lab_number: int) -> list[str]:
    """Spellings of ``name`` that may already exist in a hand-edited workbook."""
    lab_number = int(lab_number)
    known = {
        group_column(lab_number): [f"Grupo Lab{lab_number}", f"Grupo Lab {lab_number}"],
        tm_percentage_column(lab_number): [f"%TM_{lab_number}", f"%TM {lab_number}"],
        responded_column(lab_number): [f"TM_{lab_number}_Resp?", f"TM{lab_number} Resp?", f"TM{lab_number}_Resp"],
        grade_column(lab_number): [f"Nota Lab{lab_number}", f"Nota Lab {lab_number}"],
    }
    if lab_number == 1:
        known[responded_column(lab_number)].append("LB_Resp?")
    return [name] + known.get(name, [])


def header_color(name: str, lab_number: int) -> str:
    lab_number = int(lab_number)
    if name == group_column(lab_number):
        return GROUP_COLOR
    if name == grade_column(lab_number):
        return GRADE_COLOR
    if name == responded_column(lab_number):
        return RESPONDED_COLOR
    return DEFAULT_COLOR


def normalize_custom_base_name(raw_name: str) -> str:
    """"Quiz Lab 2" -> "Quiz_Lab"; the lab number is appended at use time."""
    name = clean_text(raw_name).replace(" ", "_")
    if not name:
        raise ValueError("El nombre de la columna no puede estar vacio.")
    return re.sub(r"\d+$", "", name)


def materialize_custom_column(base_name: str, lab_number: int) -> str:
    return f"{normalize_custom_base_name(base_name)}{int(lab_number)}"


def materialize_custom_columns(templates: list[dict], lab_number: int) -> list[str]:
    return [materialize_custom_column(template["base_name"], lab_number) for template in templates]


# --- worksheet access ---------------------------------------------------------


def find_column(ws, header_row: int, name: str, lab_number: int) -> int | None:
    targets = {normalize_header(alias) for alias in column_aliases(name, lab_number)}
    for col in range(1, ws.max_column + 1):
        if normalize_header(ws.cell(row=header_row, column=col).value) in targets:
            return col
    return None


def read_students(ws, header_row: int) -> list[dict]:
    """One dict per student row: ``row``, ``nro``, ``code``, ``name``, ``email``."""
    nro_col = find_col_ws(ws, header_row, NRO_ALIASES, required=False)
    code_col = find_col_ws(ws, header_row, CODE_ALIASES)
    name_col = find_col_ws(ws, header_row, NAME_ALIASES)
    email_col = find_col_ws(ws, header_row, EMAIL_ALIASES, required=False)
    students = []

    for row in range(header_row + 1, ws.max_row + 1):
        code = normalize_student_code(ws.cell(row=row, column=code_col).value)
        name = clean_text(ws.cell(row=row, column=name_col).value)
        if not code and not name:
            continue
        students.append({
            "row": row,
            "nro": ws.cell(row=row, column=nro_col).value if nro_col else len(students) + 1,
            "code": code,
            "name": name,
            "email": clean_text(ws.cell(row=row, column=email_col).value) if email_col else "",
        })

    return students


def recorded_lab_numbers(ws, header_row: int, row: int) -> list[int]:
    """Lab numbers where this row already has a grade recorded in ``Nota_LabN``."""
    numbers = []
    for col in range(1, ws.max_column + 1):
        match = _GRADE_COL_RE.match(clean_text(ws.cell(row=header_row, column=col).value))
        if not match:
            continue
        if ws.cell(row=row, column=col).value not in (None, ""):
            numbers.append(int(match.group(1)))
    return sorted(numbers)


def pop_student_row(ws, header_row: int, students: list[dict], code: str) -> dict[str, object] | None:
    """Remove one student's row from a Notas worksheet, returning its data.

    Renumbers ``Nro.`` for the rows that remain. Returns ``None`` when ``code``
    isn't among ``students``.
    """
    code = normalize_student_code(code)
    student = next((item for item in students if item["code"] == code), None)
    if not student:
        return None

    nro_col = find_col_ws(ws, header_row, NRO_ALIASES, required=False)
    row_data = row_as_dict(ws, header_row, student["row"])
    delete_row_and_renumber(ws, header_row, student["row"], nro_col)
    return row_data


def style_header(ws, header_row: int, col: int, name: str, lab_number: int) -> None:
    color = header_color(name, lab_number)
    thin = Side(style="thin", color="000000")
    cell = ws.cell(row=header_row, column=col)
    cell.fill = PatternFill("solid", fgColor=color)
    cell.font = Font(bold=True, color="000000" if color == GRADE_COLOR else "FFFFFF")
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)
    ws.column_dimensions[get_column_letter(col)].width = 14


def ensure_columns(
    ws,
    header_row: int,
    lab_number: int,
    custom_columns: list[str] | None = None,
) -> tuple[dict[str, int], list[str]]:
    """Make the lab's column block exist, and return ``(positions, created)``.

    Idempotent: existing columns are reused (under any known alias) and only
    missing ones are inserted, immediately after the group anchor.
    """
    lab_number = int(lab_number)
    positions: dict[str, int] = {}
    created: list[str] = []

    anchor = group_column(lab_number)
    group_col = find_column(ws, header_row, anchor, lab_number)
    if not group_col:
        last_col = find_last_real_header_col(ws, header_row)
        group_col = last_col + 1
        ws.insert_cols(group_col)
        copy_column_style(ws, last_col, group_col)
        ws.cell(row=header_row, column=group_col).value = anchor
        created.append(anchor)

    positions[anchor] = group_col
    style_header(ws, header_row, group_col, anchor, lab_number)

    insert_at = group_col + 1
    style_reference_col = group_col
    for name in block_columns(lab_number, custom_columns):
        existing_col = find_column(ws, header_row, name, lab_number)
        if existing_col:
            positions[name] = existing_col
            style_header(ws, header_row, existing_col, name, lab_number)
            insert_at = max(insert_at, existing_col + 1)
            style_reference_col = existing_col
            continue

        ws.insert_cols(insert_at)
        copy_column_style(ws, style_reference_col, insert_at)
        ws.cell(row=header_row, column=insert_at).value = name
        positions[name] = insert_at
        created.append(name)
        style_header(ws, header_row, insert_at, name, lab_number)
        style_reference_col = insert_at
        insert_at += 1

    return positions, created


def ensure_group_column(ws, header_row: int, lab_number: int) -> tuple[int, list[str]]:
    """The group anchor alone, for the group-generation flow."""
    positions, created = ensure_columns(ws, header_row, lab_number, custom_columns=[])
    anchor = group_column(lab_number)
    return positions[anchor], [name for name in created if name == anchor]


# --- writing values -----------------------------------------------------------


def read_group_lookup(ws, header_row: int, students: list[dict], lab_number: int) -> dict[str, int]:
    """``{student code: group number}`` as recorded in the workbook."""
    col = find_column(ws, header_row, group_column(lab_number), lab_number)
    if not col:
        return {}
    lookup = {}
    for student in students:
        value = ws.cell(row=student["row"], column=col).value
        if value is None:
            continue
        try:
            lookup[student["code"]] = int(value)
        except (TypeError, ValueError):
            continue
    return lookup


def apply_grades_by_code(ws, students: list[dict], col: int, grades: dict[str, object]) -> int:
    updated = 0
    for student in students:
        grade = grades.get(student["code"])
        if grade is None:
            continue
        ws.cell(row=student["row"], column=col).value = grade
        updated += 1
    return updated


def write_group_numbers(ws, students: list[dict], col: int, group_lookup: dict[str, int]) -> tuple[int, list[str]]:
    updated = 0
    unmatched = []
    for student in students:
        code = student["code"]
        if not code:
            continue
        if code in group_lookup:
            ws.cell(row=student["row"], column=col).value = group_lookup[code]
            updated += 1
        else:
            unmatched.append(code)
    return updated, unmatched


def absence_changes(lab_number: int, custom_columns: list[str] | None = None) -> list[tuple[str, object]]:
    """What marking a student absent writes, as ``(column name, value)`` pairs."""
    lab_number = int(lab_number)
    changes: list[tuple[str, object]] = [
        (name, ABSENT_GRADE) for name in list(custom_columns or []) + [grade_column(lab_number)]
    ]
    changes.append((tm_percentage_column(lab_number), ABSENT_TM_PERCENTAGE))
    changes.append((responded_column(lab_number), ABSENT_RESPONDED))
    return changes


def mark_absent(
    ws,
    student: dict,
    positions: dict[str, int],
    lab_number: int,
    custom_columns: list[str] | None = None,
) -> list[dict]:
    """Zero out one student's lab columns. Returns the cells actually changed."""
    lab_number = int(lab_number)
    tm_name = tm_percentage_column(lab_number)
    changed = []
    for column_name, value in absence_changes(lab_number, custom_columns):
        col = positions.get(column_name)
        if not col:
            continue
        cell = ws.cell(row=student["row"], column=col)
        cell.value = value
        if column_name == tm_name:
            cell.number_format = TM_NUMBER_FORMAT
        changed.append({"code": student["code"], "row": student["row"], "column": column_name, "value": value})
    return changed


def write_tm_percentage(ws, student: dict, col: int, percentage: float) -> None:
    cell = ws.cell(row=student["row"], column=col)
    cell.value = percentage
    cell.number_format = TM_NUMBER_FORMAT


# --- opening ------------------------------------------------------------------


class Gradebook:
    """An open Notas workbook plus its header row and student rows.

    Used as a context manager it saves on clean exit, so a whole request is one
    open/mutate/save instead of several passes over the same file.
    """

    def __init__(self, path: Path, read_only: bool = False):
        self.path = Path(path)
        self.read_only = read_only
        self.wb = load_workbook(self.path, data_only=read_only)
        self.ws = self.wb.worksheets[0]
        self.header_row = find_header_row_ws(self.ws)
        self.students = read_students(self.ws, self.header_row)

    @property
    def by_code(self) -> dict[str, dict]:
        return {student["code"]: student for student in self.students if student["code"]}

    def ensure_columns(self, lab_number: int, custom_columns: list[str] | None = None):
        return ensure_columns(self.ws, self.header_row, lab_number, custom_columns)

    def group_lookup(self, lab_number: int) -> dict[str, int]:
        return read_group_lookup(self.ws, self.header_row, self.students, lab_number)

    def refresh_students(self) -> None:
        self.students = read_students(self.ws, self.header_row)

    def recorded_lab_numbers(self, code: str) -> list[int]:
        student = self.by_code.get(normalize_student_code(code))
        if not student:
            return []
        return recorded_lab_numbers(self.ws, self.header_row, student["row"])

    def pop_student(self, code: str) -> dict[str, object] | None:
        row_data = pop_student_row(self.ws, self.header_row, self.students, code)
        if row_data is not None:
            self.refresh_students()
        return row_data

    def save(self) -> None:
        if self.read_only:
            raise RuntimeError("Este Gradebook se abrio en modo lectura.")
        self.wb.save(self.path)

    def __enter__(self) -> "Gradebook":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc_type is None and not self.read_only:
            self.save()
        self.wb.close()
        return False
