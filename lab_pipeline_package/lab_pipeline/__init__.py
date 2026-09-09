"""Reusable lab workflow package for the Quimica General notebooks.

Layout:

- ``naming``, ``settings``, ``colab`` - filesystem conventions, small JSON
  settings files, and the Colab/Jupyter environment.
- ``common``, ``gradebook`` - worksheet primitives and the Notas workbook.
- ``rosters``, ``grouping``, ``outputs``, ``teammates_csv``,
  ``blackboard_grades``, ``comments_sheet`` - the domain.
- ``services`` - orchestration, shared by every front-end.
- ``web_app``, ``ui``, ``cli`` - the three front-ends.
"""

__all__ = ["services"]
