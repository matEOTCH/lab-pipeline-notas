"""ipywidgets front-end: the shell that hosts the screens."""

from __future__ import annotations

import os
from pathlib import Path

from .. import colab

colab.ensure_packages("ipywidgets")
import ipywidgets as widgets  # noqa: E402
from IPython.display import clear_output, display  # noqa: E402

from . import screens  # noqa: E402
from .components import render_error_box, render_header, render_output_links  # noqa: E402
from .state import AppState  # noqa: E402
from .styles import inject_styles  # noqa: E402


ROUTES = [
    ("Centro de control", "dashboard"),
    ("Crear estructura", "structure"),
    ("Crear grupos", "groups"),
    ("Evaluacion", "evaluation"),
    ("Ausentes", "absences"),
    ("Outputs", "outputs"),
]

SCREENS = {
    "dashboard": screens.dashboard,
    "structure": screens.structure,
    "groups": screens.groups,
    "evaluation": screens.evaluation,
    "absences": screens.absences,
    "outputs": screens.outputs,
}


class LabManagerApp:
    def __init__(self, workspace_root: Path | None = None):
        root = Path(workspace_root) if workspace_root else colab.workspace_root()
        os.environ[colab.WORKSPACE_ENV_VAR] = str(root)
        self.state = AppState(workspace_root=root)
        self.nav = widgets.ToggleButtons(options=ROUTES, value="dashboard", button_style="")
        self.body = widgets.Output()
        self.nav.observe(lambda *_: self.render(), names="value")

    def launch(self) -> None:
        inject_styles()
        display(widgets.VBox([
            widgets.HTML('<div class="lab-app-shell">'),
            render_header(
                "Lab Manager - Quimica General",
                "Centro de control visual para estructura, grupos, notas y ausencias.",
            ),
            self.nav,
            self.body,
            widgets.HTML("</div>"),
        ]))
        self.render()

    def render(self) -> None:
        with self.body:
            clear_output()
            SCREENS[self.nav.value](self)

    def record_outputs(self, outputs: dict[str, Path]) -> None:
        self.state.last_outputs = outputs
        display(render_output_links(outputs))

    @staticmethod
    def guarded(out: widgets.Output, action):
        """Wrap a click handler so errors land in the panel instead of raising."""
        def handler(_):
            with out:
                clear_output()
                try:
                    action()
                except Exception as exc:
                    display(render_error_box(exc))
        return handler


def launch_lab_manager_app(workspace_root: Path | None = None) -> LabManagerApp:
    colab.bootstrap("openpyxl", "ipywidgets", "reportlab")
    app = LabManagerApp(workspace_root=workspace_root)
    app.launch()
    return app
