"""Route 2: Crear Grupos de Laboratorio, as an interactive notebook flow."""

from __future__ import annotations

from pathlib import Path

from .. import colab, groups_csv, grouping, naming, rosters
from ..services import groups as groups_service
from . import bajas_flow, prompts


def ask_section_people(course_root: Path, section: str) -> tuple[str, str]:
    """Reuse the remembered professor/jefe, or ask once and remember them."""
    saved = groups_service.section_people(course_root, section)

    professor = saved["professor"]
    if professor:
        print(f"Profesor guardado para seccion {section}: {professor}")
    else:
        professor = prompts.ask_required(f"Profesor para seccion {section}")

    jefe = saved["jefe"]
    if jefe:
        print(f"Jefe de Practica guardado para seccion {section}: {jefe}")
    else:
        jefe = prompts.ask_required(f"Jefe de Practica para seccion {section}")

    return professor, jefe


def ask_forced_assignments(students: list[dict], group_count: int) -> dict[str, int]:
    forced: dict[str, int] = {}
    while prompts.ask_yes_no("Hay algun alumno que deba ir en un grupo especifico?"):
        student = prompts.choose_student(students, set(forced), "grupo fijo")
        if not student:
            continue
        try:
            group_number = prompts.ask_int(
                f"Grupo especifico para {student['name']} (1-{group_count})", minimum=1, maximum=group_count
            )
        except ValueError as exc:
            print(f"{exc} Intente de nuevo.")
            continue
        forced[student["code"]] = group_number
        print(f"Asignado: {student['name']} -> Grupo {group_number}")

    if forced:
        print("\nAsignaciones fijas:")
        by_code = {student["code"]: student for student in students}
        for code, group_number in forced.items():
            print(f"  Grupo {group_number}: {code} | {by_code[code]['name']}")
    return forced


def _filter_to_current_students(mapping: dict[str, int], students: list[dict]) -> dict[str, int]:
    """Drop any code no longer on the roster (e.g. a recent baja), with a warning."""
    current_codes = {student["code"] for student in students}
    filtered = {code: group for code, group in mapping.items() if code in current_codes}
    dropped = len(mapping) - len(filtered)
    if dropped:
        print(f"Aviso: se ignoraron {dropped} codigo(s) que ya no estan en la lista de la seccion.")
    return filtered


def ask_group_mode(course_root: Path, section: str) -> str:
    has_saved = bool(groups_service.fixed_groups(course_root, section))
    print("\nComo se van a asignar los grupos para este laboratorio?")
    print("  (1) Aleatorio")
    print("  (2) Importar CSV de grupos ya creados (fijos)")
    if has_saved:
        print("  (3) Reusar los grupos fijos ya guardados para esta seccion")
    options = {"1", "2", "3"} if has_saved else {"1", "2"}
    mode = input("Seleccione modo: ").strip()
    if mode not in options:
        raise ValueError("Modo invalido.")
    return mode


def ask_group_assignment(course_root: Path, section: str, students: list[dict]) -> tuple[int, dict[str, int]]:
    """Returns ``(group_count, forced_assignments)`` for whichever mode was chosen."""
    mode = ask_group_mode(course_root, section)

    if mode == "2":
        csv_path = colab.upload_file(
            "Suba el CSV de grupos (exportado de Blackboard, o el members_csv de esta herramienta).",
            folder=Path.cwd() / "uploaded_group_csvs",
            accept=".csv,.xls",
        )
        forced_assignments = _filter_to_current_students(groups_csv.parse_groups_csv(csv_path), students)
        group_count = prompts.ask_int(
            "Cuantos grupos se van a crear?",
            minimum=1,
            maximum=grouping.MAX_GROUPS,
            default=max(forced_assignments.values()) if forced_assignments else grouping.MAX_GROUPS,
        )
        groups_service.remember_fixed_groups(course_root, section, forced_assignments)
        return group_count, forced_assignments

    if mode == "3":
        forced_assignments = _filter_to_current_students(groups_service.fixed_groups(course_root, section), students)
        group_count = prompts.ask_int(
            "Cuantos grupos se van a crear?",
            minimum=1,
            maximum=grouping.MAX_GROUPS,
            default=max(forced_assignments.values()) if forced_assignments else grouping.MAX_GROUPS,
        )
        return group_count, forced_assignments

    group_count = prompts.ask_int(
        "Cuantos grupos se van a crear?", minimum=1, maximum=grouping.MAX_GROUPS, default=grouping.MAX_GROUPS
    )
    forced_assignments = ask_forced_assignments(students, group_count)
    return group_count, forced_assignments


def run_once(
    seed: int | None = None,
    project_root: Path | None = None,
    course_root: Path | None = None,
    workspace_root: Path | None = None,
    self_enroll: str = "N",
) -> dict[str, object]:
    colab.bootstrap("openpyxl", "reportlab")
    workspace = Path(workspace_root) if workspace_root else colab.workspace_root()

    project_root = project_root or prompts.choose_path("Proyecto", naming.projects_in(workspace))
    course_root = course_root or prompts.choose_path("Curso/ciclo", naming.course_roots_in(project_root))

    section = prompts.choose(
        "Seccion",
        naming.sections_in(course_root),
    )
    _, students = rosters.parse_student_list(naming.lista_path(course_root, section))
    print(f"\nSeccion seleccionada: {section}")
    print(f"Estudiantes cargados: {len(students)}")

    bajas_flow.ask_withdrawals(course_root, section, students)
    _, students = rosters.parse_student_list(naming.lista_path(course_root, section))
    print(f"Estudiantes activos tras bajas: {len(students)}")

    professor, jefe = ask_section_people(course_root, section)
    lab_number = prompts.ask_int("Numero de laboratorio, ejemplo 1, 2, 3", minimum=1)
    group_count, forced_assignments = ask_group_assignment(course_root, section, students)

    result = groups_service.create_lab_groups(
        course_root=course_root,
        section=section,
        professor=professor,
        jefe=jefe,
        lab_number=lab_number,
        group_count=group_count,
        forced_assignments=forced_assignments,
        seed=seed,
        download=True,
        self_enroll=self_enroll,
    )
    result["project_root"] = project_root

    print("\nLab group workflow complete.")
    print(f"Section: {section}")
    print(f"Professor: {professor}")
    print(f"Jefe: {jefe}")
    print(f"Laboratorio: {lab_number}")
    print(f"Grupos: {group_count} ({result['group_sizes']})")
    print(f"Notas: {result['notas_path']}")
    print(f"PDF grupos: {result['pdf_path']}")
    print(f"Blackboard Groups CSV: {result['groups_csv']}")
    print(f"Blackboard Members CSV: {result['members_csv']}")
    print(f"ZIP descargable: {result['zip_path']}")
    print(f"Students updated in Notas: {result['notas_result']['updated_count']}")
    for warning in result["warnings"]:
        print(f"Aviso: {warning}")
    return result


def run(config=None, seed: int | None = None) -> list[dict[str, object]]:
    """``config`` is accepted for notebook compatibility; only self-enroll is read."""
    self_enroll = getattr(config, "bb_self_enroll", "N") if config else "N"
    result = run_once(seed=seed, self_enroll=self_enroll)
    print("Crear Grupos de Laboratorio finalizado.")
    print("Para crear otro grupo/laboratorio, vuelva a correr la opcion 2 desde el orquestador.")
    return [result]
