"""Reusable widget pieces: the location picker and the student selector."""

from __future__ import annotations

from pathlib import Path

from .. import colab, naming, rosters

colab.ensure_packages("ipywidgets")
import ipywidgets as widgets  # noqa: E402

from .wizards import labeled  # noqa: E402


UPLOAD_DIRS = {
    "roster": "uploaded_blackboard_csvs",
    "grades": "uploaded_grade_files",
    "teammates": "uploaded_teammates_csvs",
}

GRADE_METHODS = [
    ("Ninguno", ""),
    ("Blackboard CSV/XLS", "1"),
    ("Manual por alumno", "2"),
    ("Manual por grupo", "3"),
]


def upload_dir(kind: str) -> Path:
    return Path.cwd() / UPLOAD_DIRS[kind]


def option_pairs(paths: list[Path]) -> list[tuple[str, str]]:
    return [(path.name, str(path)) for path in paths]


def path_from_dropdown(dropdown: widgets.Dropdown) -> Path:
    if not dropdown.value:
        raise ValueError("Seleccione una opcion valida.")
    return Path(dropdown.value)


def parse_optional_int(value: str) -> int | None:
    value = str(value or "").strip()
    return int(value) if value else None


def parse_key_value_lines(text: str) -> dict[str, str]:
    """"20250052=18" per line -> ``{"20250052": "18"}``."""
    values = {}
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip():
            values[key.strip()] = value.strip()
    return values


class Picker:
    """Linked project / course / section (/ lab) dropdowns."""

    def __init__(self, workspace_root: Path, include_labs: bool = False):
        self.workspace_root = workspace_root
        self.include_labs = include_labs
        self.project = widgets.Dropdown(options=option_pairs(naming.projects_in(workspace_root)))
        self.course = widgets.Dropdown(options=[])
        self.section = widgets.Dropdown(options=[])
        self.lab = widgets.Dropdown(options=[])

        self.project.observe(self._refresh_courses, names="value")
        self.course.observe(self._refresh_sections, names="value")
        self.section.observe(self._refresh_labs, names="value")
        self._refresh_courses()

    def _refresh_courses(self, *_):
        self.course.options = (
            option_pairs(naming.course_roots_in(Path(self.project.value))) if self.project.value else []
        )
        self._refresh_sections()

    def _refresh_sections(self, *_):
        sections = naming.sections_in(Path(self.course.value)) if self.course.value else []
        self.section.options = [(section, section) for section in sections]
        self._refresh_labs()

    def _refresh_labs(self, *_):
        if not (self.include_labs and self.course.value and self.section.value):
            self.lab.options = []
            return
        labs = naming.labs_in(Path(self.course.value), self.section.value)
        self.lab.options = [(f"Laboratorio {lab}", lab) for lab in labs]

    @property
    def course_root(self) -> Path:
        return path_from_dropdown(self.course)

    @property
    def lab_number(self) -> int:
        if not self.lab.value:
            raise ValueError("Seleccione un laboratorio. Primero debe generar grupos.")
        return int(self.lab.value)

    def students(self) -> list[dict]:
        _, students = rosters.parse_student_list(naming.lista_path(self.course_root, self.section.value))
        return students

    def notas_path(self) -> Path:
        return naming.notas_path(self.course_root, self.section.value)

    def fields(self) -> list:
        fields = [
            labeled("Proyecto", self.project),
            labeled("Curso/ciclo", self.course),
            labeled("Seccion", self.section),
        ]
        if self.include_labs:
            fields.append(labeled("Laboratorio", self.lab))
        return fields


class StudentSelector:
    """Search by surname initial, then accumulate a set of chosen students."""

    def __init__(self, picker: Picker, on_change=None):
        self.picker = picker
        self.on_change = on_change
        self.chosen: dict[str, str] = {}
        self.initial = widgets.Text(placeholder="A", layout=widgets.Layout(width="80px"))
        self.candidates = widgets.Dropdown(options=[])
        self.initial.observe(self.refresh, names="value")
        picker.section.observe(self.refresh, names="value")

    def refresh(self, *_):
        try:
            found = rosters.search_by_lastname_initial(
                self.picker.students(), self.initial.value, set(self.chosen)
            )
            self.candidates.options = [(f"{s['code']} | {s['name']}", s["code"]) for s in found]
        except Exception:
            self.candidates.options = []

    def add(self) -> str | None:
        code = self.candidates.value
        if not code:
            return None
        labels = {value: label for label, value in self.candidates.options}
        self.chosen[code] = labels.get(code, code)
        self.refresh()
        if self.on_change:
            self.on_change()
        return code

    @property
    def codes(self) -> list[str]:
        return list(self.chosen)
