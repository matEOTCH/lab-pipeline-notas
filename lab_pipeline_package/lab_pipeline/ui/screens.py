"""The six screens of the ipywidgets app.

Each screen builds its widgets, wires the buttons to a service call, and
displays the result. ``app`` is the :class:`~lab_pipeline.ui.app.LabManagerApp`
that owns the shared state and the error-guarded click wrapper.
"""

from __future__ import annotations

from pathlib import Path

from .. import colab, naming, services

colab.ensure_packages("ipywidgets")
import ipywidgets as widgets  # noqa: E402
from IPython.display import HTML, display  # noqa: E402

from ..grouping import MAX_GROUPS  # noqa: E402
from .components import (  # noqa: E402
    display_dataframe_preview,
    render_card,
    render_checklist,
    render_status,
    render_success_box,
)
from .pickers import (  # noqa: E402
    GRADE_METHODS,
    Picker,
    StudentSelector,
    option_pairs,
    parse_key_value_lines,
    parse_optional_int,
    upload_dir,
)
from .wizards import labeled, save_upload_value  # noqa: E402


CUSTOM_COLUMN_SLOTS = 3


def dashboard(app) -> None:
    display(render_card("Workspace activo", str(app.state.workspace_root), status="listo"))
    projects = naming.projects_in(app.state.workspace_root)

    sections_total = 0
    labs_total = 0
    alerts = []
    for project in projects:
        for course in naming.course_roots_in(project):
            status = services.course_status(course)
            sections_total += len(status["sections"])
            for section_status in status["section_status"]:
                labs_total += len(section_status["labs"])
                if not section_status["notas_path"]:
                    alerts.append(f"{course.name} / {section_status['section']}: falta Notas")

    display(HTML('<div class="lab-grid">'))
    display(render_card("Proyectos detectados", str(len(projects)), status="inspeccion"))
    display(render_card("Secciones", str(sections_total), status="detectado"))
    display(render_card("Laboratorios generados", str(labs_total), status="detectado"))
    display(render_card("Alertas pendientes", str(len(alerts)), status="revision"))
    display(HTML("</div>"))

    if alerts:
        display(render_checklist([(alert, False) for alert in alerts[:8]]))
    else:
        display(render_status("No hay alertas visibles en el escaneo rapido.", "success"))


def structure(app) -> None:
    project_dropdown = widgets.Dropdown(
        options=[("Crear nuevo", "")] + option_pairs(naming.projects_in(app.state.workspace_root))
    )
    project_text = widgets.Text(placeholder="2026")
    course_text = widgets.Text(placeholder="Quimica General 2026-1")
    section_text = widgets.Text(placeholder="315")
    domain_text = widgets.Text(value="aloe.ulima.edu.pe")
    overwrite = widgets.Checkbox(value=False, description="Sobrescribir si ya existe")
    uploader = widgets.FileUpload(accept=".csv", multiple=False, description="Subir CSV")
    preview_button = widgets.Button(description="Previsualizar", button_style="info")
    create_button = widgets.Button(description="Crear Lista y Notas", button_style="success")
    out = widgets.Output()

    def project_name() -> str:
        return Path(project_dropdown.value).name if project_dropdown.value else project_text.value.strip()

    def preview():
        csv_path = save_upload_value(uploader.value, upload_dir("roster"))
        rows = services.structure.preview_roster(csv_path, domain_text.value)
        display(render_success_box(f"CSV valido. Estudiantes detectados: {len(rows)}"))
        display_dataframe_preview(rows)

    def create():
        csv_path = save_upload_value(uploader.value, upload_dir("roster"))
        result = services.create_structure(
            workspace_root=app.state.workspace_root,
            project_name=project_name(),
            course_cycle_name=course_text.value,
            section=section_text.value,
            email_domain=domain_text.value,
            csv_path=csv_path,
            overwrite=overwrite.value,
        )
        app.state.project_root = result["project_root"]
        app.state.course_root = result["course_root"]
        app.state.section = result["section"]
        display(render_success_box("Estructura creada correctamente."))
        app.record_outputs({"Lista": result["list_path"], "Notas": result["notas_path"]})
        display_dataframe_preview(result["students"])

    preview_button.on_click(app.guarded(out, preview))
    create_button.on_click(app.guarded(out, create))
    display(widgets.VBox([
        render_checklist([
            ("Seleccionar o crear proyecto", False),
            ("Ingresar curso/ciclo", False),
            ("Subir CSV de Blackboard", False),
            ("Previsualizar y crear Lista/Notas", False),
        ]),
        labeled("Proyecto existente", project_dropdown),
        labeled("Nuevo proyecto", project_text),
        labeled("Curso/ciclo", course_text),
        labeled("Seccion", section_text),
        labeled("Dominio institucional", domain_text),
        labeled("CSV Blackboard", uploader),
        overwrite,
        widgets.HBox([preview_button, create_button]),
        out,
    ]))


