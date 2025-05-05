from unittest.mock import MagicMock, patch

from strds.mine import fetch_top_pypi_packages, sample_pypi_projects


def test_sample_pypi_projects():
    csv = sample_pypi_projects(
        sample_size=1,
        random_seed=42,
        project_list_file=None,
        redirect_github_urls=True,
        remove_duplicates=False,
        remove_no_github_url_found=True,
    )
    assert csv


def test_fetch_top_pypi_packages():
    # Create a mock JSON response with package data
    mock_json = {
        "rows": [
            {"project": "package1", "download_count": 1000000},
            {"project": "package2", "download_count": 900000},
            {"project": "package3", "download_count": 800000},
        ]
    }

    # Create a mock response object
    mock_response = MagicMock()
    mock_response.json.return_value = mock_json

    # Patch the requests.get function to return our mock response
    with patch("requests.get", return_value=mock_response):
        # Call the function with a limit of 2 packages
        result = fetch_top_pypi_packages(top_n=2)

        # Verify the result
        assert len(result) == 2
        assert result[0] == "package1"
        assert result[1] == "package2"


def test_sample_pypi_projects_with_top_packages():
    # Mock the fetch_top_pypi_packages function to return a predefined list
    mock_packages = ["package1", "package2", "package3"]

    with patch("strds.mine.fetch_top_pypi_packages", return_value=mock_packages):
        # Call sample_pypi_projects with use_top_packages=True
        csv = sample_pypi_projects(
            sample_size=3,  # This now determines the number of top packages to fetch
            random_seed=42,
            use_top_packages=True,
            redirect_github_urls=False,  # Avoid actual network calls
            remove_duplicates=False,
            remove_no_github_url_found=False,
        )

        # Verify that we got a CSV string back
        assert csv
        # We can't easily verify the exact content because it depends on PyPI metadata
        # But we can check that it's a non-empty string
        assert isinstance(csv, str)
        assert len(csv) > 0


def test_sample_pypi_projects_with_language_filter():
    """Test that sample_pypi_projects correctly filters projects by language."""
    # Mock packages to use
    mock_packages = ["python_package", "cpp_package", "js_package", "mixed_package"]

    # Define language data for each package
    language_data = {
        "https://github.com/user/python_package": {"Python": 100000},
        "https://github.com/user/cpp_package": {"C++": 50000, "C": 20000},
        "https://github.com/user/js_package": {"JavaScript": 80000, "HTML": 10000},
        "https://github.com/user/mixed_package": {
            "Python": 40000,
            "C++": 30000,
            "JavaScript": 20000,
        },
    }

    # Mock function to return predefined language data based on URL
    def mock_fetch_github_languages(url):
        return language_data.get(url, {})

    # Mock function to return predefined GitHub URLs for packages
    def mock_get_pypi_metadata(project_name):
        return (
            "successful",
            200,
            {
                "info": {
                    "project_urls": {
                        "Source": f"https://github.com/user/{project_name}"
                    },
                    "classifiers": [],
                },
                "releases": {"1.0.0": [{"upload_time": "2023-01-01"}]},
            },
        )

    # Apply mocks
    with (
        patch("strds.mine.fetch_all_pypi_projects", return_value=mock_packages),
        patch(
            "strds.mine._fetch_github_languages",
            side_effect=mock_fetch_github_languages,
        ),
        patch("strds.mine._get_pypi_metadata", side_effect=mock_get_pypi_metadata),
        patch("strds.mine.resolve_url", return_value=("", 200)),
        patch("strds.mine._get_git_tags", return_value=[]),
    ):

        # Test filtering for C/C++ languages
        csv_cpp = sample_pypi_projects(
            sample_size=None,  # Use all mock packages
            random_seed=42,
            redirect_github_urls=False,  # Avoid actual network calls
            remove_duplicates=False,
            remove_no_github_url_found=False,
            languages=["C", "C++"],
        )

        # The result should include cpp_package and mixed_package (2 packages)
        assert csv_cpp
        assert isinstance(csv_cpp, str)
        # Count occurrences of package names in the CSV
        assert csv_cpp.count("cpp_package") > 0
        assert csv_cpp.count("mixed_package") > 0
        assert csv_cpp.count("python_package") == 0
        assert csv_cpp.count("js_package") == 0

        # Test filtering for Python language
        csv_python = sample_pypi_projects(
            sample_size=None,
            random_seed=42,
            redirect_github_urls=False,
            remove_duplicates=False,
            remove_no_github_url_found=False,
            languages=["Python"],
        )

        # The result should include python_package and mixed_package (2 packages)
        assert csv_python
        assert isinstance(csv_python, str)
        assert csv_python.count("python_package") > 0
        assert csv_python.count("mixed_package") > 0
        assert csv_python.count("cpp_package") == 0
        assert csv_python.count("js_package") == 0

        # Test filtering with minimum language percentage
        csv_python_min_percentage = sample_pypi_projects(
            sample_size=None,
            random_seed=42,
            redirect_github_urls=False,
            remove_duplicates=False,
            remove_no_github_url_found=False,
            languages=["Python"],
            min_language_percentage=0.5,  # 50%
        )

        # The result should include only python_package (Python is 100% of the code)
        # but not mixed_package (Python is only 40000/90000 = 44.4% of the code)
        assert csv_python_min_percentage
        assert isinstance(csv_python_min_percentage, str)
        assert csv_python_min_percentage.count("python_package") > 0
        assert csv_python_min_percentage.count("mixed_package") == 0
        assert csv_python_min_percentage.count("cpp_package") == 0
        assert csv_python_min_percentage.count("js_package") == 0

        # Test filtering with C++ and a lower minimum percentage
        csv_cpp_min_percentage = sample_pypi_projects(
            sample_size=None,
            random_seed=42,
            redirect_github_urls=False,
            remove_duplicates=False,
            remove_no_github_url_found=False,
            languages=["C++"],
            min_language_percentage=0.3,  # 30%
        )

        # The result should include both cpp_package (C++ is 50000/70000 = 71.4% of the code)
        # and mixed_package (C++ is 30000/90000 = 33.3% of the code)
        assert csv_cpp_min_percentage
        assert isinstance(csv_cpp_min_percentage, str)
        assert csv_cpp_min_percentage.count("cpp_package") > 0
        assert csv_cpp_min_percentage.count("mixed_package") > 0
        assert csv_cpp_min_percentage.count("python_package") == 0
        assert csv_cpp_min_percentage.count("js_package") == 0
