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
    only_cover: dict[str, tuple[str, ...]] | None = None


def create_pynguin_xmls(repos: Dataset, output_path: Path, *, cli_only: bool = False) -> None:
    """Creates Pynguin XML files for the given repositories.

    Args:
        repos: The dataset containing repositories
        output_path: Path to write the XML file
        cli_only: If True, only include CLI methods in the XML with only_cover tags
    """
    projects = {
        repo.name: create_pynguin_project(repo, cli_only=cli_only)
        for repo in repos.repositories
    }
    write_xml(projects, output_path)


def create_pynguin_project(project: Repository, *, cli_only: bool = False) -> Project:
    """Creates a Pynguin XML file for the given project.

    Args:
        project: The repository to create the project for
        cli_only: If True, collect CLI methods for each module
    """
    modules_tuple = tuple(module_to_string(module) for module in project.modules)

    cli_methods_dict = None
    if cli_only:
        cli_methods_dict = {}
        for module in project.modules:
            module_name = module_to_string(module)
            cli_callables = []

            # Collect CLI functions
            for func in module.functions:
                if func.is_cli:
                    cli_callables.extend([func.name for func in module.functions if func.is_cli])

            # Collect CLI methods from classes
            for cls in module.classes:
                cli_callables.extend(
                    f"{cls.name}.{method.name}" for method in cls.methods if method.is_cli
                )

            if cli_callables:
                cli_methods_dict[module_name] = tuple(sorted(cli_callables))

    return Project(
        project_name=project.name,
        version=project.pypi_tag,
        repository_url=project.url,
        sources="projects/" + project.name,
        modules=modules_tuple,
        only_cover=cli_methods_dict,
    )


def module_to_string(module: Module) -> str:
    """Converts a module to a pynguin-module string."""
    path = module.file_path.with_suffix("").as_posix()
    path = path.removeprefix("src/")
    return path.replace("/", ".")


def write_xml(projects: dict[str, Project], out_file: Path) -> None:
    """Saves the projects to the respective output file.

    Args:
        projects: The project data
        out_file: The output file
    """
    root_element = ET.Element("projects")
    cli_only = any(project.only_cover is not None for project in projects.values())

    for project in projects.values():
        if len(project.modules) == 0:
            continue
        proj = ET.SubElement(root_element, "project")
        ET.SubElement(proj, "name").text = project.project_name
        ET.SubElement(proj, "version").text = project.version
        ET.SubElement(proj, "repository").text = project.repository_url
        ET.SubElement(proj, "sources").text = project.sources
        modules = ET.SubElement(proj, "modules")

        if cli_only and project.only_cover:
            for module_name in sorted(project.modules):
                module_elem = ET.SubElement(modules, "module")
                ET.SubElement(module_elem, "name").text = module_name

                # Add only_cover elements for CLI methods
                if module_name in project.only_cover:
                    for cli_method in project.only_cover[module_name]:
                        ET.SubElement(module_elem, "only_cover").text = cli_method
        else:
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