def groups(app) -> None:
    picker = Picker(app.state.workspace_root)
    professor = widgets.Text(placeholder="Perez, Martin")
    jefe = widgets.Text(placeholder="Tapia, Mateo")
    lab_number = widgets.BoundedIntText(value=1, min=1, max=40)
    lab_name = widgets.Text(placeholder="Nombre opcional del laboratorio")
    group_count = widgets.BoundedIntText(value=MAX_GROUPS, min=1, max=MAX_GROUPS)
    seed = widgets.Text(placeholder="opcional")
    forced_group = widgets.BoundedIntText(value=1, min=1, max=MAX_GROUPS, layout=widgets.Layout(width="90px"))
    add_forced = widgets.Button(description="Agregar asignacion", button_style="info")
    preview_button = widgets.Button(description="Vista previa", button_style="info")
    generate_button = widgets.Button(description="Generar PDF, CSVs y ZIP", button_style="success")
    out = widgets.Output()

    forced_assignments: dict[str, int] = {}
    selector = StudentSelector(picker)

    def remember_people(*_):
        if not (picker.course.value and picker.section.value):
            return
        people = services.groups.section_people(picker.course_root, picker.section.value)
        professor.value = people["professor"] or professor.value
        jefe.value = people["jefe"] or jefe.value

    picker.section.observe(remember_people, names="value")
    remember_people()

    def add_assignment():
        code = selector.add()
        if not code:
            raise ValueError("Seleccione un alumno candidato.")
        forced_assignments[code] = int(forced_group.value)
        display(render_success_box(f"Asignacion fija agregada: {code} -> Grupo {forced_group.value}"))

    def preview():
        result = services.preview_groups(
            picker.students(), int(group_count.value), forced_assignments, parse_optional_int(seed.value)
        )
        rows = [
            {"Grupo": index, "Codigo": student["code"], "Nombre": student["name"]}
            for index, group in enumerate(result, start=1)
            for student in group
        ]
        display(render_success_box(f"Vista previa lista. Tamaños: {[len(group) for group in result]}"))
        display_dataframe_preview(rows, limit=60)

    def generate():
        result = services.create_lab_groups(
            course_root=picker.course_root,
            section=picker.section.value,
            professor=professor.value,
            jefe=jefe.value,
            lab_number=int(lab_number.value),
            lab_name=lab_name.value,
            group_count=int(group_count.value),
            forced_assignments=forced_assignments,
            seed=parse_optional_int(seed.value),
            download=True,
        )
        app.state.course_root = result["course_root"]
        app.state.section = result["section"]
        app.state.lab_number = result["lab_number"]
        display(render_success_box("Grupos generados correctamente."))
        for warning in result["warnings"]:
            display(render_status(warning, "warning"))
        app.record_outputs({
            "PDF": result["pdf_path"],
            "Blackboard Groups CSV": result["groups_csv"],
            "Blackboard Members CSV": result["members_csv"],
            "ZIP": result["zip_path"],
        })

    add_forced.on_click(app.guarded(out, add_assignment))
    preview_button.on_click(app.guarded(out, preview))
    generate_button.on_click(app.guarded(out, generate))
    display(widgets.VBox(picker.fields() + [
        labeled("Profesor", professor),
        labeled("Jefe de practica", jefe),
        labeled("Numero de laboratorio", lab_number),
        labeled("Nombre laboratorio", lab_name),
        labeled("Numero de grupos", group_count),
        labeled("Seed", seed),
        render_card("Asignaciones fijas", "Busque por inicial, seleccione alumno y grupo especifico."),
        widgets.HBox([
            labeled("Inicial apellido", selector.initial),
            labeled("Alumno", selector.candidates),
            labeled("Grupo", forced_group),
            add_forced,
        ]),
        widgets.HBox([preview_button, generate_button]),
        out,
    ]))


