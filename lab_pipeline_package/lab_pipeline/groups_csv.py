"""Reading a fixed grouping out of a groups CSV (Blackboard export, or our own
``members_csv`` from ``outputs.write_blackboard_csvs``)."""

from __future__ import annotations

from pathlib import Path

from .common import normalize_header, normalize_student_code
from .rosters import read_delimited


CODE_ALIASES = (
    "nombre de usuario",
    "nombre usuario",
    "username",
    "user name",
    "id de usuario",
    "user id",
    "userid",
    "student id",
    "codigo",
)

GROUP_CODE_ALIASES = (
    "group code",
    "codigo de grupo",
    "group name",
    "group",
)


def _find_column(headers: list[str], aliases: tuple[str, ...]) -> str | None:
    normalized = {normalize_header(header): header for header in headers}
    for alias in aliases:
        if alias in normalized:
            return normalized[alias]
    for norm, original in normalized.items():
        if any(alias in norm for alias in aliases):
            return original
    return None


def find_code_column(headers: list[str]) -> str | None:
    return _find_column(headers, CODE_ALIASES)


def find_group_code_column(headers: list[str]) -> str | None:
    return _find_column(headers, GROUP_CODE_ALIASES)


def parse_groups_csv(path: Path) -> dict[str, int]:
    """``{student code: group number}``.

    Each distinct value in the group-code column becomes one group, numbered
    1..N in the order it first appears — robust to whatever naming scheme the
    export used (Blackboard's own group codes, or our own ``Grupo_gc_LabN_``
    prefix), since only the grouping the codes express matters, not their text.
    """
    rows = read_delimited(Path(path))
    if not rows:
        raise ValueError("El CSV de grupos esta vacio.")

    headers = list(rows[0].keys())
    code_col = find_code_column(headers)
    if not code_col:
        raise ValueError(f"No encontre una columna de codigo de alumno en el CSV. Columnas: {', '.join(headers)}")
    group_col = find_group_code_column(headers)
    if not group_col:
        raise ValueError(f"No encontre una columna de codigo de grupo en el CSV. Columnas: {', '.join(headers)}")

    mapping: dict[str, int] = {}
    group_numbers: dict[str, int] = {}
    for row in rows:
        code = normalize_student_code(row.get(code_col))
        group_code = str(row.get(group_col) or "").strip()
        if not code or not group_code:
            continue
        if group_code not in group_numbers:
            group_numbers[group_code] = len(group_numbers) + 1
        mapping[code] = group_numbers[group_code]

    if not mapping:
        raise ValueError("No pude leer ninguna asignacion de grupo valida del CSV.")
    return mapping
