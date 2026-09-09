"""Every filesystem convention used by the lab workflows lives here.

A workspace looks like this::

    <workspace>/                      # Drive MyDrive, or cwd outside Colab
      <project>/                      # e.g. "2026"
        .lab_pipeline_settings.json
        <course> <cycle>/             # e.g. "Quimica General 2026-1"
          .lab_group_settings.json
          .grade_upload_settings.json
          Lista/<section>-Lista.xlsx
          Notas/<section>-Notas-Laboratorios.xlsx
          Grupos Laboratorio/<section>/Laboratorio <n>/...
          Bajas/<section>-Lista-Bajas.xlsx
          Bajas/<section>-Notas-Laboratorios-Bajas.xlsx

No other module should build these paths by hand.
"""

from __future__ import annotations

import re
from pathlib import Path


LISTA_FOLDER = "Lista"
NOTAS_FOLDER = "Notas"
GROUPS_FOLDER = "Grupos Laboratorio"
DEFAULT_FOLDERS = (NOTAS_FOLDER, LISTA_FOLDER, GROUPS_FOLDER)

LISTA_SUFFIX = "-Lista.xlsx"
NOTAS_SUFFIX = "-Notas-Laboratorios.xlsx"

BAJAS_FOLDER = "Bajas"
BAJAS_LISTA_SUFFIX = "-Lista-Bajas.xlsx"
BAJAS_NOTAS_SUFFIX = "-Notas-Laboratorios-Bajas.xlsx"

IGNORED_PROJECT_NAMES = {"lab_pipeline", "__pycache__", "uploaded_blackboard_csvs", "web_uploads"}

_LAB_FOLDER_RE = re.compile(r"Laboratorio\s+(\d+)$", flags=re.IGNORECASE)


# --- course-level files -------------------------------------------------------


def lista_path(course_root: Path, section: str) -> Path:
    return Path(course_root) / LISTA_FOLDER / f"{section}{LISTA_SUFFIX}"


def notas_path(course_root: Path, section: str) -> Path:
    return Path(course_root) / NOTAS_FOLDER / f"{section}{NOTAS_SUFFIX}"


def section_from_lista_path(path: Path) -> str:
    return Path(path).name[: -len(LISTA_SUFFIX)].strip()


def bajas_lista_path(course_root: Path, section: str) -> Path:
    return Path(course_root) / BAJAS_FOLDER / f"{section}{BAJAS_LISTA_SUFFIX}"


def bajas_notas_path(course_root: Path, section: str) -> Path:
    return Path(course_root) / BAJAS_FOLDER / f"{section}{BAJAS_NOTAS_SUFFIX}"


def create_base_structure(course_root: Path) -> dict[str, Path]:
    """Create Notas/Lista/Grupos Laboratorio under ``course_root``."""
    folders = {}
    for folder_name in DEFAULT_FOLDERS:
        folder = Path(course_root) / folder_name
        folder.mkdir(parents=True, exist_ok=True)
        folders[folder_name] = folder
    return folders


# --- lab output files ---------------------------------------------------------


def lab_folder(course_root: Path, section: str, lab_number: int) -> Path:
    return Path(course_root) / GROUPS_FOLDER / section / f"Laboratorio {int(lab_number)}"


def groups_pdf_path(course_root: Path, section: str, lab_number: int) -> Path:
    return lab_folder(course_root, section, lab_number) / f"{section}-Grupos-Laboratorio-{int(lab_number)}.pdf"


def blackboard_groups_csv_path(course_root: Path, section: str, lab_number: int) -> Path:
    return lab_folder(course_root, section, lab_number) / f"Blackboard_Groups_{section}.csv"


def blackboard_members_csv_path(course_root: Path, section: str, lab_number: int) -> Path:
    return lab_folder(course_root, section, lab_number) / f"Blackboard_Members_Lab{int(lab_number)}_{section}.csv"


