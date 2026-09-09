"""Generated artefacts for one lab: the groups PDF, Blackboard CSVs, and zip."""

from __future__ import annotations

import csv
import shutil
import time
import zipfile
from pathlib import Path

from . import colab
from .common import clean_text


GROUPS_CSV_HEADERS = ["Group Code*", "Title*", "Description", "Group Set*", "Self Enroll*"]
MEMBERS_CSV_HEADERS = ["Group Code*", "User Name*", "Student Id", "First Name", "Last Name", "Group Set"]

MIN_PDF_ROWS_PER_GROUP = 5


def blackboard_group_prefix(lab_number: int) -> str:
    return f"Grupo_gc_Lab{int(lab_number)}_"


def blackboard_set_name(lab_number: int) -> str:
    return f"Laboratorio_{int(lab_number)}"


def split_blackboard_name(full_name: str) -> tuple[str, str]:
    """"CASTRO, CARLA" -> ("Carla", "Castro"); falls back to first-token split."""
    full_name = clean_text(full_name)
    if "," in full_name:
        last, first = full_name.split(",", 1)
        return first.strip().title(), last.strip().title()

    parts = full_name.title().split()
    first = parts[0] if parts else ""
    last = " ".join(parts[1:]) if len(parts) > 1 else ""
    return first, last


def write_blackboard_csvs(
    groups: list[list[dict]],
    section: str,
    lab_number: int,
    groups_out: Path,
    members_out: Path,
    self_enroll: str = "N",
) -> tuple[Path, Path]:
    prefix = blackboard_group_prefix(lab_number)
    set_name = blackboard_set_name(lab_number)
    groups_out, members_out = Path(groups_out), Path(members_out)
    groups_out.parent.mkdir(parents=True, exist_ok=True)
    members_out.parent.mkdir(parents=True, exist_ok=True)

    with groups_out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(GROUPS_CSV_HEADERS)
        for group_number in range(1, len(groups) + 1):
            writer.writerow([
                f"{prefix}{group_number}",
                f"Grupo {group_number}",
                f"Grupo de laboratorio {group_number} - Seccion {section}",
                set_name,
                self_enroll,
            ])

    with members_out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(MEMBERS_CSV_HEADERS)
        for group_number, group in enumerate(groups, start=1):
            for student in group:
                first, last = split_blackboard_name(student["name"])
                writer.writerow([f"{prefix}{group_number}", student["code"], "", first, last, set_name])

    return groups_out, members_out


def write_groups_pdf(
    groups: list[list[dict]],
    section: str,
    professor: str,
    jefe: str,
    lab_number: int,
    out_path: Path,
) -> Path:
    colab.ensure_packages("reportlab")
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    normal = getSampleStyleSheet()["Normal"]
    normal.fontName = "Helvetica"
    normal.fontSize = 9
    normal.leading = 11

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        rightMargin=1.1 * cm,
        leftMargin=1.1 * cm,
        topMargin=1.0 * cm,
        bottomMargin=1.0 * cm,
    )

    info_table = Table(
        [
            ["", "Seccion", section],
            ["", "Profesor", professor],
            ["", "Jefe de Practica", jefe],
            ["", f"Laboratorio N° {int(lab_number)}", ""],
        ],
        colWidths=[3.0 * cm, 4.2 * cm, 10.0 * cm],
    )
    info_table.setStyle(TableStyle([
        ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
    ]))

    table_rows = [["Grupo N°", "Codigo", "Apellidos y Nombres"]]
    spans = []
    current_row = 1
    for group_number, group in enumerate(groups, start=1):
        start_row = current_row
        for index in range(max(MIN_PDF_ROWS_PER_GROUP, len(group))):
            label = str(group_number) if index == 0 else ""
            if index < len(group):
                student = group[index]
                table_rows.append([label, student["code"], Paragraph(student["name"], normal)])
            else:
                table_rows.append([label, "", ""])
            current_row += 1
        spans.append((start_row, current_row - 1))

    group_table = Table(table_rows, colWidths=[3.0 * cm, 4.0 * cm, 10.0 * cm], repeatRows=1)
    style_commands = [
        ("GRID", (0, 0), (-1, -1), 1.0, colors.black),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 11),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("ALIGN", (0, 1), (1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 1), (1, -1), 10),
        ("LEFTPADDING", (2, 1), (2, -1), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white]),
    ]
    for start_row, end_row in spans:
        style_commands.append(("SPAN", (0, start_row), (0, end_row)))
        style_commands.append(("FONTSIZE", (0, start_row), (0, end_row), 14))
    group_table.setStyle(TableStyle(style_commands))

    doc.build([info_table, Spacer(1, 0.35 * cm), group_table])
    return out_path


def write_bundle_zip(paths: list[Path], zip_path: Path) -> Path:
    zip_path = Path(zip_path)
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            archive.write(path, arcname=Path(path).name)
    return zip_path


def download(paths: list[Path]) -> None:
    """Push files to the browser in Colab. No-op anywhere else.

    Colab drops downloads when several are queued at once, so prefer the bundled
    ZIP when one is present.
    """
    if not colab.running_in_colab():
        return
    from google.colab import files
    from IPython.display import FileLink, display

    zips = [Path(path) for path in paths if Path(path).suffix.lower() == ".zip"]
    download_list = zips or [Path(path) for path in paths]

    print("\nIniciando descarga...")
    print("La descarga puede tardar 15 a 20 segundos en aparecer en el navegador.")
    for path in download_list:
        local_path = Path("/content") / path.name
        shutil.copy(path, local_path)
        print(f"Descargando: {local_path.name}")
        files.download(str(local_path))
        time.sleep(3)
        print("\nSi la descarga automatica queda cargando, use este enlace manual:")
        display(FileLink(str(local_path)))

    print("Descarga enviada. La celda terminara ahora para que Colab libere la descarga.")
