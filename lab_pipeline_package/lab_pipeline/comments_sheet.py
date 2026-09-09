"""The "TM_Comments per student" sheet: peer comments, one row per student."""

from __future__ import annotations

from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .common import clean_text


SHEET_NAME = "TM_Comments per student"
COMMENT_SEPARATOR = ", "
FIXED_HEADERS = ["Nro.", "codigo", "nombre completo"]

HEADER_FILL = "1F4E78"
BORDER_COLOR = "D9D9D9"
FIXED_WIDTHS = {"A": 8, "B": 15, "C": 42}
COMMENT_WIDTH = 95


def question_header(question_number: int, lab_number: int) -> str:
    return f"Q{int(question_number)}_Lab{int(lab_number)}"


def _headers_by_name(ws) -> dict[str, int]:
    return {
        clean_text(ws.cell(row=1, column=col).value): col
        for col in range(1, ws.max_column + 1)
        if clean_text(ws.cell(row=1, column=col).value)
    }


def ensure_columns(ws, lab_number: int) -> tuple[int, int]:
    """Guarantee the fixed headers and this lab's Q2/Q3 columns exist."""
    for index, header in enumerate(FIXED_HEADERS, start=1):
        ws.cell(row=1, column=index).value = header

    columns = []
    for question_number in (2, 3):
        header = question_header(question_number, lab_number)
        existing = _headers_by_name(ws).get(header)
        if not existing:
            existing = ws.max_column + 1
            ws.cell(row=1, column=existing).value = header
        columns.append(existing)

    return columns[0], columns[1]


def style(ws, q2_col: int, q3_col: int) -> None:
    header_fill = PatternFill("solid", fgColor=HEADER_FILL)
    header_font = Font(bold=True, color="FFFFFF")
    thin = Side(style="thin", color=BORDER_COLOR)

    for col in range(1, ws.max_column + 1):
        cell = ws.cell(row=1, column=col)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)

    ws.freeze_panes = "D2"
    for column, width in FIXED_WIDTHS.items():
        ws.column_dimensions[column].width = width
    for col in (q2_col, q3_col):
        ws.column_dimensions[get_column_letter(col)].width = COMMENT_WIDTH

    for row in range(2, ws.max_row + 1):
        for col in (q2_col, q3_col):
            ws.cell(row=row, column=col).alignment = Alignment(wrap_text=True, vertical="top")


def update(wb, students: list[dict], lab_number: int, q2_comments, q3_comments) -> None:
    """Rewrite the sheet for ``students``, clearing any longer previous roster."""
    ws = wb[SHEET_NAME] if SHEET_NAME in wb.sheetnames else wb.create_sheet(SHEET_NAME)
    q2_col, q3_col = ensure_columns(ws, lab_number)

    for index, student in enumerate(students, start=2):
        ws.cell(row=index, column=1).value = student.get("nro")
        ws.cell(row=index, column=2).value = student.get("code")
        ws.cell(row=index, column=3).value = student.get("name")
        for col, comments in ((q2_col, q2_comments), (q3_col, q3_comments)):
            found = comments.find(student, default=[])
            ws.cell(row=index, column=col).value = COMMENT_SEPARATOR.join(found) if found else ""

    for row in range(len(students) + 2, ws.max_row + 1):
        for col in (1, 2, 3, q2_col, q3_col):
            ws.cell(row=row, column=col).value = None

    style(ws, q2_col, q3_col)
