from __future__ import annotations

from pathlib import Path

try:
    import pandas as pd
except Exception:  # pragma: no cover - pandas may not be installed locally.
    pd = None

from .. import colab

colab.ensure_packages("ipywidgets")
import ipywidgets as widgets  # noqa: E402
from IPython.display import HTML, display  # noqa: E402


def render_header(title: str, subtitle: str = "") -> widgets.HTML:
    subtitle_html = f"<p>{subtitle}</p>" if subtitle else ""
    return widgets.HTML(f'<div class="lab-header"><h1>{title}</h1>{subtitle_html}</div>')


def render_card(title: str, description: str, icon: str | None = None, status: str | None = None) -> widgets.HTML:
    status_html = f'<div class="lab-muted">Estado: {status}</div>' if status else ""
    icon_text = f"{icon} " if icon else ""
    return widgets.HTML(f'<div class="lab-card"><h3>{icon_text}{title}</h3><div>{description}</div>{status_html}</div>')


def render_status(message: str, status: str = "info") -> widgets.HTML:
    return widgets.HTML(f'<div class="lab-status {status}">{message}</div>')


def render_checklist(items: list[tuple[str, bool] | str]) -> widgets.HTML:
    rows = []
    for item in items:
        if isinstance(item, tuple):
            label, done = item
        else:
            label, done = item, False
        marker = "✓" if done else "•"
        rows.append(f"<li>{marker} {label}</li>")
    return widgets.HTML(f'<div class="lab-card"><h3>Checklist</h3><ul>{"".join(rows)}</ul></div>')


def display_dataframe_preview(rows: list[dict], limit: int = 10) -> None:
    if not rows:
        display(render_status("No hay datos para previsualizar.", "warning"))
        return
    if pd is None:
        display(HTML("<pre>" + "\n".join(str(row) for row in rows[:limit]) + "</pre>"))
        return
    display(pd.DataFrame(rows).head(limit))


def render_output_links(paths: dict[str, Path] | list[Path]) -> widgets.HTML:
    if isinstance(paths, dict):
        items = paths.items()
    else:
        items = [(Path(path).name, path) for path in paths]
    links = []
    for label, path in items:
        path = Path(path)
        links.append(f'<span class="lab-output-link"><b>{label}:</b> {path}</span>')
    return widgets.HTML(f'<div class="lab-card"><h3>Outputs generados</h3>{"".join(links)}</div>')


def render_error_box(error: Exception | str) -> widgets.HTML:
    return render_status(str(error), "error")


def render_success_box(message: str) -> widgets.HTML:
    return render_status(message, "success")
