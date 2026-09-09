from __future__ import annotations

from pathlib import Path

import pytest

from lab_pipeline import groups_csv


def test_numbers_groups_by_order_of_first_appearance(tmp_path: Path):
    path = tmp_path / "grupos.csv"
    path.write_text(
        "Group Code*,User Name*\n"
        "Grupo_gc_Lab1_3,20250003\n"
        "Grupo_gc_Lab1_1,20250001\n"
        "Grupo_gc_Lab1_1,20250002\n",
        encoding="utf-8",
    )

    assert groups_csv.parse_groups_csv(path) == {"20250003": 1, "20250001": 2, "20250002": 2}


def test_round_trips_the_exact_members_csv_shape_this_tool_writes(tmp_path: Path):
    """Headers match outputs.MEMBERS_CSV_HEADERS exactly."""
    path = tmp_path / "members.csv"
    path.write_text(
        "Group Code*,User Name*,Student Id,First Name,Last Name,Group Set\n"
        "Grupo_gc_Lab1_1,20250001,,Ana,Alvarez,Laboratorio_1\n"
        "Grupo_gc_Lab1_2,20250002,,Bruno,Benitez,Laboratorio_1\n",
        encoding="utf-8",
    )

    assert groups_csv.parse_groups_csv(path) == {"20250001": 1, "20250002": 2}


@pytest.mark.parametrize("header", ["Nombre de usuario", "Username", "User Id", "Student Id"])
def test_code_column_aliases(tmp_path: Path, header: str):
    path = tmp_path / "grupos.csv"
    path.write_text(f"Group Code*,{header}\nGrupo1,20250001\n", encoding="utf-8")

    assert groups_csv.parse_groups_csv(path) == {"20250001": 1}


def test_normalizes_float_looking_codes(tmp_path: Path):
    path = tmp_path / "grupos.csv"
    path.write_text("Group Code*,User Name*\nGrupo1,20250001.0\n", encoding="utf-8")

    assert groups_csv.parse_groups_csv(path) == {"20250001": 1}


def test_rows_missing_code_or_group_are_skipped(tmp_path: Path):
    path = tmp_path / "grupos.csv"
    path.write_text(
        "Group Code*,User Name*\nGrupo1,20250001\n,20250002\nGrupo2,\n",
        encoding="utf-8",
    )

    assert groups_csv.parse_groups_csv(path) == {"20250001": 1}


def test_missing_group_code_column_is_an_error(tmp_path: Path):
    path = tmp_path / "grupos.csv"
    path.write_text("User Name*\n20250001\n", encoding="utf-8")

    with pytest.raises(ValueError, match="codigo de grupo"):
        groups_csv.parse_groups_csv(path)


def test_missing_code_column_is_an_error(tmp_path: Path):
    path = tmp_path / "grupos.csv"
    path.write_text("Group Code*\nGrupo1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="codigo de alumno"):
        groups_csv.parse_groups_csv(path)


def test_empty_file_is_an_error(tmp_path: Path):
    path = tmp_path / "grupos.csv"
    path.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="vacio"):
        groups_csv.parse_groups_csv(path)
