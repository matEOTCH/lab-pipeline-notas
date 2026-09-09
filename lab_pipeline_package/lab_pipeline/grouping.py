"""Dividing a section's students into lab groups."""

from __future__ import annotations

import random

from .common import normalize_student_code


MAX_GROUPS = 8


def validate_group_count(group_count: int, maximum: int = MAX_GROUPS) -> int:
    group_count = int(group_count)
    if group_count < 1 or group_count > maximum:
        raise ValueError(f"El numero de grupos debe estar entre 1 y {maximum}.")
    return group_count


def validate_forced_assignments(
    students: list[dict],
    group_count: int,
    forced_assignments: dict[str, int] | None = None,
) -> dict[str, int]:
    """Normalize ``{code: group}``, rejecting unknown codes and bad groups."""
    student_codes = {normalize_student_code(student.get("code")) for student in students}
    validated = {}
    for raw_code, raw_group in (forced_assignments or {}).items():
        code = normalize_student_code(raw_code)
        if code not in student_codes:
            raise ValueError(f"El codigo {raw_code} no existe en la lista de estudiantes.")
        group_number = int(raw_group)
        if group_number < 1 or group_number > group_count:
            raise ValueError(f"El grupo fijo para {code} debe estar entre 1 y {group_count}.")
        validated[code] = group_number
    return validated


def shuffle_groups(
    students: list[dict],
    group_count: int,
    forced_assignments: dict[str, int] | None = None,
    seed: int | None = None,
) -> list[list[dict]]:
    """Shuffle students into ``group_count`` groups, honouring fixed placements.

    Forced students are seated first; everyone else is shuffled and then dealt
    into whichever group is currently smallest, so sizes stay balanced even when
    the fixed placements are lopsided. A ``seed`` makes the result reproducible.
    """
    group_count = int(group_count)
    forced_assignments = forced_assignments or {}
    rng = random.Random(seed)
    groups: list[list[dict]] = [[] for _ in range(group_count)]
    by_code = {normalize_student_code(student.get("code")): student for student in students}

    for code, group_number in forced_assignments.items():
        student = by_code.get(normalize_student_code(code))
        if student:
            groups[int(group_number) - 1].append(student)

    remaining = [
        student
        for student in students
        if normalize_student_code(student.get("code")) not in forced_assignments
    ]
    rng.shuffle(remaining)

    for student in remaining:
        target = min(range(group_count), key=lambda index: (len(groups[index]), index))
        groups[target].append(student)

    return groups


def build_group_lookup(groups: list[list[dict]]) -> dict[str, int]:
    """``{student code: group number}`` for the shuffled groups."""
    return {
        normalize_student_code(student.get("code")): group_number
        for group_number, group in enumerate(groups, start=1)
        for student in group
        if normalize_student_code(student.get("code"))
    }
