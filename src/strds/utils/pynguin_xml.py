import xml.etree.ElementTree as ET  # noqa: S405
from dataclasses import dataclass
from pathlib import Path

from strds.utils.structure import Module, Repository, Dataset


# TODO: Use "--ignore_methods" and specify all methods but one. Modify
#  `pynguin-experiments/prepare_experiment.py` to allow this. Then add all methods
#  but the selected one to the Pynguin XML file.
#  Alternative: Implement a --method flag to Pynguin that allows to specify a method
#  to test. Then adjust stuff accordingly.

# TODO: Behaviour/correctness of this script is not tested with Pynguin yet.


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
        sources="projects/" + project.name,  # TODO: Does this work?
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
