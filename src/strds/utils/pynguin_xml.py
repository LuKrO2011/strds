"""Utility functions for Pynguin XML files."""

import xml.etree.ElementTree as ET  # noqa: S405
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from defusedxml.ElementTree import parse

from strds.utils.structure import Dataset, Module, Repository


@dataclass(frozen=True)
class Project:
    """The data for a project for Pynguin."""

    project_name: str
    version: str
    repository_url: str
    sources: str
    modules: tuple[str, ...]


def create_pynguin_xmls(repos: Dataset, output_path: Path) -> None:
    """Creates Pynguin XML files for the given repositories."""
    projects = {repo.name: create_pynguin_project(repo) for repo in repos.repositories}
    write_xml(projects, output_path)


def create_pynguin_project(project: Repository) -> Project:
    """Creates a Pynguin XML file for the given project."""
    return Project(
        project_name=project.name,
        version=project.pypi_tag,
        repository_url=project.url,
        sources="projects/" + project.name,
        modules=tuple(module_to_string(module) for module in project.modules),
    )


def module_to_string(module: Module) -> str:
    """Converts a module to a pynguin-module string."""
    return module.file_path.with_suffix("").as_posix().replace("/", ".")


def write_xml(projects: dict[str, Project], out_file: Path) -> None:
    """Saves the projects to the respective output file.

    Args:
        projects: The project data
        out_file: The output file
    """
    root_element = ET.Element("projects")
    for project in projects.values():
        if len(project.modules) == 0:
            continue
        proj = ET.SubElement(root_element, "project")
        ET.SubElement(proj, "name").text = project.project_name
        ET.SubElement(proj, "version").text = project.version
        ET.SubElement(proj, "repository").text = project.repository_url
        ET.SubElement(proj, "sources").text = project.sources
        modules = ET.SubElement(proj, "modules")
        for module in sorted(project.modules):
            ET.SubElement(modules, "module").text = module

    tree = ET.ElementTree(root_element)
    tree.write(out_file, encoding="unicode", xml_declaration=True)


def _get_text(element: ET.Element | Any | None) -> str:
    """Safely gets the text of an XML element."""
    if isinstance(element, ET.Element):
        return element.text if element.text is not None else ""
    return ""


def _parse_modules(modules_element: ET.Element | None) -> tuple[str, ...]:
    """Parses the modules from the given XML element."""
    if modules_element is not None and isinstance(modules_element, ET.Element):
        modules = tuple(
            _get_text(module)
            for module in modules_element
            if isinstance(module, ET.Element)
        )
    else:
        modules = ()
    return modules


def read_xml(file: Path) -> dict[str, Project]:
    """Reads the projects from the given XML file.

    Args:
        file: The XML file to read

    Returns:
        The projects
    """
    tree = parse(file)
    root = tree.getroot()
    projects = {}
    for project in root:
        project_name = _get_text(project.find("name"))
        version = _get_text(project.find("version"))
        repository_url = _get_text(project.find("repository"))
        sources = _get_text(project.find("sources"))
        modules_element = project.find("modules")
        modules = _parse_modules(modules_element)
        projects[project_name] = Project(
            project_name=project_name,
            version=version,
            repository_url=repository_url,
            sources=sources,
            modules=modules,
        )
    return projects
