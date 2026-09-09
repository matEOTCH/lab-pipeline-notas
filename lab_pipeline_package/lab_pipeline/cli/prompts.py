"""Console prompt helpers shared by the three notebook workflows."""

from __future__ import annotations

from pathlib import Path

from ..common import clean_text


YES_ANSWERS = {"s", "si", "sí", "y", "yes"}


def ask_yes_no(question: str, default: bool = False) -> bool:
    suffix = "[S/n]" if default else "[s/N]"
    answer = input(f"{question} {suffix}: ").strip().lower()
    if not answer:
        return default
    return answer in YES_ANSWERS


def ask_required(question: str) -> str:
    value = clean_text(input(f"{question}: "))
    if not value:
        raise ValueError(f"{question} no puede estar vacio.")
    return value


def ask_int(question: str, minimum: int = 1, maximum: int | None = None, default: int | None = None) -> int:
    hint = f" [default {default}]" if default is not None else ""
    raw = input(f"{question}{hint}: ").strip()
    if not raw and default is not None:
        return default
    if not raw.isdigit():
        raise ValueError("Debe ingresar un numero entero.")
    value = int(raw)
    if value < minimum or (maximum is not None and value > maximum):
        limit = f"entre {minimum} y {maximum}" if maximum is not None else f"mayor o igual a {minimum}"
        raise ValueError(f"El valor debe estar {limit}.")
    return value


def choose(label: str, items: list, describe=str):
    """Print a numbered menu and return the chosen item."""
    if not items:
        raise FileNotFoundError(f"No encontre {label.lower()} disponibles.")
    print(f"\n{label} disponibles:")
    for index, item in enumerate(items, start=1):
        print(f"  ({index}) {describe(item)}")
    choice = input(f"Seleccione {label.lower()} por numero: ").strip()
    if not choice.isdigit() or not (1 <= int(choice) <= len(items)):
        raise ValueError("La opcion seleccionada esta fuera de rango.")
    return items[int(choice) - 1]


def choose_path(label: str, paths: list[Path]) -> Path:
    return choose(label, paths, describe=lambda path: path.name)


def choose_existing_or_new(label: str, existing_names: list[str], manual_prompt: str) -> tuple[str, bool]:
    """Pick from ``existing_names`` or type a new one. Returns ``(value, is_new)``."""
    existing_names = sorted(name for name in existing_names if clean_text(name))
    print()
    if existing_names:
        print(f"{label} existentes:")
        for index, name in enumerate(existing_names, start=1):
            print(f"  ({index}) {name}")
        new_option = len(existing_names) + 1
        print(f"  ({new_option}) Crear nuevo")

        choice = input(f"Seleccione {label.lower()} por numero: ").strip()
        if not choice.isdigit():
            raise ValueError("Debe seleccionar una opcion numerica.")
        choice_number = int(choice)
        if 1 <= choice_number <= len(existing_names):
            return existing_names[choice_number - 1], False
        if choice_number != new_option:
            raise ValueError("La opcion seleccionada esta fuera de rango.")
    else:
        print(f"No encontre {label.lower()} existentes. Crearemos uno nuevo.")

    value = clean_text(input(manual_prompt))
    if not value:
        raise ValueError(f"{label} no puede estar vacio.")
    return value, True


def choose_student(students: list[dict], excluded_codes: set[str], purpose: str) -> dict | None:
    """Narrow by surname initial, then pick. ``None`` means "nothing selected"."""
    from ..rosters import search_by_lastname_initial

    initial = input("Inicial del apellido del alumno: ").strip().upper()[:1]
    if not initial:
        print("Inicial vacia. Intente de nuevo.")
        return None

    candidates = search_by_lastname_initial(students, initial, excluded_codes)
    if not candidates:
        print(f"No encontre alumnos disponibles con inicial {initial}.")
        return None

    print(f"\nAlumnos con apellido inicial {initial} ({purpose}):")
    for index, student in enumerate(candidates, start=1):
        print(f"  ({index}) {student['code']} | {student['name']}")

    choice = input("Seleccione alumno por numero: ").strip()
    if not choice.isdigit() or not (1 <= int(choice) <= len(candidates)):
        print("Seleccion invalida. Intente de nuevo.")
        return None
    return candidates[int(choice) - 1]


def collect_students(students: list[dict], question: str, purpose: str) -> list[dict]:
    """Repeatedly pick students until the user says no. Order preserved."""
    chosen: dict[str, dict] = {}
    while ask_yes_no(question):
        student = choose_student(students, set(chosen), purpose)
        if student:
            chosen[student["code"]] = student
            print(f"Seleccionado: {student['code']} | {student['name']}")
    return list(chosen.values())
