"""Route 1: Generar estructura, as an interactive notebook flow."""

from __future__ import annotations

from pathlib import Path

from .. import colab, naming, settings
from ..common import clean_text
from ..services import structure as structure_service
from . import prompts


def explain_blackboard_download() -> None:
    print("\nGuia para descargar el CSV desde Blackboard:")
    print("  1. Entrar a Estadisticas.")
    print("  2. Ir a Actividad del curso.")
    print("  3. Hacer click en el boton de descargar.")
    print("  4. Subir aqui el CSV descargado.\n")


def ask_email_domain(project_root: Path) -> str:
    saved = structure_service.saved_email_domain(project_root)
    if saved and prompts.ask_yes_no(f"Usar el dominio guardado '{saved}'?", default=True):
        return saved

    domain = prompts.ask_required("Dominio institucional para el correo, ejemplo aloe.ulima.edu.pe")
    return domain.removeprefix("@")


def get_csv(csv_path: Path | None) -> Path:
    if csv_path:
        path = Path(csv_path)
        if not path.exists():
            raise FileNotFoundError(f"No se encontro el CSV: {path}")
        return path

    explain_blackboard_download()
    return colab.upload_file(
        "Seleccione el CSV de Blackboard.",
        folder=Path.cwd() / "uploaded_blackboard_csvs",
        accept=".csv",
    )


def ask_course_cycle(project_root: Path) -> str:
    existing = [path.name for path in naming.course_roots_in(project_root)]
    course_cycle_name, is_new = prompts.choose_existing_or_new(
        label="Curso/ciclo",
        existing_names=existing,
        manual_prompt="Nombre de curso/ciclo, ejemplo Quimica General 2026-1: ",
    )
    if not is_new:
        return course_cycle_name

    _, cycle = naming.split_course_cycle(course_cycle_name)
    if cycle:
        return course_cycle_name

    course_name = prompts.ask_required("Curso, ejemplo Quimica General")
    academic_cycle = prompts.ask_required("Ciclo academico, ejemplo 2026-1")
    return f"{course_name} {academic_cycle}"


def run_once(csv_path: Path | None = None, workspace_root: Path | None = None) -> dict[str, object]:
    colab.bootstrap("openpyxl")
    workspace = Path(workspace_root) if workspace_root else colab.workspace_root()

    project_name, _ = prompts.choose_existing_or_new(
        label="Proyecto principal",
        existing_names=[path.name for path in naming.projects_in(workspace)],
        manual_prompt="Nombre del proyecto principal, ejemplo 2026: ",
    )
    project_root = workspace / project_name
    course_cycle_name = ask_course_cycle(project_root)
    course_root = project_root / course_cycle_name

    section, is_new_section = prompts.choose_existing_or_new(
        label="Seccion",
        existing_names=naming.sections_in(course_root),
        manual_prompt="Que seccion esta creando? Ejemplo 315: ",
    )
    overwrite = False
    if not is_new_section:
        overwrite = prompts.ask_yes_no(f"La seccion {section} ya existe. Desea reemplazar Lista/Notas?")
        if not overwrite:
            print("No se reemplazo la seccion existente.")
            naming.create_base_structure(course_root)
            return {
                "project_root": project_root,
                "course_root": course_root,
                "section": section,
                "skipped": True,
            }

    email_domain = ask_email_domain(project_root)
    source_csv = get_csv(csv_path)

    result = structure_service.create_structure(
        workspace_root=workspace,
        project_name=project_name,
        course_cycle_name=course_cycle_name,
        section=section,
        email_domain=email_domain,
        csv_path=source_csv,
        overwrite=overwrite,
    )

    print("\nEstructura generada correctamente.")
    print(f"Proyecto: {result['project_root']}")
    print(f"Curso/ciclo: {result['course_root']}")
    print(f"Lista creada: {result['list_path']}")
    print(f"Notas creado: {result['notas_path']}")
    print(f"Estudiantes procesados: {len(result['students'])}")
    for warning in result["warnings"]:
        print(f"Aviso: {warning}")
    return result


def run(csv_path: Path | None = None, mydrive: Path | None = None) -> list[dict[str, object]]:
    """Create sections until the user is done. ``mydrive`` overrides the workspace."""
    results = []
    while True:
        results.append(run_once(csv_path=csv_path, workspace_root=mydrive))
        csv_path = None
        if not prompts.ask_yes_no("\nDesea crear otra seccion/lista en la estructura?"):
            print("Generar estructura finalizado.")
            return results
