"""Script to generate statistics from a dataset file and a repos file.

This script takes a dataset file (JSON) and a repos file (CSV) as input and
provides an overview of the dataset in a tabular format.
"""

import ast
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from strds.utils.flapy_csv_utils import FlaPyProject, parse_csv
from strds.utils.latex import export_to_latex
from strds.utils.pynguin_xml import module_to_string, read_xml
from strds.utils.structure import Dataset, Repository, load_from_json_file

console = Console()


def get_language_percentages(languages_str: str) -> dict[str, float]:
    """Parse the GitHub languages string and return a dictionary of language percentages.

    Args:
        languages_str: A string representation of the GitHub languages dictionary

    Returns:
        A dictionary mapping language names to their percentage in the codebase
    """
    try:
        # Parse the languages string into a dictionary
        languages_dict = ast.literal_eval(languages_str)

        # Calculate the total lines of code
        total_loc = sum(languages_dict.values())

        # Calculate the percentage for each language
        return {lang: (loc / total_loc) * 100 for lang, loc in languages_dict.items()}
    except (SyntaxError, ValueError, TypeError):
        return {}


def get_cc_percentage(languages_str: str) -> float:
    """Calculate the percentage of C/C++ code in the codebase.

    Args:
        languages_str: A string representation of the GitHub languages dictionary

    Returns:
        The percentage of C/C++ code in the codebase
    """
    percentages = get_language_percentages(languages_str)
    c_percentage = percentages.get("C", 0)
    cpp_percentage = percentages.get("C++", 0)
    return c_percentage + cpp_percentage


def count_modules_per_project(dataset: Dataset) -> dict[str, int]:
    """Count the number of modules per project in the dataset.

    Args:
        dataset: The dataset containing repositories and their modules

    Returns:
        A dictionary mapping project names to their module counts
    """
    return {repo.name: len(repo.modules) for repo in dataset.repositories}


def get_project_stats(
    dataset: Dataset,
    projects: list[FlaPyProject]
) -> list[dict[str, Any]]:
    """Generate statistics for each project.

    Args:
        dataset: The dataset containing repositories and their modules
        projects: List of FlaPyProject objects from the CSV file

    Returns:
        A list of dictionaries containing statistics for each project
    """
    # Create a lookup dictionary for projects from the CSV file
    projects_dict = {project.project_name: project for project in projects}

    # Count modules per project
    modules_count = count_modules_per_project(dataset)

    # Generate statistics for each project
    stats = []
    for repo in dataset.repositories:
        project_name = repo.name

        # Get the corresponding project from the CSV file
        project = projects_dict.get(project_name)

        if project:
            # Calculate C/C++ percentage and bytes in MB
            cc_percentage = 0.0
            python_mb = 0.0
            cc_mb = 0.0
            if project.github_languages:
                # Convert the dictionary to a string representation for get_cc_percentage
                languages_str = str(project.github_languages)
                cc_percentage = get_cc_percentage(languages_str)
                try:
                    languages_dict = ast.literal_eval(languages_str)
                    python_bytes = languages_dict.get("Python", 0)
                    cc_bytes = languages_dict.get("C", 0) + languages_dict.get("C++", 0)
                    python_mb = round(python_bytes / (1024 * 1024), 2)
                    cc_mb = round(cc_bytes / (1024 * 1024), 2)
                except Exception:  # noqa: BLE001
                    python_mb = 0.0
                    cc_mb = 0.0

            stats.append({
                "project_name": project_name,
                "modules_count": modules_count.get(project_name, 0),
                "version_tag": repo.pypi_tag,
                "cc_percentage": cc_percentage,
                "python_mb": python_mb,
                "cc_mb": cc_mb
            })

    return stats


def filter_dataset_with_xml(dataset: Dataset, xml_projects: dict[str, Any]) -> Dataset:
    """Filter the dataset to only include projects and modules that exist in the XML.

    Args:
        dataset: The dataset to filter
        xml_projects: Dictionary of projects from the XML file

    Returns:
        A new dataset with only the projects and modules that exist in the XML
    """
    # Get the project names from the XML
    xml_project_names = set(xml_projects.keys())
    filtered_repositories = []

    for repo in dataset.repositories:
        if repo.name in xml_project_names:
            # Get the modules from the XML for this project
            xml_project_modules = set(xml_projects[repo.name].modules)

            # Filter the repository's modules to only include those that exist in the XML
            filtered_modules = [
                module for module in repo.modules
                if module_to_string(module) in xml_project_modules
            ]

            # Create a new Repository object with the filtered modules
            filtered_repo = Repository(
                name=repo.name,
                url=repo.url,
                pypi_tag=repo.pypi_tag,
                git_commit_hash=repo.git_commit_hash,
                modules=filtered_modules
            )

            filtered_repositories.append(filtered_repo)

    # Create a new dataset with the filtered repositories
    return Dataset(repositories=filtered_repositories)


def print_table(stats: list[dict[str, Any]]) -> Table:
    """Create a rich table with the statistics.

    Args:
        stats: A list of dictionaries containing statistics for each project

    Returns:
        A rich Table object containing the statistics
    """
    # Create a table
    table = Table(title="Dataset Statistics")

    # Add columns
    table.add_column("Project Name", style="cyan")
    table.add_column("Modules Count", justify="right", style="green")
    table.add_column("Version/Tag", style="yellow")
    table.add_column("C/C++ Percentage", justify="right", style="magenta")

    # Add rows
    for stat in stats:
        table.add_row(
            stat["project_name"],
            str(stat["modules_count"]),
            stat["version_tag"],
            f"{stat['cc_percentage']:.2f}%"
        )

    return table


@click.command()
@click.argument(
    "dataset_file",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path),
)
@click.argument(
    "repos_file",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--latex-output",
    type=click.Path(file_okay=True, dir_okay=False, path_type=Path),
    help="Path to export the table as LaTeX",
)
@click.option(
    "--filtered-xml",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path),
    help="Path to XML file to filter projects for",
)
def cli(
    dataset_file: Path,
    repos_file: Path,
    latex_output: Path | None = None,
    filtered_xml: Path | None = None,
) -> None:
    """Main function to run the script.

    Args:
        dataset_file: Path to the dataset file (JSON)
        repos_file: Path to the repos file (CSV)
        latex_output: Optional path to export the table as LaTeX
        filtered_xml: Optional path to the Pynguin-XML file to filter projects/modules for
    """
    # Load the dataset file
    dataset = load_from_json_file(dataset_file)

    # Filter dataset if filtered_xml is provided
    if filtered_xml:
        # Read the XML file
        xml_projects = read_xml(filtered_xml)

        # Filter the dataset to only include projects and modules that exist in the XML
        dataset = filter_dataset_with_xml(dataset, xml_projects)

    # Load the repos file
    projects = parse_csv(repos_file)

    # Generate statistics
    stats = get_project_stats(dataset, projects)

    # Create and display the table
    table = print_table(stats)
    console.print(table)

    # Export to LaTeX if requested
    if latex_output:
        export_to_latex(stats, latex_output)


if __name__ == "__main__":
    # pylint: disable=no-value-for-parameter
    cli()
