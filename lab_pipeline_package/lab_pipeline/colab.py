"""Colab / Jupyter environment concerns: detection, Drive, deps, uploads.

These used to be copy-pasted into six modules. Keep the copies here.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


WORKSPACE_ENV_VAR = "LAB_PIPELINE_WORKSPACE_DIR"
COLAB_MYDRIVE = Path("/content/drive/MyDrive")

_installed: set[str] = set()
_drive_mounted = False


def running_in_colab() -> bool:
    try:
        import google.colab  # noqa: F401
    except Exception:
        return False
    return True


def ensure_packages(*names: str) -> None:
    """pip-install ``names`` once per process. No-op for anything importable."""
    missing = [name for name in names if name not in _installed and not _importable(name)]
    if not missing:
        _installed.update(names)
        return
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", *missing])
    _installed.update(names)


def _importable(name: str) -> bool:
    import importlib.util

    module_name = name.replace("-", "_")
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ValueError):
        return False


def mount_drive() -> None:
    """Mount Google Drive when running in Colab. Idempotent, no-op elsewhere."""
    global _drive_mounted
    if _drive_mounted or not running_in_colab():
        return
    from google.colab import drive

    drive.mount("/content/drive")
    _drive_mounted = True


def bootstrap(*packages: str) -> None:
    """The standard workflow preamble: install deps, then mount Drive."""
    if packages:
        ensure_packages(*packages)
    mount_drive()


def workspace_root() -> Path:
    """Where projects live: the env override, else Drive in Colab, else cwd."""
    override = os.environ.get(WORKSPACE_ENV_VAR)
    if override:
        return Path(override)
    if running_in_colab():
        return COLAB_MYDRIVE
    return Path.cwd()


# --- uploads ------------------------------------------------------------------


def save_upload(upload_value, folder: Path) -> Path:
    """Persist an ``ipywidgets.FileUpload`` value to ``folder``.

    Handles both widget payload shapes: the ipywidgets 7 dict keyed by filename
    and the ipywidgets 8 tuple of items.
    """
    if not upload_value:
        raise ValueError("No se subio ningun archivo.")

    if isinstance(upload_value, dict):
        name, item = next(iter(upload_value.items()))
        content = item["content"]
    else:
        item = upload_value[0]
        name = item["name"]
        content = item["content"]

    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    out_path = folder / Path(name).name
    out_path.write_bytes(bytes(content))
    return out_path


def upload_file(prompt: str, folder: Path, accept: str = "") -> Path:
    """Ask the user for a file: Colab picker, else a widget, else a typed path."""
    print(prompt)

    if running_in_colab():
        from google.colab import files

        uploaded = files.upload()
        if not uploaded:
            raise ValueError("No se subio ningun archivo.")
        return Path(next(iter(uploaded)))

    try:
        import ipywidgets as widgets
        from IPython.display import display
    except ModuleNotFoundError:
        path = Path(input("Ruta local del archivo: ").strip()).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"No se encontro el archivo: {path}")
        return path

    uploader = widgets.FileUpload(accept=accept, multiple=False, description="Subir archivo")
    display(uploader)
    input("Cuando el archivo ya aparezca cargado arriba, presione Enter para continuar: ")
    return save_upload(uploader.value, folder)
