"""Utilities for parsing CSV files containing FlaPy project data."""

import csv
from ast import literal_eval
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class FlaPyProject:  # pylint: disable=too-many-instance-attributes
    """Dataclass representing a FlaPy project."""

    project_name: str
    github_url: str
    matching_github_tag: str | None
    pypi_latest_tag: str | None
    funcs_to_trace: str | None
    tests_to_run: str | None
    pypi_fetch_status: str | None
    pypi_http_response_code: int
    pypi_classifiers: list[str]
    pypi_project_urls: dict[str, str]
    github_url_status: float
    git_tags: list[str]


def parse_list_field(field: str) -> list[Any]:
    """Parses a list field from the CSV (string is in Python list format)."""
    if field and field.startswith("[") and field.endswith("]"):
        try:
            parsed_field = literal_eval(field)
            if isinstance(parsed_field, list):
                return parsed_field
        except (ValueError, SyntaxError):
            pass
    return []


def parse_dict_field(field: str) -> dict[str, Any]:
    """Parses a dictionary field from the CSV (string is in Python dict format)."""
    if field and field.startswith("{") and field.endswith("}"):
        try:
            parsed_field = literal_eval(field)
            if isinstance(parsed_field, dict):
                return parsed_field
        except (ValueError, SyntaxError):
            pass
    return {}


def parse_int_field(field: str) -> int:
    """Safely converts a field to an integer."""
    try:
        return int(float(field))
    except (ValueError, TypeError):
        return 0


def parse_float_field(field: str) -> float:
    """Safely converts a field to a float."""
    try:
        return float(field)
    except (ValueError, TypeError):
        return 0.0


def parse_optional_field(field: str) -> str | None:
    """Returns None if the field is empty, otherwise returns the field as is."""
    return field if field.strip() else None


def parse_csv(file_path: Path) -> list[FlaPyProject]:
    """Reads a CSV file and converts rows into a list of dataclass objects."""
    projects = []
    with open(file_path, encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            project = FlaPyProject(
                project_name=row["Project_Name"],
                github_url=row["Github_URL"],
                matching_github_tag=parse_optional_field(row["matching_github_tag"]),
                pypi_latest_tag=parse_optional_field(row["PYPI_latest_tag"]),
                funcs_to_trace=parse_optional_field(row["funcs_to_trace"]),
                tests_to_run=parse_optional_field(row["tests_to_run"]),
                pypi_fetch_status=parse_optional_field(row["pypi_fetch_status"]),
                pypi_http_response_code=parse_int_field(row["pypi_http_response_code"]),
                pypi_classifiers=parse_list_field(row["PYPI_classifiers"]),
                pypi_project_urls=parse_dict_field(row["PYPI_project_urls"]),
                github_url_status=parse_float_field(row["github_url_status"]),
                git_tags=parse_list_field(row["git_tags"]),
            )
            projects.append(project)
    return projects
