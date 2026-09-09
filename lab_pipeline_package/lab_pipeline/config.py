"""Notebook-facing configuration object.

Only ``bb_self_enroll`` still affects behaviour: the folder layout this class
used to describe (Templates/, Lists/, Output/, the APR docx) belongs to an
earlier design that no current workflow reads. Paths now come from
:mod:`lab_pipeline.naming`, which derives them from the course folder.

Deployed notebooks construct this with a fixed set of keyword arguments, so it
accepts and ignores anything it no longer uses rather than raising.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LabConfig:
    lab_number: int = 1
    lab_name: str = ""
    num_groups: int = 8
    bb_self_enroll: str = "N"
    #: Retired keyword arguments, kept so old notebook cells still run.
    legacy: dict = field(default_factory=dict, repr=False)

    def __init__(self, lab_number: int = 1, lab_name: str = "", num_groups: int = 8, bb_self_enroll: str = "N", **legacy):
        self.lab_number = int(lab_number)
        self.lab_name = lab_name
        self.num_groups = int(num_groups)
        self.bb_self_enroll = bb_self_enroll
        self.legacy = legacy
