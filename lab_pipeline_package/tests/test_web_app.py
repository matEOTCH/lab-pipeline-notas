from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from lab_pipeline import naming, services
from lab_pipeline.web_app import create_web_app
from tests.test_teammates_csv import write_export


@pytest.fixture
def client(workspace: Path):
    workspace.mkdir(parents=True, exist_ok=True)
    app = create_web_app(workspace_root=workspace)
    app.config.update(TESTING=True)
    with app.test_client() as test_client:
        test_client.workspace = workspace
        yield test_client


@pytest.fixture
def section(client, roster_csv: Path):
    return services.create_structure(
        workspace_root=client.workspace,
        project_name="2026",
        course_cycle_name="Quimica General 2026-1",
        section="315",
        email_domain="aloe.ulima.edu.pe",
        csv_path=roster_csv,
    )


# --- containment (regression tests for the arbitrary-path read) ---------------


def test_file_route_refuses_paths_outside_the_workspace(client):
    response = client.get("/file", query_string={"path": "/etc/passwd"})

    assert response.status_code == 400
    assert "workspace" in response.get_json()["error"]


def test_file_route_refuses_traversal_out_of_the_workspace(client):
    response = client.get("/file", query_string={"path": str(client.workspace / ".." / ".." / "etc" / "passwd")})

    assert response.status_code == 400


def test_file_route_serves_a_file_inside_the_workspace(client):
    target = client.workspace / "2026" / "nota.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("hola", encoding="utf-8")

    response = client.get("/file", query_string={"path": str(target)})

    assert response.status_code == 200
    assert response.data == b"hola"


def test_file_route_404s_for_a_missing_file_inside_the_workspace(client):
    response = client.get("/file", query_string={"path": str(client.workspace / "ausente.txt")})

    assert response.status_code == 404


@pytest.mark.parametrize(
    ("route", "params"),
    [
        ("/api/courses", {"project_root": "/etc"}),
        ("/api/sections", {"course_root": "/etc"}),
        ("/api/labs", {"course_root": "/etc", "section": "315"}),
        ("/api/students", {"course_root": "/etc", "section": "315"}),
    ],
)
def test_get_routes_refuse_paths_outside_the_workspace(client, route: str, params: dict):
    response = client.get(route, query_string=params)

    assert response.status_code == 400


def test_post_routes_refuse_paths_outside_the_workspace(client):
    response = client.post(
        "/api/groups/preview",
        json={"course_root": "/etc", "section": "315", "group_count": 2},
    )

    assert response.status_code == 400


# --- normal operation ---------------------------------------------------------