def bundle_zip_path(course_root: Path, section: str, lab_number: int) -> Path:
    lab_number = int(lab_number)
    return lab_folder(course_root, section, lab_number) / f"{section}-Laboratorio-{lab_number}-Blackboard-y-Grupos.zip"


def lab_output_paths(course_root: Path, section: str, lab_number: int) -> dict[str, Path]:
    """The four generated artefacts for one lab, whether or not they exist yet."""
    return {
        "pdf": groups_pdf_path(course_root, section, lab_number),
        "groups_csv": blackboard_groups_csv_path(course_root, section, lab_number),
        "members_csv": blackboard_members_csv_path(course_root, section, lab_number),
        "zip": bundle_zip_path(course_root, section, lab_number),
    }


def existing_lab_outputs(course_root: Path, section: str, lab_number: int) -> dict[str, Path | None]:
    return {
        key: path if path.exists() else None
        for key, path in lab_output_paths(course_root, section, lab_number).items()
    }


# --- discovery ----------------------------------------------------------------


def projects_in(workspace_root: Path) -> list[Path]:
    root = Path(workspace_root)
    if not root.exists():
        return []
    return sorted(
        (
            path
            for path in root.iterdir()
            if path.is_dir() and not path.name.startswith(".") and path.name not in IGNORED_PROJECT_NAMES
        ),
        key=lambda path: path.name,
    )


def course_roots_in(project_root: Path) -> list[Path]:
    """Course/cycle folders: directories carrying at least one of the standard folders."""
    root = Path(project_root)
    if not root.exists():
        return []
    return sorted(
        (
            path
            for path in root.iterdir()
            if path.is_dir() and any((path / folder).exists() for folder in DEFAULT_FOLDERS)
        ),
        key=lambda path: path.name,
    )


def lista_files_in(course_root: Path) -> list[Path]:
    folder = Path(course_root) / LISTA_FOLDER
    if not folder.exists():
        return []
    return sorted(folder.glob(f"*{LISTA_SUFFIX}"), key=lambda path: path.name)


def sections_in(course_root: Path) -> list[str]:
    """Sections known to the course, from either its Lista or its Notas folder."""
    course_root = Path(course_root)
    sections = set()
    for folder_name, suffix in ((LISTA_FOLDER, LISTA_SUFFIX), (NOTAS_FOLDER, NOTAS_SUFFIX)):
        folder = course_root / folder_name
        if not folder.exists():
            continue
        for path in folder.glob(f"*{suffix}"):
            section = path.name[: -len(suffix)].strip()
            if section:
                sections.add(section)
    return sorted(sections)


def labs_in(course_root: Path, section: str) -> list[int]:
    """Lab numbers that already have a generated output folder."""
    section_folder = Path(course_root) / GROUPS_FOLDER / section
    if not section_folder.exists():
        return []
    labs = set()
    for path in section_folder.iterdir():
        match = _LAB_FOLDER_RE.search(path.name) if path.is_dir() else None
        if match:
            labs.add(int(match.group(1)))
    return sorted(labs)


def split_course_cycle(folder_name: str) -> tuple[str, str]:
    """"Quimica General 2026-1" -> ("Quimica General", "2026-1")."""
    course, _, cycle = str(folder_name).rpartition(" ")
    return (course, cycle) if course else (str(folder_name), "")


# --- containment --------------------------------------------------------------


def is_inside(candidate: Path, root: Path) -> bool:
    """True when ``candidate`` resolves to ``root`` or somewhere beneath it."""
    try:
        resolved = Path(candidate).expanduser().resolve()
        base = Path(root).expanduser().resolve()
    except (OSError, RuntimeError):
        return False
    return resolved == base or base in resolved.parents


def resolve_inside(candidate: Path, root: Path) -> Path:
    """Resolve ``candidate``, refusing anything that escapes ``root``."""
    if not is_inside(candidate, root):
        raise ValueError(f"La ruta esta fuera del workspace permitido: {candidate}")
    return Path(candidate).expanduser().resolve()
