from __future__ import annotations

import pytest

from lab_pipeline import grouping

STUDENTS = [{"code": f"2025000{index}", "name": f"NAME{index}, X"} for index in range(1, 10)]


def test_all_students_land_in_exactly_one_group():
    groups = grouping.shuffle_groups(STUDENTS, 4, seed=1)

    placed = [student["code"] for group in groups for student in group]
    assert len(groups) == 4
    assert sorted(placed) == sorted(student["code"] for student in STUDENTS)
    assert len(placed) == len(set(placed))


def test_group_sizes_stay_balanced_within_one():
    groups = grouping.shuffle_groups(STUDENTS, 4, seed=7)

    sizes = [len(group) for group in groups]
    assert max(sizes) - min(sizes) <= 1


def test_the_same_seed_reproduces_the_same_groups():
    first = grouping.shuffle_groups(STUDENTS, 3, seed=42)
    second = grouping.shuffle_groups(STUDENTS, 3, seed=42)

    assert [[s["code"] for s in group] for group in first] == [[s["code"] for s in group] for group in second]


def test_different_seeds_generally_differ():
    first = grouping.shuffle_groups(STUDENTS, 3, seed=1)
    second = grouping.shuffle_groups(STUDENTS, 3, seed=2)

    assert first != second


def test_forced_assignments_are_honoured():
    groups = grouping.shuffle_groups(STUDENTS, 4, {"20250001": 3, "20250002": 3}, seed=5)

    assert {student["code"] for student in groups[2]} >= {"20250001", "20250002"}


def test_forced_assignments_still_balance_the_rest():
    groups = grouping.shuffle_groups(STUDENTS, 3, {"20250001": 1, "20250002": 1, "20250003": 1}, seed=5)

    sizes = [len(group) for group in groups]
    assert sum(sizes) == len(STUDENTS)
    assert max(sizes) - min(sizes) <= 1


def test_validate_group_count_bounds():
    assert grouping.validate_group_count("4") == 4
    for bad in (0, -1, 9):
        with pytest.raises(ValueError):
            grouping.validate_group_count(bad)


def test_validate_forced_assignments_rejects_unknown_code():
    with pytest.raises(ValueError, match="no existe"):
        grouping.validate_forced_assignments(STUDENTS, 4, {"99999999": 1})


def test_validate_forced_assignments_rejects_out_of_range_group():
    with pytest.raises(ValueError, match="entre 1 y 4"):
        grouping.validate_forced_assignments(STUDENTS, 4, {"20250001": 5})


def test_validate_forced_assignments_normalizes_codes():
    assert grouping.validate_forced_assignments(STUDENTS, 4, {"20250001.0": "2"}) == {"20250001": 2}


def test_build_group_lookup_maps_every_student():
    groups = grouping.shuffle_groups(STUDENTS, 3, seed=3)

    lookup = grouping.build_group_lookup(groups)

    assert len(lookup) == len(STUDENTS)
    assert set(lookup.values()) == {1, 2, 3}