def test_index_serves_the_app_html(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"Lab Manager" in response.data


def test_status_lists_projects_courses_and_sections(client, section):
    payload = client.get("/api/status").get_json()

    assert payload["workspace"] == str(client.workspace.resolve())
    assert [project["name"] for project in payload["projects"]] == ["2026"]
    course = payload["projects"][0]["courses"][0]
    assert course["name"] == "Quimica General 2026-1"
    assert course["status"]["sections"] == ["315"]


def test_courses_sections_and_students_routes(client, section):
    courses = client.get("/api/courses", query_string={"project_root": str(section["project_root"])}).get_json()
    assert [course["name"] for course in courses] == ["Quimica General 2026-1"]

    course_root = str(section["course_root"])
    assert client.get("/api/sections", query_string={"course_root": course_root}).get_json() == ["315"]

    students = client.get(
        "/api/students", query_string={"course_root": course_root, "section": "315"}
    ).get_json()
    assert len(students) == 6

    filtered = client.get(
        "/api/students", query_string={"course_root": course_root, "section": "315", "initial": "c"}
    ).get_json()
    assert [student["name"] for student in filtered] == ["CASTRO, CARLA"]


def test_structure_preview_and_create(client, roster_csv: Path):
    preview = client.post(
        "/api/structure/preview",
        data={"email_domain": "aloe.ulima.edu.pe", "csv": (io.BytesIO(roster_csv.read_bytes()), "roster.csv")},
        content_type="multipart/form-data",
    ).get_json()
    assert preview["students_count"] == 6

    created = client.post(
        "/api/structure/create",
        data={
            "project_name": "2026",
            "course_cycle_name": "Quimica General 2026-1",
            "section": "307",
            "email_domain": "aloe.ulima.edu.pe",
            "csv": (io.BytesIO(roster_csv.read_bytes()), "roster.csv"),
        },
        content_type="multipart/form-data",
    )
    assert created.status_code == 200
    assert Path(created.get_json()["notas_path"]).exists()


def test_creating_an_existing_section_without_overwrite_is_a_conflict(client, section, roster_csv: Path):
    response = client.post(
        "/api/structure/create",
        data={
            "project_name": "2026",
            "course_cycle_name": "Quimica General 2026-1",
            "section": "315",
            "email_domain": "aloe.ulima.edu.pe",
            "csv": (io.BytesIO(roster_csv.read_bytes()), "roster.csv"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 409


def test_groups_preview_then_create_then_labs_route(client, section):
    course_root = str(section["course_root"])
    payload = {
        "course_root": course_root,
        "section": "315",
        "professor": "Perez, Martin",
        "jefe": "Tapia, Mateo",
        "lab_number": 1,
        "group_count": 3,
        "seed": 5,
    }

    preview = client.post("/api/groups/preview", json=payload).get_json()
    assert sum(preview["group_sizes"]) == 6

    created = client.post("/api/groups/create", json=payload)
    assert created.status_code == 200
    assert Path(created.get_json()["zip_path"]).exists()

    labs = client.get("/api/labs", query_string={"course_root": course_root, "section": "315"}).get_json()
    assert labs == [1]


def test_evaluation_accepts_index_keyed_payloads(client, section):
    """The browser keys uploads by template index; the server names the column."""
    course_root = str(section["course_root"])
    client.post("/api/groups/create", json={
        "course_root": course_root, "section": "315", "professor": "P", "jefe": "J",
        "lab_number": 1, "group_count": 2, "seed": 3,
    })

    grade_file = b"Apellidos,Nombre,Nombre de usuario,Quiz\nAlvarez,Ana,20250001,19\n"
    response = client.post(
        "/api/evaluation/apply",
        data={
            "course_root": course_root,
            "section": "315",
            "lab_number": "1",
            # A base name with a space: the old client-side name derivation broke here.
            "templates": json.dumps([{"base_name": "Quiz Lab", "method": "1"}]),
            "grade_file__0": (io.BytesIO(grade_file), "quiz.csv"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert response.get_json()["custom_updates"] == {"Quiz_Lab1": 1}


def test_evaluation_applies_teammates_and_absences(client, section, tmp_path: Path):
    course_root = str(section["course_root"])
    client.post("/api/groups/create", json={
        "course_root": course_root, "section": "315", "professor": "P", "jefe": "J",
        "lab_number": 1, "group_count": 2, "seed": 3,
    })
    export = write_export(tmp_path / "tm.csv")

    response = client.post(
        "/api/evaluation/apply",
        data={
            "course_root": course_root,
            "section": "315",
            "lab_number": "1",
            "templates": json.dumps([]),
            "absent_codes": json.dumps(["20250004"]),
            "teammates": (io.BytesIO(export.read_bytes()), "tm.csv"),
        },
        content_type="multipart/form-data",
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["tm_result"]["updated_tm"] == 2
    assert payload["absences"]["absences_updated"] == 1


def test_absences_route(client, section):
    course_root = str(section["course_root"])
    client.post("/api/groups/create", json={
        "course_root": course_root, "section": "315", "professor": "P", "jefe": "J",
        "lab_number": 1, "group_count": 2, "seed": 3,
    })

    response = client.post("/api/absences/apply", json={
        "course_root": course_root,
        "section": "315",
        "lab_number": 1,
        "absent_codes": ["20250002", "99999999"],
    })

    payload = response.get_json()
    assert payload["absences_updated"] == 1
    assert payload["not_found_codes"] == ["99999999"]


def test_a_missing_required_field_is_a_400(client):
    assert client.get("/api/sections").status_code == 400


def test_a_missing_lista_is_a_404(client, section):
    response = client.get(
        "/api/students",
        query_string={"course_root": str(section["course_root"]), "section": "999"},
    )

    assert response.status_code == 404
