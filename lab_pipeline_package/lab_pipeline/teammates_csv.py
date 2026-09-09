"""Parsing the TeamMates peer-evaluation export.

The export is not a table: it is several labelled sections stacked in one CSV,
each with its own header row, separated by blank lines. This module locates the
three sections we care about and turns each into lookups keyed by student code,
email and name (the export is inconsistent about which it fills in).
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

from .common import clean_text, decode_csv_bytes, normalize_header, normalize_text


MAX_TM_SCORE = 20
CRITERIA_COUNT = 5

OVERALL_MARKER = "Per Recipient Statistics (Overall)"
NOT_RESPONDED_MARKER = "Participants who have not responded to any question"
SECTION_MARKERS = ("Question 1", "Question 2", "Question 3", NOT_RESPONDED_MARKER)


def read_teammates_csv(csv_path: Path) -> list[list[str]]:
    text = decode_csv_bytes(csv_path)
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except Exception:
        dialect = csv.excel
    return list(csv.reader(io.StringIO(text, newline=""), dialect))


# --- row helpers --------------------------------------------------------------


def is_blank_row(row: list[str]) -> bool:
    return all(clean_text(cell) == "" for cell in row)


def row_contains(row: list[str], text: str) -> bool:
    return normalize_text(text) in normalize_text(" ".join(clean_text(cell) for cell in row))


def find_marker_row(rows: list[list[str]], marker_text: str) -> int | None:
    for index, row in enumerate(rows):
        if row_contains(row, marker_text):
            return index
    return None


def next_non_empty_row(rows: list[list[str]], start_index: int) -> int | None:
    for index in range(start_index, len(rows)):
        if not is_blank_row(rows[index]):
            return index
    return None


def header_index_map(header_row: list[str]) -> dict[str, int]:
    return {normalize_header(value): index for index, value in enumerate(header_row) if clean_text(value)}


def column_index(header_map: dict[str, int], aliases: list[str], required: bool = True) -> int | None:
    alias_norms = [normalize_header(alias) for alias in aliases]
    for alias in alias_norms:
        if alias in header_map:
            return header_map[alias]
    for header, index in header_map.items():
        if any(alias in header or header in alias for alias in alias_norms):
            return index
    if required:
        raise ValueError(f"Could not find column with aliases: {aliases}")
    return None


def cell(row: list[str], index: int | None) -> str:
    return "" if index is None or index >= len(row) else clean_text(row[index])


def normalize_email(value) -> str:
    return clean_text(value).lower()


def code_from_email(email) -> str:
    email = normalize_email(email)
    return email.split("@", 1)[0].strip() if "@" in email else ""


def parse_float_list(value) -> list[float]:
    return [float(item) for item in re.findall(r"\d+(?:\.\d+)?", clean_text(value))]


def _section_header(rows: list[list[str]], marker: str) -> tuple[int, dict[str, int]] | None:
    marker_index = find_marker_row(rows, marker)
    if marker_index is None:
        return None
    header_index = next_non_empty_row(rows, marker_index + 1)
    if header_index is None:
        return None
    return header_index, header_index_map(rows[header_index])


class StudentLookup:
    """Three parallel indexes over the same records: by code, email, and name.

    TeamMates fills these in inconsistently, so a student is matched on code
    first, then email, then normalized name.
    """

    def __init__(self):
        self.by_code: dict[str, object] = {}
        self.by_email: dict[str, object] = {}
        self.by_name: dict[str, object] = {}

    def add(self, code: str, email: str, name: str, value) -> None:
        if code:
            self.by_code[code] = value
        if email:
            self.by_email[normalize_email(email)] = value
        if name:
            self.by_name[normalize_text(name)] = value

    def append(self, code: str, email: str, name: str, item) -> None:
        if code:
            self.by_code.setdefault(code, []).append(item)
        if email:
            self.by_email.setdefault(normalize_email(email), []).append(item)
        if name:
            self.by_name.setdefault(normalize_text(name), []).append(item)

    def find(self, student: dict, default=None):
        code = student.get("code", "")
        email = normalize_email(student.get("email", ""))
        name = normalize_text(student.get("name", ""))
        if code and code in self.by_code:
            return self.by_code[code]
        if email and email in self.by_email:
            return self.by_email[email]
        if name and name in self.by_name:
            return self.by_name[name]
        return default

    def __len__(self) -> int:
        return len(self.by_code) or len(self.by_email) or len(self.by_name)


def parse_overall_scores(rows: list[list[str]]) -> StudentLookup:
    """The "Per Recipient Statistics (Overall)" section -> TM totals.

    Prefers the per-criterion values (summed); falls back to the single Average
    column scaled by the criteria count when the export omits them.
    """
    found = _section_header(rows, OVERALL_MARKER)
    if found is None:
        raise ValueError(f'Could not find "{OVERALL_MARKER}" in CSV.')
    header_index, header_map = found

    team_idx = column_index(header_map, ["Team"], required=False)
    name_idx = column_index(header_map, ["Recipient Name"])
    email_idx = column_index(header_map, ["Recipient Email"])
    average_idx = column_index(header_map, ["Average"], required=False)
    per_criterion_idx = column_index(header_map, ["Per Criterion Average"])

    lookup = StudentLookup()
    for row in rows[header_index + 1:]:
        if is_blank_row(row) or row_contains(row, "Question 2") or row_contains(row, "Question 3"):
            break

        name = cell(row, name_idx)
        email = cell(row, email_idx)
        values = parse_float_list(cell(row, per_criterion_idx))
        if values:
            tm_total = round(sum(values), 2)
        else:
            averages = parse_float_list(cell(row, average_idx))
            tm_total = round(averages[0] * CRITERIA_COUNT, 2) if averages else None
        if tm_total is None:
            continue

        code = code_from_email(email)
        lookup.add(code, email, name, {
            "team": cell(row, team_idx),
            "name": name,
            "email": normalize_email(email),
            "code": code,
            "tm_total": tm_total,
            "tm_percentage": tm_total / MAX_TM_SCORE,
            "criterion_values": values,
        })
    return lookup


def parse_non_responders(rows: list[list[str]]) -> tuple[set, set, set]:
    """Codes, emails and names of students who answered nothing."""
    found = _section_header(rows, NOT_RESPONDED_MARKER)
    if found is None:
        print(f'Warning: could not find "{NOT_RESPONDED_MARKER}".')
        return set(), set(), set()
    header_index, header_map = found

    name_idx = column_index(header_map, ["Name"], required=False)
    email_idx = column_index(header_map, ["Email"], required=False)
    codes, emails, names = set(), set(), set()

    for row in rows[header_index + 1:]:
        if is_blank_row(row):
            continue
        name = cell(row, name_idx)
        email = cell(row, email_idx)
        code = code_from_email(email)
        if code:
            codes.add(code)
        if email:
            emails.add(normalize_email(email))
        if name:
            names.add(normalize_text(name))

    return codes, emails, names


def parse_question_comments(rows: list[list[str]], question_number: int) -> StudentLookup:
    """Free-text answers to one question, grouped by recipient."""
    marker = f"Question {question_number}"
    found = _section_header(rows, marker)
    if found is None:
        print(f'Warning: could not find "{marker}".')
        return StudentLookup()
    header_index, header_map = found

    giver_idx = column_index(header_map, ["Giver's Name", "Giver Name"])
    recipient_name_idx = column_index(header_map, ["Recipient's Name", "Recipient Name"])
    recipient_email_idx = column_index(header_map, ["Recipient's Email", "Recipient Email"])
    feedback_idx = column_index(header_map, ["Feedback"], required=False)
    giver_comment_idx = column_index(header_map, ["Giver's Comment", "Giver Comment"], required=False)

    lookup = StudentLookup()
    for row in rows[header_index + 1:]:
        if is_blank_row(row):
            continue
        if any(row_contains(row, other) for other in SECTION_MARKERS if other != marker):
            break

        pieces = [piece for piece in (cell(row, feedback_idx), cell(row, giver_comment_idx)) if piece]
        comment_text = " - ".join(dict.fromkeys(pieces)).strip()
        if not comment_text:
            continue

        giver_name = cell(row, giver_idx)
        recipient_name = cell(row, recipient_name_idx)
        recipient_email = cell(row, recipient_email_idx)
        full_comment = f"{comment_text} ({giver_name})" if giver_name else comment_text
        lookup.append(code_from_email(recipient_email), recipient_email, recipient_name, full_comment)

    return lookup


class TeammatesExport:
    """Everything we read out of one TeamMates CSV."""

    def __init__(self, rows: list[list[str]]):
        self.scores = parse_overall_scores(rows)
        self.non_responder_codes, self.non_responder_emails, self.non_responder_names = parse_non_responders(rows)
        self.q2_comments = parse_question_comments(rows, 2)
        self.q3_comments = parse_question_comments(rows, 3)

    @classmethod
    def from_path(cls, csv_path: Path) -> "TeammatesExport":
        return cls(read_teammates_csv(csv_path))

    def responded(self, student: dict) -> bool:
        code = student.get("code", "")
        email = normalize_email(student.get("email", ""))
        name = normalize_text(student.get("name", ""))
        return not (
            code in self.non_responder_codes
            or email in self.non_responder_emails
            or name in self.non_responder_names
        )
