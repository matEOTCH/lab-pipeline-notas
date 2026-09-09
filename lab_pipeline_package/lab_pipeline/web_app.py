"""Flask front-end: HTTP routes over :mod:`lab_pipeline.services`.

Every filesystem path that arrives from the browser is resolved and checked
against the workspace before use, so a crafted request cannot reach files
outside it.
"""

from __future__ import annotations

import json
import os
import socket
import threading
from pathlib import Path

from . import colab, naming, rosters, services
from .services import grades as grades_service

colab.ensure_packages("flask")
from flask import Flask, jsonify, request, send_file  # noqa: E402


UPLOAD_FOLDER = "web_uploads"
MAX_UPLOAD_BYTES = 80 * 1024 * 1024
DEFAULT_PORT = 7860
GRADE_FILE_PREFIX = "grade_file__"

STATIC_DIR = Path(__file__).parent / "static"
APP_HTML_PATH = STATIC_DIR / "app.html"


def _json_safe(value):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return value


def _resolve_workspace(workspace_root: Path | None = None) -> Path:
    root = Path(workspace_root) if workspace_root else Path(
        os.environ.get(colab.WORKSPACE_ENV_VAR) or colab.workspace_root()
    )
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def _save_upload(file_storage, workspace: Path, subfolder: str) -> Path:
    if not file_storage or not file_storage.filename:
        raise ValueError("No se subio ningun archivo.")
    upload_dir = workspace / UPLOAD_FOLDER / subfolder
    upload_dir.mkdir(parents=True, exist_ok=True)
    out_path = upload_dir / Path(file_storage.filename).name
    file_storage.save(out_path)
    return out_path


def _parse_json_field(name: str, default):
    raw = request.form.get(name)
    if raw in (None, ""):
        return default
    return json.loads(raw)


def _parse_bool(value) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "s", "si", "sí", "yes", "y"}


