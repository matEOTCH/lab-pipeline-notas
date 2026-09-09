"""Route 3: Subiendo notas (TeamMates, notas adicionales, ausentes)."""

from __future__ import annotations

from pathlib import Path

from .. import blackboard_grades, colab, gradebook, naming
from ..services import grades as grades_service
from . import prompts


METHOD_LABELS = {
    "1": "Archivo automatico de Blackboard (.csv o .xls)",
    "2": "Ingreso manual por alumno",
    "3": "Ingreso manual por grupo",
}


def ask_method() -> str:
    print("Metodo de carga para esta columna:")
    for key, label in METHOD_LABELS.items():
        print(f"  ({key}) {label}")
    method = input("Seleccione metodo: ").strip()
    if method not in METHOD_LABELS:
        raise ValueError("Metodo invalido.")
    return method


def ask_grade_column_templates() -> list[dict[str, str]]:
    if not prompts.ask_yes_no("Desea crear columnas para subir notas adicionales?"):
        return []

    count = prompts.ask_int("Cuantas columnas de nota desea crear?", minimum=1)
    templates = []
    for index in range(1, count + 1):
        default_name = f"NotaExtra{index}_Lab"
        name = input(f"Nombre base de la columna {index} [{default_name}]: ").strip() or default_name
        base_name = gradebook.normalize_custom_base_name(name)
        method = ask_method()
        templates.append({"base_name": base_name, "method": method})
        print(f"Logica guardada: {base_name} + numero de laboratorio | metodo {method}")
    return templates


def get_or_create_templates(course_root: Path, section: str) -> list[dict[str, str]]:
    """Reuse the section's remembered templates, or ask for them once."""
    saved = grades_service.grade_column_templates(course_root, section)
    if saved:
        print(f"Logica de notas guardada para seccion {section}:")
        for template in saved:
            print(f"  - {template['base_name']} | metodo {template['method']}")
        return saved

    templates = ask_grade_column_templates()
    grades_service.configure_grade_columns(course_root, section, 1, templates)
    return templates


def resolve_score_column(path: Path) -> str | None:
    """When a Blackboard file has several grade columns, ask which one to use.

    Returns ``None`` when the file has zero or one grade column, or when the
    student-code column is missing: in those cases ``parse_grades`` already
    gives a clear error or resolves it on its own.
    """
    try:
        headers, _ = blackboard_grades.read_headers_and_rows(path)
        code_column = blackboard_grades.find_code_column(headers)
        if not code_column:
            return None
        candidates = blackboard_grades.grade_column_candidates(headers, code_column)
    except ValueError:
        return None
    if len(candidates) <= 1:
        return None

    print("\nEl archivo tiene varias columnas de nota.")
    ranked = blackboard_grades.rank_grade_candidates(candidates)
    return prompts.choose("Columna de nota", ranked)


def collect_column_payloads(
    templates: list[dict[str, str]],
    columns: list[str],
    students: list[dict],
    group_lookup: dict[str, int],
) -> tuple[dict, dict, dict]:
    """Ask for each custom column's grades, keyed by materialized column name."""
    uploaded_files: dict[str, Path] = {}
    manual_student: dict[str, dict] = {}
    manual_group: dict[str, dict] = {}

    for template, column_name in zip(templates, columns):
        method = template["method"]
        print(f"\nCarga de notas para {column_name} ({METHOD_LABELS[method]}):")

        if method == "1":
            path = colab.upload_file(
                "Suba el archivo de Blackboard para esta nota.",
                folder=Path.cwd() / "uploaded_grade_files",
                accept=".csv,.xls",
            )
            score_column = resolve_score_column(path)
            uploaded_files[column_name] = (
                {"path": path, "score_column": score_column} if score_column else path
            )
        elif method == "2":
            manual_student[column_name] = {
                student["code"]: raw
                for student in students
                if (raw := input(f"Nota para {student['code']} | {student['name']} [Enter para vacio]: ").strip())
            }
        else:
            if not group_lookup:
                raise ValueError(
                    f"No encontre {gradebook.group_column(1)}; primero ejecute la opcion 2."
                )
            manual_group[column_name] = {
                group_number: raw
                for group_number in sorted(set(group_lookup.values()))
                if (raw := input(f"Nota para Grupo {group_number} [Enter para vacio]: ").strip())
            }

    return uploaded_files, manual_student, manual_group


