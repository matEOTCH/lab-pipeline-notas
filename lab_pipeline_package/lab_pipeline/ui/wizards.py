"""Small widget helpers for the ipywidgets front-end."""

from __future__ import annotations

from pathlib import Path

from .. import colab

colab.ensure_packages("ipywidgets")
import ipywidgets as widgets  # noqa: E402


def save_upload_value(upload_value, folder: Path) -> Path:
    return colab.save_upload(upload_value, folder)


def labeled(label: str, widget: widgets.Widget) -> widgets.HBox:
    return widgets.HBox([
        widgets.HTML(f"<b>{label}</b>", layout=widgets.Layout(width="190px")),
        widget,
    ])