def _find_free_port(start: int = DEFAULT_PORT) -> int:
    for port in range(start, start + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError("No encontre un puerto libre.")


def create_web_app(workspace_root: Path | None = None) -> Flask:
    workspace = _resolve_workspace(workspace_root)
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES

    def safe_path(value) -> Path:
        """Every path from the browser goes through here."""
        return naming.resolve_inside(Path(str(value)), workspace)

    def course_root_arg(source, key: str = "course_root") -> Path:
        return safe_path(source[key])

    @app.errorhandler(ValueError)
    def handle_value_error(error):
        return jsonify({"error": str(error)}), 400

    @app.errorhandler(FileNotFoundError)
    def handle_missing_file(error):
        return jsonify({"error": str(error)}), 404

    @app.errorhandler(FileExistsError)
    def handle_existing_file(error):
        return jsonify({"error": str(error)}), 409

    @app.errorhandler(KeyError)
    def handle_missing_field(error):
        return jsonify({"error": f"Falta el campo requerido: {error}"}), 400

    @app.get("/")
    def index():
        return APP_HTML_PATH.read_text(encoding="utf-8")

    @app.get("/api/status")
    def api_status():
        return jsonify({
            "workspace": str(workspace),
            "projects": [
                {
                    "name": project.name,
                    "path": str(project),
                    "courses": [
                        {
                            "name": course.name,
                            "path": str(course),
                            "status": _json_safe(services.course_status(course)),
                        }
                        for course in naming.course_roots_in(project)
                    ],
                }
                for project in naming.projects_in(workspace)
            ],
        })

    @app.get("/api/courses")
    def api_courses():
        project_root = safe_path(request.args["project_root"])
        return jsonify([
            {"name": path.name, "path": str(path)} for path in naming.course_roots_in(project_root)
        ])

    @app.get("/api/sections")
    def api_sections():
        return jsonify(naming.sections_in(course_root_arg(request.args)))

    @app.get("/api/labs")
    def api_labs():
        return jsonify(naming.labs_in(course_root_arg(request.args), request.args["section"]))

    @app.get("/api/students")
    def api_students():
        course_root = course_root_arg(request.args)
        section = request.args["section"]
        _, students = rosters.parse_student_list(naming.lista_path(course_root, section))
        initial = request.args.get("initial", "")
        if initial:
            students = rosters.search_by_lastname_initial(students, initial)
        return jsonify(students)

    @app.post("/api/structure/preview")
    def api_structure_preview():
        csv_path = _save_upload(request.files.get("csv"), workspace, "blackboard_csv")
        rows = services.structure.preview_roster(csv_path, request.form.get("email_domain", ""))
        return jsonify({"students_count": len(rows), "preview": rows[:12], "csv_path": str(csv_path)})

    @app.post("/api/structure/create")
    def api_structure_create():
        csv_path = _save_upload(request.files.get("csv"), workspace, "blackboard_csv")
        result = services.create_structure(
            workspace_root=workspace,
            project_name=request.form["project_name"],
            course_cycle_name=request.form["course_cycle_name"],
            section=request.form["section"],
            email_domain=request.form["email_domain"],
            csv_path=csv_path,
            overwrite=_parse_bool(request.form.get("overwrite")),
        )
        return jsonify(_json_safe(result))

    @app.post("/api/groups/preview")
    def api_groups_preview():
        payload = request.get_json(force=True)
        course_root = course_root_arg(payload)
        _, students = rosters.parse_student_list(naming.lista_path(course_root, payload["section"]))
        groups = services.preview_groups(
            students,
            int(payload.get("group_count") or 8),
            payload.get("forced_assignments") or {},
            payload.get("seed"),
        )
        return jsonify({"group_sizes": [len(group) for group in groups], "groups": groups})

    @app.post("/api/groups/create")
    def api_groups_create():
        payload = request.get_json(force=True)
        result = services.create_lab_groups(
            course_root=course_root_arg(payload),
            section=payload["section"],
            professor=payload["professor"],
            jefe=payload["jefe"],
            lab_number=int(payload["lab_number"]),
            lab_name=payload.get("lab_name") or "",
            group_count=int(payload.get("group_count") or 8),
            forced_assignments=payload.get("forced_assignments") or {},
            seed=payload.get("seed"),
            download=False,
        )
        return jsonify(_json_safe(result))

    @app.post("/api/evaluation/apply")
    def api_evaluation_apply():
        course_root = course_root_arg(request.form)
        section = request.form["section"]
        lab_number = int(request.form["lab_number"])
        templates = _parse_json_field("templates", [])

        uploaded_files = {}
        teammates_path = None
        for file_key, file_storage in request.files.items():
            if file_key == "teammates":
                teammates_path = _save_upload(file_storage, workspace, "teammates")
            elif file_key.startswith(GRADE_FILE_PREFIX):
                key = file_key[len(GRADE_FILE_PREFIX):]
                uploaded_files[key] = _save_upload(file_storage, workspace, "grade_files")

        grades_service.configure_grade_columns(course_root, section, lab_number, templates)
        result = services.apply_grade_updates(
            notas_path=naming.notas_path(course_root, section),
            lab_number=lab_number,
            custom_grade_templates=templates,
            uploaded_files=uploaded_files,
            manual_student_grades=_parse_json_field("manual_student_grades", {}),
            manual_group_grades=_parse_json_field("manual_group_grades", {}),
            teammates_csv_path=teammates_path,
            absent_codes=_parse_json_field("absent_codes", []),
        )
        return jsonify(_json_safe(result))

    @app.post("/api/absences/apply")
    def api_absences_apply():
        payload = request.get_json(force=True)
        course_root = course_root_arg(payload)
        result = services.apply_absences(
            notas_path=naming.notas_path(course_root, payload["section"]),
            lab_number=int(payload["lab_number"]),
            absent_codes=payload.get("absent_codes") or [],
            custom_grade_columns=payload.get("custom_grade_columns") or [],
        )
        return jsonify(_json_safe(result))

    @app.get("/file")
    def api_file():
        path = safe_path(request.args["path"])
        if not path.is_file():
            return jsonify({"error": "Archivo no encontrado."}), 404
        return send_file(path, as_attachment=True)

    return app


def launch_lab_manager_web_app(
    port: int | None = None,
    workspace_root: Path | None = None,
    open_browser: bool = True,
    host: str = "127.0.0.1",
):
    """Serve the app on a background thread and return its URL.

    Binds loopback by default; Colab's ``serve_kernel_port_as_window`` proxies
    localhost, so there is no need to listen on every interface.
    """
    port = port or _find_free_port()
    app = create_web_app(workspace_root=workspace_root)
    thread = threading.Thread(
        target=lambda: app.run(host=host, port=port, debug=False, use_reloader=False),
        daemon=True,
    )
    thread.start()

    url = f"http://127.0.0.1:{port}"
    print(f"Lab Manager web app running on {url}")

    if open_browser:
        try:
            from google.colab import output

            output.serve_kernel_port_as_window(port)
        except Exception:
            try:
                import webbrowser

                webbrowser.open(url)
            except Exception:
                pass

    return {"url": url, "port": port, "thread": thread}
