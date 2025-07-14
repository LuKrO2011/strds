"""Tests for the stats module."""

import xml.etree.ElementTree as ET  # noqa: S405
from pathlib import Path
from typing import Any

import pytest
from rich.table import Table

from strds.stats import (
    count_modules_per_project,
    export_to_latex,
    filter_dataset_with_xml,
    get_cc_percentage,
    get_language_percentages,
    get_project_stats,
    print_table,
)
from strds.utils.flapy_csv_utils import FlaPyProject
from strds.utils.pynguin_xml import read_xml
from strds.utils.structure import Dataset, Module, Repository


@pytest.fixture
def repo1() -> Repository:
    """Fixture for a test repository with two modules."""
    return Repository(
        name="repo1",
        url="https://github.com/user/repo1",
        pypi_tag="1.0.0",
        git_commit_hash="abc123",
        modules=[
            Module(name="module1", file_path=Path("module1.py")),
            Module(name="module2", file_path=Path("module2.py")),
        ],
    )


@pytest.fixture
def repo2() -> Repository:
    """Fixture for a test repository with one module."""
    return Repository(
        name="repo2",
        url="https://github.com/user/repo2",
        pypi_tag="2.0.0",
        git_commit_hash="def456",
        modules=[
            Module(name="module3", file_path=Path("module3.py")),
        ],
    )


@pytest.fixture
def repo3() -> Repository:
    """Fixture for a test repository with two modules."""
    return Repository(
        name="repo3",
        url="https://github.com/user/repo3",
        pypi_tag="3.0.0",
        git_commit_hash="ghi789",
        modules=[
            Module(name="module5", file_path=Path("module5.py")),
            Module(name="module6", file_path=Path("module6.py")),  # This module won't be in the XML
        ],
    )


@pytest.fixture
def basic_dataset(repo1: Repository, repo2: Repository) -> Dataset:
    """Fixture for a basic dataset with two repositories."""
    return Dataset(repositories=[repo1, repo2])


@pytest.fixture
def extended_dataset(repo1: Repository, repo2: Repository, repo3: Repository) -> Dataset:
    """Fixture for an extended dataset with three repositories."""
    return Dataset(repositories=[repo1, repo2, repo3])


@pytest.fixture
def flapy_projects() -> list[FlaPyProject]:
    """Fixture for FlaPyProject objects used in tests."""
    project1 = FlaPyProject(
        project_name="repo1",
        github_url="https://github.com/user/repo1",
        matching_github_tag=None,
        pypi_latest_tag="1.0.0",
        funcs_to_trace=None,
        tests_to_run=None,
        pypi_fetch_status=None,
        pypi_http_response_code=200,
        pypi_classifiers=[],
        pypi_project_urls={},
        github_url_status=200.0,
        git_tags=[],
        github_languages={"Python": 1000, "C": 500, "C++": 500},
    )
    project2 = FlaPyProject(
        project_name="repo2",
        github_url="https://github.com/user/repo2",
        matching_github_tag=None,
        pypi_latest_tag="2.0.0",
        funcs_to_trace=None,
        tests_to_run=None,
        pypi_fetch_status=None,
        pypi_http_response_code=200,
        pypi_classifiers=[],
        pypi_project_urls={},
        github_url_status=200.0,
        git_tags=[],
        github_languages={"Python": 1000, "Java": 500},
    )
    return [project1, project2]


@pytest.fixture
def stats_data() -> list[dict[str, Any]]:
    """Fixture for stats data used in table tests."""
    return [
        {
            "project_name": "repo1",
            "modules_count": 2,
            "version_tag": "1.0.0",
            "python_mb": 0.95,
            "cc_mb": 0.48,
            "cc_percentage": 50.0,
        },
        {
            "project_name": "repo2",
            "modules_count": 1,
            "version_tag": "2.0.0",
            "python_mb": 0.95,
            "cc_mb": 0.0,
            "cc_percentage": 0.0,
        },
    ]


@pytest.fixture
def xml_file(tmp_path: Path) -> Path:
    """Fixture for creating a temporary XML file with specific content.

    Creates an XML file with two projects (repo1 and repo3) and selected modules.
    repo1 includes module1 and module2 (but not module3).
    repo3 includes module5 (but not module6).
    """
    # Create a temporary XML file with only repo1 and repo3, and only some of their modules
    tmp_file = tmp_path / "test.xml"

    # Create XML content
    root_element = ET.Element("projects")

    # Add repo1 with only module1 and module2
    proj1 = ET.SubElement(root_element, "project")
    ET.SubElement(proj1, "name").text = "repo1"
    ET.SubElement(proj1, "version").text = "1.0.0"
    ET.SubElement(proj1, "repository").text = "https://github.com/user/repo1"
    ET.SubElement(proj1, "sources").text = "projects/repo1"
    modules1 = ET.SubElement(proj1, "modules")
    ET.SubElement(modules1, "module").text = "module1"
    ET.SubElement(modules1, "module").text = "module2"
    # Note: module3 is not included in the XML

    # Add repo3 with only module5
    proj3 = ET.SubElement(root_element, "project")
    ET.SubElement(proj3, "name").text = "repo3"
    ET.SubElement(proj3, "version").text = "3.0.0"
    ET.SubElement(proj3, "repository").text = "https://github.com/user/repo3"
    ET.SubElement(proj3, "sources").text = "projects/repo3"
    modules3 = ET.SubElement(proj3, "modules")
    ET.SubElement(modules3, "module").text = "module5"
    # Note: module6 is not included in the XML

    # Write XML to file
    tree = ET.ElementTree(root_element)
    tree.write(tmp_file, encoding="unicode", xml_declaration=True)

    return tmp_file