def evaluation(app) -> None:
    picker = Picker(app.state.workspace_root, include_labs=True)
    teammates_upload = widgets.FileUpload(accept=".csv", multiple=False, description="Teammates CSV")
    use_tm = widgets.Checkbox(value=True, description="Actualizar Teammates")
    apply_button = widgets.Button(description="Aplicar actualizacion", button_style="success")
    out = widgets.Output()

    column_rows = [
        (
            widgets.Text(placeholder=f"NotaExtra{index}_Lab"),
            widgets.Dropdown(options=GRADE_METHODS),
            widgets.FileUpload(accept=".csv,.xls", multiple=False, description="Archivo BB"),
            widgets.Textarea(
                placeholder="Para manual: codigo=nota o grupo=nota, una linea por valor",
                layout=widgets.Layout(width="420px", height="70px"),
            ),
        )
        for index in range(1, CUSTOM_COLUMN_SLOTS + 1)
    ]

    def apply():
        lab_number = picker.lab_number
        templates = []
        uploaded_files: dict[str, Path] = {}
        manual_student: dict[str, dict] = {}
        manual_group: dict[str, dict] = {}

        # Keyed by template position: the service materializes the column name.
        for base, method, upload, values in column_rows:
            if not base.value.strip() or not method.value:
                continue
            index = str(len(templates))
            templates.append({"base_name": base.value.strip(), "method": method.value})
            if method.value == "1":
                uploaded_files[index] = save_upload_value(upload.value, upload_dir("grades"))
            elif method.value == "2":
                manual_student[index] = parse_key_value_lines(values.value)
            else:
                manual_group[index] = parse_key_value_lines(values.value)

        services.configure_grade_columns(picker.course_root, picker.section.value, lab_number, templates)
        teammates_path = (
            save_upload_value(teammates_upload.value, upload_dir("teammates")) if use_tm.value else None
        )
        result = services.apply_grade_updates(
            notas_path=picker.notas_path(),
            lab_number=lab_number,
            custom_grade_templates=templates,
            uploaded_files=uploaded_files,
            manual_student_grades=manual_student,
            manual_group_grades=manual_group,
            teammates_csv_path=teammates_path,
        )
        display(render_success_box("Evaluacion actualizada correctamente."))
        app.record_outputs({"Notas actualizado": result["notas_path"]})
        display(render_card(
            "Resumen", f"Columnas nuevas: {', '.join(result['created_columns']) or 'ninguna'}"
        ))

    apply_button.on_click(app.guarded(out, apply))
    column_widgets = []
    for index, (base, method, upload, values) in enumerate(column_rows, start=1):
        column_widgets.extend([
            render_card(f"Columna adicional {index}", "Deje el metodo en Ninguno si no la usara."),
            labeled("Nombre base", base),
            labeled("Metodo", method),
            labeled("Archivo Blackboard", upload),
            labeled("Valores manuales", values),
        ])
    display(widgets.VBox(picker.fields() + [
        render_card(
            "Columnas canonicas",
            "Grupo_LabN, %TMN, TMN_Resp?, Nota_LabN y columnas adicionales configuradas.",
        ),
        use_tm,
        labeled("Archivo Teammates", teammates_upload),
        *column_widgets,
        apply_button,
        out,
    ]))


def absences(app) -> None:
    picker = Picker(app.state.workspace_root, include_labs=True)
    selected = widgets.SelectMultiple(options=[], rows=5)
    add_button = widgets.Button(description="Marcar candidato", button_style="info")
    preview_button = widgets.Button(description="Ver impacto", button_style="info")
    apply_button = widgets.Button(description="Confirmar y aplicar", button_style="danger")
    out = widgets.Output()

    selector = StudentSelector(picker)
    selector.on_change = lambda: setattr(
        selected, "options", [(label, code) for code, label in selector.chosen.items()]
    )

    def add_candidate():
        if not selector.add():
            raise ValueError("Seleccione un alumno candidato.")

    def preview():
        result = services.preview_absences(picker.notas_path(), picker.lab_number, selector.codes)
        rows = [
            {
                "Codigo": student["code"],
                "Nombre": student["name"],
                "Cambios": ", ".join(change["column"] for change in student["changes"]),
            }
            for student in result["students"]
        ]
        display_dataframe_preview(rows, limit=30)
        if result["not_found_codes"]:
            display(render_status(f"No encontrados: {', '.join(result['not_found_codes'])}", "warning"))

    def apply():
        result = services.apply_absences(picker.notas_path(), picker.lab_number, selector.codes)
        display(render_success_box(f"Ausentes actualizados: {result['absences_updated']}"))
        app.record_outputs({"Notas actualizado": result["notas_path"]})

    add_button.on_click(app.guarded(out, add_candidate))
    preview_button.on_click(app.guarded(out, preview))
    apply_button.on_click(app.guarded(out, apply))
    display(widgets.VBox(picker.fields() + [
        render_card(
            "Marcar ausentes",
            "Busque por inicial de apellido, agregue alumnos y revise el impacto antes de aplicar.",
        ),
        widgets.HBox([
            labeled("Inicial apellido", selector.initial),
            labeled("Alumno", selector.candidates),
            add_button,
        ]),
        labeled("Ausentes seleccionados", selected),
        widgets.HBox([preview_button, apply_button]),
        out,
    ]))


def outputs(app) -> None:
    from .components import render_output_links

    if app.state.last_outputs:
        display(render_output_links(app.state.last_outputs))
    else:
        display(render_status("Aun no hay outputs generados en esta sesion.", "warning"))
    keys = app.state.last_outputs
    display(render_checklist([
        ("PDF de grupos", any("PDF" in key for key in keys)),
        ("CSV de grupos Blackboard", any("Groups" in key for key in keys)),
        ("CSV de miembros Blackboard", any("Members" in key for key in keys)),
        ("Excel de notas actualizado", any("Notas" in key for key in keys)),
        ("ZIP final", any("ZIP" in key for key in keys)),
    ]))
