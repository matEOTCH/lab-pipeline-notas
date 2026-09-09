from __future__ import annotations

from pathlib import Path

import pytest

from lab_pipeline import naming


def test_lista_and_notas_paths_round_trip(course_root: Path):
    lista = naming.lista_path(course_root, "315")
    notas = naming.notas_path(course_root, "315")

    assert lista.name == "315-Lista.xlsx"
    assert notas.name == "315-Notas-Laboratorios.xlsx"
    assert naming.section_from_lista_path(lista) == "315"


def test_bajas_paths_round_trip(course_root: Path):
    lista_bajas = naming.bajas_lista_path(course_root, "315")
    notas_bajas = naming.bajas_notas_path(course_root, "315")

    assert lista_bajas.name == "315-Lista-Bajas.xlsx"
    assert notas_bajas.name == "315-Notas-Laboratorios-Bajas.xlsx"
    assert lista_bajas.parent.name == "Bajas"
    assert notas_bajas.parent.name == "Bajas"


def test_create_base_structure_creates_the_three_folders(tmp_path: Path):
    folders = naming.create_base_structure(tmp_path / "curso")

    assert set(folders) == {"Notas", "Lista", "Grupos Laboratorio"}
    assert all(folder.is_dir() for folder in folders.values())


def test_lab_output_paths_all_live_in_the_lab_folder(course_root: Path):
    folder = naming.lab_folder(course_root, "315", 2)
    outputs = naming.lab_output_paths(course_root, "315", 2)

    assert folder.name == "Laboratorio 2"
    assert all(path.parent == folder for path in outputs.values())
    assert outputs["pdf"].name == "315-Grupos-Laboratorio-2.pdf"
    assert outputs["groups_csv"].name == "Blackboard_Groups_315.csv"
    assert outputs["members_csv"].name == "Blackboard_Members_Lab2_315.csv"
    assert outputs["zip"].name == "315-Laboratorio-2-Blackboard-y-Grupos.zip"


def test_existing_lab_outputs_reports_only_what_exists(course_root: Path):
    outputs = naming.lab_output_paths(course_root, "315", 1)
    outputs["pdf"].parent.mkdir(parents=True, exist_ok=True)
    outputs["pdf"].write_bytes(b"%PDF-1.4")

    found = naming.existing_lab_outputs(course_root, "315", 1)

    assert found["pdf"] == outputs["pdf"]
    assert found["zip"] is None


def test_discovery_finds_what_the_writers_wrote(workspace: Path, course_root: Path):
    naming.lista_path(course_root, "315").write_bytes(b"")
    naming.lista_path(course_root, "307").write_bytes(b"")
    naming.notas_path(course_root, "412").write_bytes(b"")
    naming.lab_folder(course_root, "315", 3).mkdir(parents=True)
    naming.lab_folder(course_root, "315", 1).mkdir(parents=True)

    assert [path.name for path in naming.projects_in(workspace)] == ["2026"]
    assert [path.name for path in naming.course_roots_in(workspace / "2026")] == ["Quimica General 2026-1"]
    assert naming.sections_in(course_root) == ["307", "315", "412"]
    assert naming.labs_in(course_root, "315") == [1, 3]
    assert naming.labs_in(course_root, "307") == []


def test_projects_skips_hidden_and_infrastructure_folders(workspace: Path):
    workspace.mkdir(parents=True)
    for name in (".config", "lab_pipeline", "__pycache__", "web_uploads", "2026"):
        (workspace / name).mkdir()

    assert [path.name for path in naming.projects_in(workspace)] == ["2026"]


def test_discovery_on_missing_folders_returns_empty(tmp_path: Path):
    missing = tmp_path / "nope"

    assert naming.projects_in(missing) == []
    assert naming.course_roots_in(missing) == []
    assert naming.sections_in(missing) == []
    assert naming.labs_in(missing, "315") == []
    assert naming.lista_files_in(missing) == []


@pytest.mark.parametrize(
    ("folder_name", "expected"),
    [
        ("Quimica General 2026-1", ("Quimica General", "2026-1")),
        ("Quimica 2026-1", ("Quimica", "2026-1")),
        ("SinCiclo", ("SinCiclo", "")),
    ],
)
def test_split_course_cycle(folder_name: str, expected: tuple[str, str]):
    assert naming.split_course_cycle(folder_name) == expected


def test_is_inside_accepts_descendants_and_the_root_itself(tmp_path: Path):
    root = tmp_path / "workspace"
    (root / "2026").mkdir(parents=True)

    assert naming.is_inside(root, root)
    assert naming.is_inside(root / "2026", root)
    assert not naming.is_inside(tmp_path / "otro", root)
    assert not naming.is_inside(Path("/etc/passwd"), root)


def test_is_inside_rejects_traversal(tmp_path: Path):
    root = tmp_path / "workspace"
    root.mkdir()

    assert not naming.is_inside(root / ".." / ".." / "etc", root)


def test_resolve_inside_raises_for_escapes(tmp_path: Path):
    root = tmp_path / "workspace"
    (root / "2026").mkdir(parents=True)

    assert naming.resolve_inside(root / "2026", root) == (root / "2026").resolve()
    with pytest.raises(ValueError):
        naming.resolve_inside(Path("/etc/passwd"), root)
