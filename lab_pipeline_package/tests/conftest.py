from __future__ import annotations

import sys
from pathlib import Path

import pytest
from openpyxl import Workbook

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from lab_pipeline import naming  # noqa: E402


STUDENTS = [
    ("20250001", "ALVAREZ, ANA"),
    ("20250002", "BENITEZ, BRUNO"),
    ("20250003", "CASTRO, CARLA"),
    ("20250004", "DIAZ, DIEGO"),
    ("20250005", "ESPINOZA, ELENA"),
    ("20250006", "FLORES, FABIO"),
]


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    return tmp_path / "workspace"


@pytest.fixture
def course_root(workspace: Path) -> Path:
    root = workspace / "2026" / "Quimica General 2026-1"
    naming.create_base_structure(root)
    return root


def write_notas_workbook(path: Path, students=STUDENTS, domain: str = "aloe.ulima.edu.pe") -> Path:
    """A minimal Notas workbook shaped like the real one: header row 1, 4 columns."""
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "Lista"
    ws.append(["Nro.", "Codigo", "Nombre Completo", "Email"])
    for index, (code, name) in enumerate(students, start=1):
        ws.append([index, code, name, f"{code}@{domain}"])
    wb.save(path)
    return path


@pytest.fixture
def notas_path(course_root: Path) -> Path:
    return write_notas_workbook(naming.notas_path(course_root, "315"))


@pytest.fixture
def lista_path(course_root: Path) -> Path:
    return write_notas_workbook(naming.lista_path(course_root, "315"))


@pytest.fixture
def roster_csv(tmp_path: Path) -> Path:
    """A Blackboard course-activity export, with the BOM the real one carries."""
    path = tmp_path / "blackboard_roster.csv"
    lines = ["Apellido,Nombre,Nombre de usuario,Ultimo acceso"]
    for code, full_name in STUDENTS:
        apellido, nombre = full_name.split(", ")
        lines.append(f"{apellido},{nombre},{code},2026-03-01")
    path.write_text("﻿" + "\n".join(lines) + "\n", encoding="utf-8")
    return path
