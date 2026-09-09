from __future__ import annotations

from copy import copy
from pathlib import Path
import re
import unicodedata

from openpyxl.utils import get_column_letter


def clean_text(value) -> str:
    return "" if value is None else str(value).strip()


def decode_csv_bytes(path: Path) -> str:
    """Decode a CSV file, tolerating the Windows-1252 exports Excel/Blackboard produce.

    UTF-8 (with or without a BOM) is tried first; files that were saved as
    Windows-1252 (common for Spanish-locale Excel exports) fail that decode on
    accented or curly-quote bytes, so we fall back to cp1252, which accepts any
    byte value.
    """
    raw = Path(path).read_bytes()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252")


def remove_accents(value) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFD", clean_text(value))
        if unicodedata.category(char) != "Mn"
    )


def normalize_text(value) -> str:
    return re.sub(r"\s+", " ", remove_accents(value).upper()).strip()


def normalize_header(value) -> str:
    text = remove_accents(value).lower()
    text = re.sub(r"[^a-z0-9%?]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_student_code(value) -> str:
    text = clean_text(value)
    if text.lower() in ("nan", "none", ""):
        return ""
    return text[:-2] if re.fullmatch(r"\d+\.0", text) else text


def copy_column_style(ws, source_col: int, target_col: int) -> None:
    source_letter = get_column_letter(source_col)
    target_letter = get_column_letter(target_col)
    ws.column_dimensions[target_letter].width = ws.column_dimensions[source_letter].width

    for row in range(1, ws.max_row + 1):
        source_cell = ws.cell(row=row, column=source_col)
        target_cell = ws.cell(row=row, column=target_col)
        if source_cell.has_style:
            target_cell._style = copy(source_cell._style)
        target_cell.font = copy(source_cell.font)
        target_cell.fill = copy(source_cell.fill)
        target_cell.border = copy(source_cell.border)
        target_cell.alignment = copy(source_cell.alignment)
        target_cell.number_format = source_cell.number_format


def find_header_row_ws(ws, max_scan_rows: int = 30) -> int:
    for row in range(1, min(ws.max_row, max_scan_rows) + 1):
        headers = [normalize_header(ws.cell(row=row, column=col).value) for col in range(1, ws.max_column + 1)]
        has_code = any(h in ("codigo", "code", "student id") or "codigo" in h or "student id" in h for h in headers)
        has_name = any(h in ("nombre completo", "apellidos y nombres", "name", "recipient name") or "nombre" in h for h in headers)
        if has_code and has_name:
            return row
    raise ValueError("Could not find the header row in the workbook.")


def find_col_ws(ws, header_row: int, aliases: list[str], required: bool = True) -> int | None:
    alias_norms = [normalize_header(alias) for alias in aliases]
    for col in range(1, ws.max_column + 1):
        header = normalize_header(ws.cell(row=header_row, column=col).value)
        if not header:
            continue
        if any(header == alias or alias in header or header in alias for alias in alias_norms):
            return col
    if required:
        raise ValueError(f"Could not find column with aliases: {aliases}")
    return None


def find_last_real_header_col(ws, header_row: int) -> int:
    for col in range(ws.max_column, 0, -1):
        if clean_text(ws.cell(row=header_row, column=col).value):
            return col
    raise ValueError("Could not identify the last real header column.")
