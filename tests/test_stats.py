"""Tests for the stats module."""

import tempfile
from pathlib import Path

from rich.table import Table

from strds.stats import (
    count_modules_per_project,
    export_to_latex,
    get_cc_percentage,
    get_language_percentages,
    get_project_stats,
    print_table,
)
from strds.utils.flapy_csv_utils import FlaPyProject
from strds.utils.structure import Dataset, Module, Repository


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


def test_count_modules_per_project():
    """Test the count_modules_per_project function."""
    # Create a test dataset
    repo1 = Repository(
        name="repo1",
        url="https://github.com/user/repo1",
        pypi_tag="1.0.0",
        git_commit_hash="abc123",
        modules=[
            Module(name="module1", file_path=Path("module1.py")),
            Module(name="module2", file_path=Path("module2.py")),
        ],
    )
    repo2 = Repository(
        name="repo2",
        url="https://github.com/user/repo2",
        pypi_tag="2.0.0",
        git_commit_hash="def456",
        modules=[
            Module(name="module3", file_path=Path("module3.py")),
        ],
    )
    dataset = Dataset(repositories=[repo1, repo2])

    # Test the function
    modules_count = count_modules_per_project(dataset)
    assert modules_count == {"repo1": 2, "repo2": 1}


def test_get_project_stats():
    """Test the get_project_stats function."""
    # Create a test dataset
    repo1 = Repository(
        name="repo1",
        url="https://github.com/user/repo1",
        pypi_tag="1.0.0",
        git_commit_hash="abc123",
        modules=[
            Module(name="module1", file_path=Path("module1.py")),
            Module(name="module2", file_path=Path("module2.py")),
        ],
    )
    repo2 = Repository(
        name="repo2",
        url="https://github.com/user/repo2",
        pypi_tag="2.0.0",
        git_commit_hash="def456",
        modules=[
            Module(name="module3", file_path=Path("module3.py")),
        ],
    )
    dataset = Dataset(repositories=[repo1, repo2])

    # Create test projects
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
    projects = [project1, project2]

    # Test the function
    stats = get_project_stats(dataset, projects)
    assert len(stats) == 2
    assert stats[0]["project_name"] == "repo1"
    assert stats[0]["modules_count"] == 2
    assert stats[0]["version_tag"] == "1.0.0"
    assert stats[0]["cc_percentage"] == 50.0
    assert stats[1]["project_name"] == "repo2"
    assert stats[1]["modules_count"] == 1
    assert stats[1]["version_tag"] == "2.0.0"
    assert stats[1]["cc_percentage"] == 0.0


def test_print_table():
    """Test the print_table function."""
    # Create test stats
    stats = [
        {
            "project_name": "repo1",
            "modules_count": 2,
            "version_tag": "1.0.0",
            "cc_percentage": 50.0,
        },
        {
            "project_name": "repo2",
            "modules_count": 1,
            "version_tag": "2.0.0",
            "cc_percentage": 0.0,
        },
    ]

    # Test the function
    table = print_table(stats)
    assert isinstance(table, Table)
    assert table.title == "Dataset Statistics"
    assert len(table.columns) == 4
    assert table.columns[0].header == "Project Name"
    assert table.columns[1].header == "Modules Count"
    assert table.columns[2].header == "Version/Tag"
    assert table.columns[3].header == "C/C++ Percentage"


def test_export_to_latex():
    """Test the export_to_latex function."""
    # Create test stats
    stats = [
        {
            "project_name": "repo1",
            "modules_count": 2,
            "version_tag": "1.0.0",
            "cc_percentage": 50.0,
        },
        {
            "project_name": "repo2",
            "modules_count": 1,
            "version_tag": "2.0.0",
            "cc_percentage": 0.0,
        },
    ]

    # Create a temporary file
    with tempfile.NamedTemporaryFile(suffix=".tex") as tmp_file:
        tmp_path = Path(tmp_file.name)

        # Test the function
        export_to_latex(stats, tmp_path)

        # Read the file content
        content = tmp_path.read_text(encoding="utf-8")

        # Check the content
        assert r"\begin{table}[h]" in content
        assert r"\centering" in content
        assert r"\begin{tabular}{|l|r|l|r|}" in content
        assert r"\hline" in content
        assert r"\textbf{Project} & \textbf{Modules} & \textbf{Version} & \textbf{C/C++}" in content
        assert "repo1 & 2 & 1.0.0 & 50.00\\%" in content
        assert "repo2 & 1 & 2.0.0 & 0.00\\%" in content
        assert r"\end{tabular}" in content
        assert r"\caption{Dataset Statistics}" in content
        assert r"\label{tab:dataset_stats}" in content
        assert r"\end{table}" in content