def test_get_language_percentages():
    """Test the get_language_percentages function."""
    # Test with a valid languages string
    languages_str = "{'Python': 1000, 'C': 500, 'C++': 500}"
    percentages = get_language_percentages(languages_str)
    assert percentages == {"Python": 50.0, "C": 25.0, "C++": 25.0}

    # Test with an empty languages string
    percentages = get_language_percentages("")
    assert percentages == {}

    # Test with an invalid languages string
    percentages = get_language_percentages("{invalid syntax}")
    assert percentages == {}


def test_get_cc_percentage():
    """Test the get_cc_percentage function."""
    # Test with a valid languages string containing C and C++
    languages_str = "{'Python': 1000, 'C': 500, 'C++': 500}"
    cc_percentage = get_cc_percentage(languages_str)
    assert cc_percentage == 50.0

    # Test with a valid languages string containing only C
    languages_str = "{'Python': 1000, 'C': 500}"
    cc_percentage = get_cc_percentage(languages_str)
    assert cc_percentage == 33.33333333333333

    # Test with a valid languages string containing only C++
    languages_str = "{'Python': 1000, 'C++': 500}"
    cc_percentage = get_cc_percentage(languages_str)
    assert cc_percentage == 33.33333333333333

    # Test with a valid languages string containing neither C nor C++
    languages_str = "{'Python': 1000, 'Java': 500}"
    cc_percentage = get_cc_percentage(languages_str)
    assert cc_percentage == 0.0

    # Test with an empty languages string
    cc_percentage = get_cc_percentage("")
    assert cc_percentage == 0.0


def test_count_modules_per_project(basic_dataset: Dataset):
    """Test the count_modules_per_project function."""
    # Test the function
    modules_count = count_modules_per_project(basic_dataset)
    assert modules_count == {"repo1": 2, "repo2": 1}


def test_get_project_stats(basic_dataset: Dataset, flapy_projects: list[FlaPyProject]):
    """Test the get_project_stats function."""
    # Test the function
    stats = get_project_stats(basic_dataset, flapy_projects)
    assert len(stats) == 2
    assert stats[0]["project_name"] == "repo1"
    assert stats[0]["modules_count"] == 2
    assert stats[0]["version_tag"] == "1.0.0"
    assert stats[0]["cc_percentage"] == 50.0
    assert stats[1]["project_name"] == "repo2"
    assert stats[1]["modules_count"] == 1
    assert stats[1]["version_tag"] == "2.0.0"
    assert stats[1]["cc_percentage"] == 0.0


def test_print_table(stats_data: list[dict[str, Any]]):
    """Test the print_table function."""
    # Test the function
    table = print_table(stats_data)
    assert isinstance(table, Table)
    assert table.title == "Dataset Statistics"
    assert len(table.columns) == 6
    assert table.columns[0].header == "Project Name"
    assert table.columns[1].header == "Modules Count"
    assert table.columns[2].header == "Version/Tag"
    assert table.columns[3].header == "Python MB"
    assert table.columns[4].header == "C/C++ MB"
    assert table.columns[5].header == "C/C++ Percentage"


def test_export_to_latex(stats_data: list[dict[str, Any]], tmp_path: Path):
    """Test the export_to_latex function."""
    # Create a temporary file
    tmp_file = tmp_path / "test.tex"

    # Test the function
    export_to_latex(stats_data, tmp_file)

    # Read the file content
    content = tmp_file.read_text(encoding="utf-8")

    # Check the content
    assert content


def test_filter_dataset_with_xml(extended_dataset: Dataset, xml_file: Path):
    """Test filtering the dataset with an XML file."""
    # Read the XML file
    xml_projects = read_xml(xml_file)

    # Filter the dataset using the filter_dataset_with_xml function
    filtered_dataset = filter_dataset_with_xml(extended_dataset, xml_projects)

    # Verify the filtered dataset
    assert len(filtered_dataset.repositories) == 2
    assert filtered_dataset.repositories[0].name == "repo1"
    assert filtered_dataset.repositories[1].name == "repo3"
    assert "repo2" not in [repo.name for repo in filtered_dataset.repositories]

    # Verify that only the modules in the XML are included
    repo1_modules = [module.name for module in filtered_dataset.repositories[0].modules]
    assert "module1" in repo1_modules
    assert "module2" in repo1_modules
    assert "module3" not in repo1_modules  # This module should be filtered out
    assert len(repo1_modules) == 2

    repo3_modules = [module.name for module in filtered_dataset.repositories[1].modules]
    assert "module5" in repo3_modules
    assert "module6" not in repo3_modules  # This module should be filtered out
    assert len(repo3_modules) == 1
