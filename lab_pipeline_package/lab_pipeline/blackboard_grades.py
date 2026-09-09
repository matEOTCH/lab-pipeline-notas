"""Reading a grade column out of a Blackboard grade-centre download."""

from __future__ import annotations

import csv
import re
from pathlib import Path

from .common import clean_text, normalize_header, normalize_student_code


# The student-code column, across Blackboard's interface languages.
CODE_ALIASES = (
    "nombre de usuario",
    "nombre usuario",
    "username",
    "user name",
    "id de usuario",
    "user id",
    "userid",
    "nome de usuario",
)

# Grade-centre exports always carry these; whatever else is present is a grade.
NON_GRADE_COLUMNS = {
    # Spanish
    "apellidos", "nombre", "nombre de usuario", "id de estudiante",
    "ultimo acceso", "disponibilidad",
    # English
    "last name", "first name", "username", "student id",
    "last access", "availability",
}

# Files we cannot read as text: a genuine spreadsheet rather than Blackboard's
# tab-separated export that merely carries an .xls extension.
BINARY_SIGNATURES = {
    b"PK\x03\x04": ".xlsx/.ods (a real spreadsheet)",
    b"\xd0\xcf\x11\xe0": ".xls (a real Excel binary)",
}


def normalize_grade_value(value):
    """"12,5" -> 12.5, "18" -> 18, "" / "-" / junk -> None."""
    text = clean_text(value).replace(",", ".")
    if not text or text == "-":
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    number = float(match.group(0))
    return int(number) if number.is_integer() else number


def read_grade_file(path: Path) -> list[dict[str, str]]:
    """Blackboard exports .xls files that are really UTF-16 TSV."""
    path = Path(path)
    raw = path.read_bytes()

    for signature, description in BINARY_SIGNATURES.items():
        if raw.startswith(signature):
            raise ValueError(
                f"'{path.name}' es {description}, no la descarga directa de Blackboard. "
                "Vuelva a descargar el archivo del Centro de calificaciones sin abrirlo en Excel, "
                "o guardelo como CSV."
            )

    encoding = "utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig"
    try:
        text = raw.decode(encoding)
    except UnicodeDecodeError as exc:
        raise ValueError(
            f"No pude leer '{path.name}' como texto ({encoding}). "
            "Descargue de nuevo el archivo desde Blackboard o guardelo como CSV."
        ) from exc

    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except Exception:
        dialect = csv.excel_tab if path.suffix.lower() in (".xls", ".tsv") else csv.excel
    return list(csv.DictReader(text.splitlines(), dialect=dialect))


def read_headers_and_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    rows = read_grade_file(path)
    if not rows:
        raise ValueError("El archivo de Blackboard esta vacio.")
    # Ragged rows make csv.DictReader emit a None key; drop it.
    headers = [header for header in rows[0].keys() if header is not None]
    return headers, rows


def find_code_column(headers: list[str]) -> str | None:
    """The header holding the student code, whatever Blackboard called it."""
    normalized = {normalize_header(header): header for header in headers}
    for alias in CODE_ALIASES:
        if alias in normalized:
            return normalized[alias]
    # Fall back to a containment match: some exports append notes to the header.
    for norm, original in normalized.items():
        if any(alias in norm for alias in CODE_ALIASES):
            return original
    return None


def grade_column_candidates(headers: list[str], code_column: str | None = None) -> list[str]:
    """Everything that isn't an identity column is a candidate grade column."""
    candidates = [
        header
        for header in headers
        if header != code_column and normalize_header(header) not in NON_GRADE_COLUMNS
    ]
    if not candidates:
        raise ValueError("No encontre columnas de nota en el archivo de Blackboard.")
    return candidates


def rank_grade_candidates(candidates: list[str]) -> list[str]:
    """Sort candidates so likely test/quiz columns come first.

    Blackboard grade-centre exports usually mix in unrelated columns (labs,
    portfolios, attendance); when asking which one to use, we default to
    showing "test"/"prueba" columns first since that is what is picked most often.
    """

    def is_test_like(header: str) -> bool:
        normalized = normalize_header(header)
        return "test" in normalized or "prueba" in normalized

    return sorted(candidates, key=lambda header: 0 if is_test_like(header) else 1)


def parse_grades(path: Path, score_column: str | None = None) -> dict[str, object]:
    """``{student code: grade}``.

    ``score_column`` may be omitted when the file has exactly one grade column.
    """
    headers, rows = read_headers_and_rows(path)
    code_col = find_code_column(headers)
    if not code_col:
        raise ValueError(
            "No encontre la columna 'Nombre de usuario' en el archivo de Blackboard.\n"
            f"Columnas detectadas en '{Path(path).name}': "
            f"{', '.join(str(header) for header in headers) or '(ninguna)'}\n"
            "Revise que sea la descarga del Centro de calificaciones y no otro archivo "
            "(por ejemplo el CSV de Teammates)."
        )

    if score_column is None:
        candidates = grade_column_candidates(headers, code_col)
        if len(candidates) > 1:
            raise ValueError(
                "El archivo tiene varias columnas de nota; indique cual usar: " + ", ".join(candidates)
            )
        score_column = candidates[0]

    grades = {}
    for row in rows:
        code = normalize_student_code(row.get(code_col))
        grade = normalize_grade_value(row.get(score_column))
        if code and grade is not None:
            grades[code] = grade
    return grades
