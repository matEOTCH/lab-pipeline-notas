from __future__ import annotations

from pathlib import Path

import pytest

from lab_pipeline import blackboard_grades


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("18", 18),
        ("12,5", 12.5),
        ("12.5", 12.5),
        ("  20  ", 20),
        ("Nota: 15", 15),
        ("-", None),
        ("", None),
        (None, None),
        ("sin nota", None),
    ],
)
def test_normalize_grade_value(raw, expected):
    assert blackboard_grades.normalize_grade_value(raw) == expected


def write_grade_file(path: Path, extra_columns: str = "", extra_values: str = "") -> Path:
    path.write_text(
        f"Apellidos,Nombre,Nombre de usuario,Ultimo acceso,Quiz Lab 1 [Total Pts: 20]{extra_columns}\n"
        f"Alvarez,Ana,20250001,2026-03-01,18{extra_values}\n"
        f"Benitez,Bruno,20250002,2026-03-01,12,5{extra_values}\n"
        f"Castro,Carla,20250003,2026-03-01,-{extra_values}\n",
        encoding="utf-8",
    )
    return path


def test_parses_the_single_grade_column(tmp_path: Path):
    grades = blackboard_grades.parse_grades(write_grade_file(tmp_path / "grades.csv"))

    assert grades == {"20250001": 18, "20250002": 12}
    assert "20250003" not in grades


def test_identifies_grade_columns_by_excluding_the_standard_ones(tmp_path: Path):
    headers = ["Apellidos", "Nombre", "Nombre de usuario", "Ultimo acceso", "Quiz Lab 1"]

    assert blackboard_grades.grade_column_candidates(headers) == ["Quiz Lab 1"]


def test_several_grade_columns_require_an_explicit_choice(tmp_path: Path):
    path = write_grade_file(tmp_path / "two.csv", extra_columns=",Informe", extra_values=",15")

    with pytest.raises(ValueError, match="varias columnas"):
        blackboard_grades.parse_grades(path)

    assert blackboard_grades.parse_grades(path, score_column="Informe")["20250001"] == 15


def test_reads_the_utf16_tab_separated_xls_blackboard_actually_exports(tmp_path: Path):
    path = tmp_path / "grades.xls"
    text = (
        "Apellidos\tNombre\tNombre de usuario\tQuiz Lab 1\n"
        "Alvarez\tAna\t20250001\t18\n"
        "Benitez\tBruno\t20250002\t14\n"
    )
    path.write_bytes(text.encode("utf-16"))

    assert blackboard_grades.parse_grades(path) == {"20250001": 18, "20250002": 14}


def test_missing_username_column_is_an_error(tmp_path: Path):
    path = tmp_path / "grades.csv"
    path.write_text("Apellidos,Nombre,Quiz\nAlvarez,Ana,18\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Nombre de usuario"):
        blackboard_grades.parse_grades(path)


def test_empty_file_is_an_error(tmp_path: Path):
    path = tmp_path / "grades.csv"
    path.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="vacio"):
        blackboard_grades.parse_grades(path)


# --- locale and wrong-file handling (regressions from a real Colab failure) ---


def test_finds_the_code_column_in_an_english_export(tmp_path: Path):
    path = tmp_path / "grades.xls"
    path.write_text(
        "Last Name\tFirst Name\tUsername\tStudent ID\tQuiz Lab 1\n"
        "Alvarez\tAna\t20250001\t\t18\n",
        encoding="utf-8",
    )

    assert blackboard_grades.parse_grades(path) == {"20250001": 18}


@pytest.mark.parametrize("header", ["Nombre de usuario", "Username", "User Id", "ID de usuario"])
def test_code_column_aliases(tmp_path: Path, header: str):
    path = tmp_path / "grades.csv"
    path.write_text(f"Apellidos,Nombre,{header},Quiz\nAlvarez,Ana,20250001,18\n", encoding="utf-8")

    assert blackboard_grades.parse_grades(path) == {"20250001": 18}


def test_the_code_column_is_never_mistaken_for_a_grade_column(tmp_path: Path):
    """A non-standard code header must not also count as a grade candidate."""
    path = tmp_path / "grades.csv"
    path.write_text("Apellidos,Nombre,User Id,Quiz\nAlvarez,Ana,20250001,18\n", encoding="utf-8")

    assert blackboard_grades.grade_column_candidates(
        ["Apellidos", "Nombre", "User Id", "Quiz"], "User Id"
    ) == ["Quiz"]


def test_the_wrong_file_names_the_columns_it_found(tmp_path: Path):
    path = tmp_path / "teammates.csv"
    path.write_text(
        "Per Recipient Statistics (Overall)\n"
        "Team,Recipient Name,Recipient Email,Average\n"
        "Grupo 1,ALVAREZ ANA,a@b.c,4\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as excinfo:
        blackboard_grades.parse_grades(path)

    message = str(excinfo.value)
    assert "Columnas detectadas" in message
    assert "Per Recipient Statistics" in message
    assert "Teammates" in message


def test_a_real_spreadsheet_is_rejected_with_a_clear_message(tmp_path: Path):
    from openpyxl import Workbook

    path = tmp_path / "grades.xlsx"
    wb = Workbook()
    wb.active.append(["Apellidos", "Nombre", "Nombre de usuario", "Quiz"])
    wb.save(path)

    with pytest.raises(ValueError, match="no la descarga directa de Blackboard"):
        blackboard_grades.parse_grades(path)