def choose_created_lab(course_root: Path, section: str) -> int:
    labs = naming.labs_in(course_root, section)
    if not labs:
        raise FileNotFoundError(
            f"No encontre laboratorios creados para la seccion {section}. "
            "Primero ejecute la opcion 2: Crear Grupos de Laboratorio."
        )
    return prompts.choose("Laboratorio", labs, describe=lambda lab: f"Laboratorio {lab}")


def run_once(
    csv_path: Path | None = None,
    project_root: Path | None = None,
    course_root: Path | None = None,
    workspace_root: Path | None = None,
) -> dict[str, object]:
    colab.bootstrap("openpyxl")
    workspace = Path(workspace_root) if workspace_root else colab.workspace_root()

    project_root = project_root or prompts.choose_path("Proyecto", naming.projects_in(workspace))
    course_root = course_root or prompts.choose_path("Curso/ciclo", naming.course_roots_in(project_root))
    section = prompts.choose("Seccion", naming.sections_in(course_root))

    notas_path = naming.notas_path(course_root, section)
    if not notas_path.exists():
        raise FileNotFoundError(f"No encontre el archivo de Notas: {notas_path}")

    lab_number = choose_created_lab(course_root, section)
    templates = get_or_create_templates(course_root, section)
    columns = gradebook.materialize_custom_columns(templates, lab_number)

    teammates_path = None
    if prompts.ask_yes_no("Desea subir/actualizar informacion de Teammates?", default=True):
        teammates_path = Path(csv_path) if csv_path else colab.upload_file(
            "Suba el CSV de Teammates.",
            folder=Path.cwd() / "uploaded_teammates_csvs",
            accept=".csv",
        )

    book = gradebook.Gradebook(notas_path, read_only=True)
    students = book.students
    group_lookup = book.group_lookup(lab_number)

    uploaded_files, manual_student, manual_group = collect_column_payloads(
        templates, columns, students, group_lookup
    )
    absent_students = prompts.collect_students(
        students, "Algun estudiante falto a la prueba?", "ausente"
    )

    result = grades_service.apply_grade_updates(
        notas_path=notas_path,
        lab_number=lab_number,
        custom_grade_templates=templates,
        uploaded_files=uploaded_files,
        manual_student_grades=manual_student,
        manual_group_grades=manual_group,
        teammates_csv_path=teammates_path,
        absent_codes=[student["code"] for student in absent_students],
    )
    result["section"] = section
    result["project_root"] = project_root
    result["course_root"] = course_root

    tm_result = result["tm_result"] or {}
    print("\nCarga de notas completada.")
    print(f"Seccion: {section}")
    print(f"Notas workbook: {notas_path}")
    print(f"Laboratorio: {lab_number}")
    print(f"TM scores updated: {tm_result.get('updated_tm', 0)}")
    print(f"Response rows updated: {tm_result.get('updated_resp', 0)}")
    for column_name, updated in result["custom_updates"].items():
        print(f"{column_name}: {updated} notas actualizadas")
    print(f"Ausentes marcados: {result['absences']['absences_updated']}")
    if result["created_columns"]:
        print(f"New columns added: {', '.join(result['created_columns'])}")
    if tm_result.get("missing_scores"):
        print(f"Missing TM score matches: {len(tm_result['missing_scores'])}")
    return result


def run(config=None, csv_path: Path | None = None) -> list[dict[str, object]]:
    """``config`` is accepted for notebook compatibility and otherwise unused."""
    results = []
    project_root = None
    course_root = None
    while True:
        result = run_once(csv_path=csv_path, project_root=project_root, course_root=course_root)
        results.append(result)
        csv_path = None
        if not prompts.ask_yes_no("\nDesea ingresar otras notas para otra seccion o laboratorio?"):
            print("Subiendo notas finalizado.")
            return results
        project_root = result["project_root"]
        course_root = result["course_root"]
