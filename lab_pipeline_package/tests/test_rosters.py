from __future__ import annotations

from pathlib import Path

import pytest

from lab_pipeline import naming, rosters


def test_reads_blackboard_roster_with_bom(roster_csv: Path):
    students = rosters.read_blackboard_roster(roster_csv)

    assert len(students) == 6
    assert students[0] == {"apellido": "ALVAREZ", "nombre": "ANA", "codigo": "20250001"}


def test_roster_is_sorted_by_surname(tmp_path: Path):
    path = tmp_path / "roster.csv"
    path.write_text(
        "Apellido,Nombre,Nombre de usuario\nZAPATA,Zoe,20250009\nABAD,Ada,20250001\n",
        encoding="utf-8",
    )

    students = rosters.read_blackboard_roster(path)

    assert [student["apellido"] for student in students] == ["ABAD", "ZAPATA"]


def test_reads_semicolon_delimited_roster(tmp_path: Path):
    path = tmp_path / "roster.csv"
    path.write_text(
        "Apellido;Nombre;Nombre de usuario\nCASTRO;Carla;20250003\nDIAZ;Diego;20250004\n",
        encoding="utf-8",
    )

    students = rosters.read_blackboard_roster(path)

    assert [student["codigo"] for student in students] == ["20250003", "20250004"]


def test_roster_skips_rows_missing_required_values(tmp_path: Path):
    path = tmp_path / "roster.csv"
    path.write_text(
        "Apellido,Nombre,Nombre de usuario\nCASTRO,Carla,20250003\n,,\nTotal,,\n",
        encoding="utf-8",
    )

    assert len(rosters.read_blackboard_roster(path)) == 1


def test_roster_normalizes_float_looking_codes(tmp_path: Path):
    path = tmp_path / "roster.csv"
    path.write_text("Apellido,Nombre,Nombre de usuario\nCASTRO,Carla,20250003.0\n", encoding="utf-8")

    assert rosters.read_blackboard_roster(path)[0]["codigo"] == "20250003"


def test_roster_rejects_a_file_missing_a_required_column(tmp_path: Path):
    path = tmp_path / "roster.csv"
    path.write_text("Apellido,Nombre\nCASTRO,Carla\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Nombre de usuario"):
        rosters.read_blackboard_roster(path)


def test_roster_rejects_an_empty_file(tmp_path: Path):
    path = tmp_path / "roster.csv"
    path.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="vacio"):
        rosters.read_blackboard_roster(path)


def test_build_clean_list_numbers_rows_and_builds_emails():
    students = [{"apellido": "CASTRO", "nombre": "CARLA", "codigo": "20250003"}]

    rows = rosters.build_clean_list(students, "@aloe.ulima.edu.pe")

    assert rows == [{
        "Nro.": 1,
        "Codigo": "20250003",
        "Nombre Completo": "CASTRO, CARLA",
        "Email": "20250003@aloe.ulima.edu.pe",
    }]


def test_workbook_round_trips_through_parse_student_list(tmp_path: Path, roster_csv: Path):
    rows = rosters.build_clean_list(rosters.read_blackboard_roster(roster_csv), "aloe.ulima.edu.pe")
    out_path = tmp_path / "315-Lista.xlsx"
    rosters.save_students_workbook(rows, out_path)

    section, students = rosters.parse_student_list(out_path)

    assert section == "315"
    assert len(students) == 6
    assert students[0] == {"code": "20250001", "name": "ALVAREZ, ANA"}


def test_parse_student_list_from_csv_with_first_and_last_name(tmp_path: Path):
    path = tmp_path / "307-Lista.csv"
    path.write_text("Codigo,First Name,Last Name\n20250003,Carla,Castro\n", encoding="utf-8")

    section, students = rosters.parse_student_list(path)

    assert section == "307"
    assert students == [{"code": "20250003", "name": "CASTRO, CARLA"}]


def test_parse_student_list_rejects_a_list_without_a_code_column(tmp_path: Path):
    path = tmp_path / "307-Lista.csv"
    path.write_text("Nombre Completo\nCASTRO, CARLA\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Codigo"):
        rosters.parse_student_list(path)


def test_lastname_initial_handles_both_name_shapes():
    assert rosters.lastname_initial({"name": "CASTRO, CARLA"}) == "C"
    assert rosters.lastname_initial({"name": "Zapata Zoe"}) == "Z"
    assert rosters.lastname_initial({"name": ""}) == ""


def test_search_by_lastname_initial_filters_and_excludes():
    students = [
        {"code": "1", "name": "CASTRO, CARLA"},
        {"code": "2", "name": "CORDOVA, CESAR"},
        {"code": "3", "name": "DIAZ, DIEGO"},
    ]

    assert [s["code"] for s in rosters.search_by_lastname_initial(students, "c")] == ["1", "2"]
    assert [s["code"] for s in rosters.search_by_lastname_initial(students, "C", {"1"})] == ["2"]
    assert rosters.search_by_lastname_initial(students, "") == []


def test_saved_workbook_lands_where_naming_says(course_root: Path):
    path = naming.lista_path(course_root, "315")
    rosters.save_students_workbook(
        [{"Nro.": 1, "Codigo": "1", "Nombre Completo": "A, B", "Email": "a@b.c"}], path
    )

    assert path.exists()
    assert naming.sections_in(course_root) == ["315"]
