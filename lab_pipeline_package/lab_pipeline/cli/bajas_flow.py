"""Route 2 helper: registering student withdrawals before forming groups."""

from __future__ import annotations

from pathlib import Path

from ..services import bajas as bajas_service
from . import prompts


def handle_one_withdrawal(course_root: Path, section: str, students: list[dict]) -> dict | None:
    student = prompts.choose_student(students, set(), "baja")
    if not student:
        return None

    preview = bajas_service.preview_withdrawal(course_root, section, student["code"])
    print(f"\nSe dara de baja a: {preview['name']} ({preview['code']})")
    if preview["recorded_labs"]:
        labs = ", ".join(str(number) for number in preview["recorded_labs"])
        print(f"Ya tiene notas registradas en Laboratorio(s) {labs}; se conservaran en la hoja de bajas.")
    else:
        print("Todavia no tiene notas registradas.")

    if not prompts.ask_yes_no(
        "Confirma mover a este alumno a la hoja de bajas? Esta accion no se puede deshacer facilmente"
    ):
        print("Baja cancelada.")
        return None

    result = bajas_service.withdraw_student(course_root, section, student["code"])
    print(f"Movido a Bajas: {result['name']} ({result['code']})")
    return result


def ask_withdrawals(course_root: Path, section: str, students: list[dict]) -> list[dict]:
    """Loop shaped like groups_flow.ask_forced_assignments: handle withdrawals
    one at a time until the professor says there are no more."""
    results = []
    remaining = list(students)
    while prompts.ask_yes_no("Hay algun alumno que se haya dado de baja del curso?"):
        result = handle_one_withdrawal(course_root, section, remaining)
        if result:
            results.append(result)
            remaining = [student for student in remaining if student["code"] != result["code"]]
    return results
