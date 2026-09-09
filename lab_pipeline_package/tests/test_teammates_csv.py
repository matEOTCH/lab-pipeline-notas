from __future__ import annotations

from pathlib import Path

import pytest

from lab_pipeline import teammates_csv


def write_export(path: Path, per_criterion: bool = True) -> Path:
    """A TeamMates export in the real shape: labelled sections, blank-separated."""
    score_header = "Team,Recipient Name,Recipient Email,Average,Per Criterion Average"
    if per_criterion:
        rows = [
            "Grupo 1,ALVAREZ ANA,20250001@aloe.ulima.edu.pe,4,\"4, 4, 4, 4, 4\"",
            "Grupo 1,BENITEZ BRUNO,20250002@aloe.ulima.edu.pe,3.5,\"3, 4, 3.5, 3.5, 3\"",
        ]
    else:
        rows = [
            "Grupo 1,ALVAREZ ANA,20250001@aloe.ulima.edu.pe,4,",
            "Grupo 1,BENITEZ BRUNO,20250002@aloe.ulima.edu.pe,3.5,",
        ]

    path.write_text(
        "\n".join([
            "Session Summary",
            "",
            "Per Recipient Statistics (Overall)",
            score_header,
            *rows,
            "",
            "Question 2",
            "Giver's Name,Recipient's Name,Recipient's Email,Feedback,Giver's Comment",
            "BENITEZ BRUNO,ALVAREZ ANA,20250001@aloe.ulima.edu.pe,Muy colaborativa,",
            "CASTRO CARLA,ALVAREZ ANA,20250001@aloe.ulima.edu.pe,Buena lider,Sigue asi",
            "",
            "Question 3",
            "Giver's Name,Recipient's Name,Recipient's Email,Feedback,Giver's Comment",
            "ALVAREZ ANA,BENITEZ BRUNO,20250002@aloe.ulima.edu.pe,Puede participar mas,",
            "",
            "Participants who have not responded to any question",
            "Name,Email",
            "CASTRO CARLA,20250003@aloe.ulima.edu.pe",
            "",
        ]) + "\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def export_path(tmp_path: Path) -> Path:
    return write_export(tmp_path / "teammates.csv")


def test_scores_sum_the_per_criterion_values(export_path: Path):
    export = teammates_csv.TeammatesExport.from_path(export_path)

    ana = export.scores.by_code["20250001"]
    assert ana["tm_total"] == 20
    assert ana["tm_percentage"] == 1.0
    bruno = export.scores.by_code["20250002"]
    assert bruno["tm_total"] == 17
    assert bruno["tm_percentage"] == 0.85


def test_scores_fall_back_to_average_times_criteria_count(tmp_path: Path):
    export = teammates_csv.TeammatesExport.from_path(
        write_export(tmp_path / "no_criteria.csv", per_criterion=False)
    )

    assert export.scores.by_code["20250001"]["tm_total"] == 20
    assert export.scores.by_code["20250002"]["tm_total"] == 17.5


def test_scores_are_indexed_by_code_email_and_name(export_path: Path):
    export = teammates_csv.TeammatesExport.from_path(export_path)

    assert "20250001" in export.scores.by_code
    assert "20250001@aloe.ulima.edu.pe" in export.scores.by_email
    assert "ALVAREZ ANA" in export.scores.by_name


def test_lookup_prefers_code_then_email_then_name(export_path: Path):
    export = teammates_csv.TeammatesExport.from_path(export_path)

    by_code = export.scores.find({"code": "20250002", "email": "", "name": ""})
    by_email = export.scores.find({"code": "", "email": "20250002@aloe.ulima.edu.pe", "name": ""})
    by_name = export.scores.find({"code": "", "email": "", "name": "Benitez Bruno"})

    assert by_code["code"] == by_email["code"] == by_name["code"] == "20250002"
    assert export.scores.find({"code": "99999999", "email": "", "name": ""}) is None


def test_non_responders_are_collected(export_path: Path):
    export = teammates_csv.TeammatesExport.from_path(export_path)

    assert export.non_responder_codes == {"20250003"}
    assert not export.responded({"code": "20250003", "email": "", "name": ""})
    assert export.responded({"code": "20250001", "email": "", "name": ""})


def test_comments_are_grouped_per_recipient_and_attributed(export_path: Path):
    export = teammates_csv.TeammatesExport.from_path(export_path)

    ana_q2 = export.q2_comments.by_code["20250001"]
    assert ana_q2 == ["Muy colaborativa (BENITEZ BRUNO)", "Buena lider - Sigue asi (CASTRO CARLA)"]
    assert export.q3_comments.by_code["20250002"] == ["Puede participar mas (ALVAREZ ANA)"]
    assert export.q2_comments.find({"code": "20250002", "email": "", "name": ""}, default=[]) == []


def test_comment_sections_do_not_bleed_into_each_other(export_path: Path):
    export = teammates_csv.TeammatesExport.from_path(export_path)

    assert "20250002" not in export.q2_comments.by_code
    assert "20250001" not in export.q3_comments.by_code


def test_missing_overall_section_is_an_error(tmp_path: Path):
    path = tmp_path / "bad.csv"
    path.write_text("Something else\nA,B\n1,2\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Per Recipient Statistics"):
        teammates_csv.TeammatesExport.from_path(path)


def test_missing_optional_sections_degrade_quietly(tmp_path: Path):
    path = tmp_path / "scores_only.csv"
    path.write_text(
        "Per Recipient Statistics (Overall)\n"
        "Recipient Name,Recipient Email,Per Criterion Average\n"
        "ALVAREZ ANA,20250001@aloe.ulima.edu.pe,\"4, 4, 4, 4, 4\"\n",
        encoding="utf-8",
    )

    export = teammates_csv.TeammatesExport.from_path(path)

    assert export.scores.by_code["20250001"]["tm_total"] == 20
    assert export.non_responder_codes == set()
    assert len(export.q2_comments) == 0


def test_code_from_email_and_float_list_helpers():
    assert teammates_csv.code_from_email("20250001@aloe.ulima.edu.pe") == "20250001"
    assert teammates_csv.code_from_email("sin-arroba") == ""
    assert teammates_csv.parse_float_list("4, 3.5, 2") == [4.0, 3.5, 2.0]
