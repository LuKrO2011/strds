"""Mine PyPI + GitHub projects."""

import logging
import operator
import os
import random
import re
import shlex
import shutil
import subprocess  # noqa: S404
import sys
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import click
import pandas as pd
import requests
from bs4 import BeautifulSoup
from rich.console import Console
from rich.logging import RichHandler
from tqdm import tqdm

GITHUB_URL_REGEX = r"https?://(www\.)?github\.com/[^/]+/[^/]+/?$"
MAX_RETRIES = 10
PARALLEL_REQUESTS = 10
TIMEOUT = 60 * 60  # 1 hour
HTTP_ERROR_STATUS_CODE = 400
HTTP_SUCCESS_STATUS_CODE = 200

# Setup the rich console and logger
console = Console()
logging.basicConfig(
    level=logging.INFO, format="%(message)s", handlers=[RichHandler(console=console)]
)

# Try to get token from env or file
token = os.getenv("GITHUB_TOKEN")
if not token:
    try:
        token = Path(".github_token").read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        console.log("[yellow]No GitHub token found. Please set GITHUB_TOKEN or create a "
                    ".github_token file.[/yellow]")

session = requests.Session()
session.mount("", requests.adapters.HTTPAdapter(max_retries=MAX_RETRIES))
if token:
    session.headers.update({
        "Authorization": f"Bearer {token}"
    })


def get_git_path() -> str:
    """Get the path to the git executable.

    Returns:
        The path to the git executable
    """
    git_path = shutil.which("git")
    if git_path is None:
        console.log("[red]Git not found in PATH[/red]")
        sys.exit(1)
    return git_path


def try_default(
    function: Callable[[], Any],
    exception: type[Exception] = Exception,
    error_return_val: Any = None,
    log_error_info: str | None = None,
    finally_: Callable[[], Any] | None = None,
) -> Any:
    """Helper function. Try-except is not allowed in lambdas.

    function: the function that shall be called. It must not have input parameters ->
    curry them first
    exception: type (class) of exception, that should be caught
    error_return_val: either a function that shall be called
    """
    try:
        if (
            isinstance(error_return_val, str)
            and error_return_val == "ERROR_MESSAGE_TUPLE"
        ):
            return "ok", function()
        return function()
    except exception as caught_exception:  # pylint: disable=broad-except
        if log_error_info is not None:
            console.log(
                f"[red]{type(caught_exception).__name__}: {caught_exception}[/red] | "
                f"{log_error_info}"
            )
        if callable(error_return_val):
            return error_return_val(caught_exception)
        if isinstance(error_return_val, str) and error_return_val == "ERROR_MESSAGE":
            return f"{type(caught_exception).__name__}: {caught_exception}"
        if (
            isinstance(error_return_val, str)
            and error_return_val == "ERROR_MESSAGE_TUPLE"
        ):
            return "error", f"{type(caught_exception).__name__}: {caught_exception}"
        return error_return_val
    finally:
        if finally_:
            finally_()


def fetch_all_pypi_projects() -> list[str]:
    """Fetch all PyPI projects.

    Returns:
        A list of PyPI projects
    """
    console.log("[bold green]Fetching all PyPI projects...[/bold green]")
    response = requests.get("https://pypi.org/simple/", timeout=TIMEOUT).text

    console.log("[bold green]Parsing PyPI projects...[/bold green]")
    soup = BeautifulSoup(response, "html.parser")
    # Use Tag type to ensure find_all is available
    return [a.text for a in soup.find_all("a")]


def fetch_top_pypi_packages(top_n: int = 100) -> list[str]:
    """Fetch top PyPI packages from hugovk.github.io/top-pypi-packages/.

    Args:
        top_n: Number of top packages to fetch. Default is 100.

    Returns:
        A list of top PyPI package names
    """
    console.log("[bold green]Fetching top PyPI packages...[/bold green]")
    url = "https://hugovk.github.io/top-pypi-packages/top-pypi-packages.min.json"
    response = requests.get(url, timeout=TIMEOUT).json()

    console.log("[bold green]Parsing top PyPI packages...[/bold green]")
    packages: list[str] = []

    # Extract package names from the JSON response
    if "rows" in response:
        packages.extend(
            row["project"] for row in response["rows"][:top_n] if "project" in row
        )

    console.log(f"[bold green]Found {len(packages)} top PyPI packages[/bold green]")
    return packages


def _get_pypi_metadata(project_name: str) -> tuple[str, int, Any]:
    """Get metadata for a PyPI project.

    Args:
        project_name: The name of the PyPI project

    Returns:
        A tuple containing the status of the fetch, the HTTP response code, and the data
    """
    try:
        response = requests.get(
            url=f"https://pypi.python.org/pypi/{project_name}/json",
            stream=True,
            timeout=TIMEOUT,
        )
        http_response_code = response.status_code
    except Exception as ex:  # noqa: BLE001
        return "fetching failed", HTTP_SUCCESS_STATUS_CODE, type(ex)
    try:
        data = response.json()
    except Exception as ex:  # noqa: BLE001
        return "parsing failed", http_response_code, type(ex)
    return "successful", http_response_code, data


def _get_latest_pypi_tag(pypi_json: dict[str, Any]) -> str:
    """Get the latest PyPI tag from the JSON data.

    Args:
        pypi_json: The JSON data from PyPI

    Returns:
        The latest PyPI tag
    """
    try:
        releases = pypi_json["releases"]
    except Exception as exc:
        raise ValueError("data does not contain releases") from exc

    def get_upload_time(release: list[dict[str, Any]]) -> str | None:
        try:
            return str(release[0]["upload_time"])
        except Exception:  # noqa: BLE001
            return None

    releases = [(r_k, get_upload_time(r_v)) for r_k, r_v in releases.items()]

    releases = [
        (release_tag, release_date)
        for release_tag, release_date in releases
        if release_date is not None
    ]
    if len(releases) == 0:
        raise ValueError("release list is empty")
    return str(max(releases, key=operator.itemgetter(1))[0])


def _is_valid_github_url(github_url: str) -> bool:
    """Check if a GitHub URL is valid.

    Args:
        github_url: The GitHub URL to check

    Returns:
        True if the URL is valid, False otherwise
    """
    return re.match(GITHUB_URL_REGEX, github_url) is not None


def _extract_github_owner_repo(github_url: str) -> tuple[str, str]:
    """Extract the owner and repository name from a GitHub URL.

    Args:
        github_url: The GitHub URL

    Returns:
        A tuple containing the owner and repository name
    """
    # Remove trailing slash if present
    github_url = github_url.removesuffix("/")

    # Extract owner and repo from URL
    parts = github_url.split("/")
    owner = parts[-2]
    repo = parts[-1]

    return owner, repo


def _fetch_github_languages(github_url: str) -> dict[str, int]:
    """Fetch the languages used in a GitHub repository.

    Args:
        github_url: The GitHub URL

    Returns:
        A dictionary mapping language names to bytes of code
    """
    if not github_url or not _is_valid_github_url(github_url):
        return {}

    try:
        owner, repo = _extract_github_owner_repo(github_url)
        api_url = f"https://api.github.com/repos/{owner}/{repo}/languages"
        response = session.get(api_url, timeout=TIMEOUT)

        if response.status_code == 200:
            # Cast the response to the expected type
            return dict(response.json())
        console.log(
            f"[yellow]Failed to fetch languages for {github_url}: {response.status_code}[/yellow]"
        )
        return {}
    except Exception as e:  # noqa: BLE001
        console.log(f"[red]Error fetching languages for {github_url}: {e}[/red]")
        return {}


def _get_git_tags(url: str) -> list[str]:
    """Get the git tags for a given URL.

    Args:
        url: The URL to get the git tags from

    Returns:
        A list of git tags
    """
    # add pseudo credentials to avoid prompt
    search_url: str = url[:8] + "pseudocredentials:pseudocredentials@" + url[8:]

    # obtain tags, if not found return empty set
    try:
        git_path = get_git_path()
        search_url = shlex.quote(search_url)
        result = subprocess.run(  # noqa: S603
            [git_path, "ls-remote", "--tags", search_url],
            capture_output=True,
            text=True,
            check=True,
        )

        data: str = result.stdout
    except subprocess.CalledProcessError:
        return []

    # parse git tags
    new_data: list[str] = data.split("\\n")
    tags: set[str] = set()
    for line in new_data:
        git_tag = re.search(r"tags/.*[0-9]+", line)
        if git_tag:
            tag_str = git_tag.group(0).split("/")[1]
            tags.add(tag_str)
    return sorted(tags)


def _match_pypi_git_tag(pypi_version: str, git_tags: list[str]) -> str:
    """Match the PyPI version with the git tags.

    Args:
        pypi_version: The PyPI version
        git_tags: The git tags

    Returns:
        The matching git tag
    """
    for git_tag in git_tags:
        regex = "v*" + pypi_version
        if re.match(regex, git_tag):
            return git_tag
    return ""


def resolve_url(url: str, max_retries: int = 10, sleep_time: int = 11) -> tuple[str, int]:
    """Resolve a URL and follow redirects.

    Args:
        url: The URL to resolve
        max_retries: The maximum number of retries
        sleep_time: The time to sleep between retries

    Returns:
        The resolved URL and the HTTP status code
    """
    num_retries = 0
    try:
        response = session.get(url)
        while response.status_code == 429 and num_retries < max_retries:
            num_retries += 1
            console.log(f"[yellow]Sleeping for {sleep_time} seconds...[/yellow]")
            time.sleep(sleep_time)
            response = session.get(url)
        if num_retries == max_retries:
            console.log(f"[red]Max retries reached for {url}[/red]")
        return response.url, response.status_code
    except Exception:  # noqa: BLE001
        return "", HTTP_ERROR_STATUS_CODE


def _filter_projects(
    project_details: pd.DataFrame,
    *,
    remove_duplicates: bool,
    remove_no_github_url_found: bool,
    languages: list[str] | None,
    min_language_percentage: float = 0.0,
) -> pd.DataFrame:
    """Filter projects based on various criteria.

    Args:
        project_details: DataFrame containing project details
        remove_duplicates: Whether to remove duplicates
        remove_no_github_url_found: Whether to remove projects with no GitHub URL found
        languages: A list of languages to filter by
        min_language_percentage: Minimum percentage (0.0-1.0) of a language in a project

    Returns:
        Filtered DataFrame
    """
    # 1. Remove cases where no Github URL was found
    if remove_no_github_url_found:
        prev_count = len(project_details)
        project_details = project_details[
            project_details["Github_URL"].notna() & project_details["Github_URL"].astype(bool)
            ]
        new_count = len(project_details)
        num_dropped = prev_count - new_count
        console.log(
            f"[yellow]Dropped {num_dropped} projects where no GitHub URL was found[/yellow]"
        )

    # 2. Drop duplicates (some PyPI projects point to the same GitHub URL)
    if remove_duplicates:
        num_duplicates = project_details.duplicated("Github_URL").sum()
        console.log(
            f"[yellow]Dropped {num_duplicates} duplicated entries (same GitHub URL)["
            f"/yellow]"
        )
        project_details = project_details[
            ~project_details.duplicated("Github_URL")
            | project_details["Github_URL"].isna()
        ]

    # 3. Filter by languages if specified
    if languages:
        # Create a function to check if any of the specified languages
        # are in the project's languages and meet the minimum percentage requirement
        def has_specified_language(project_languages: dict[str, Any] | None) -> bool:
            if not project_languages:
                return False

            # Check if any of the specified languages are in the project
            project_lang_keys = [lang.lower() for lang in project_languages]
            specified_langs_present = any(lang.lower() in project_lang_keys for lang in languages)

            # No specified languages or no minimum percentage is required => return early
            if not specified_langs_present or min_language_percentage <= 0.0:
                return specified_langs_present

            # Calculate the total bytes of code
            total_bytes = sum(project_languages.values())
            if total_bytes == 0:
                return False

            # Calculate the bytes of code for the specified languages
            specified_langs_bytes = sum(
                bytes_count
                for lang, bytes_count in project_languages.items()
                if any(spec_lang.lower() == lang.lower() for spec_lang in languages)
            )

            # Check if the specified languages make up at least the minimum percentage
            percentage = specified_langs_bytes / total_bytes
            return bool(percentage >= min_language_percentage)

        # Apply the filter
        before_count = len(project_details)
        project_details = project_details[
            project_details["github_languages"].apply(has_specified_language)
        ]
        after_count = len(project_details)

        filter_message = (
            f"[yellow]Dropped {before_count - after_count} projects that don't use any "
            f"of the specified languages: {languages}"
        )
        if min_language_percentage > 0.0:
            filter_message += (f" or don't meet the minimum language percentage: "
                               f"{min_language_percentage:.1%}")
        filter_message += "[/yellow]"
        console.log(filter_message)

    console.log(f"[bold green]Remaining projects: {len(project_details)}[/bold green]")

    return project_details


def _fetch_projects(
    sample_size: int | None,
    project_list_file: str | Path | None,
    *,
    use_top_packages: bool,
    random_seed: int | None,
) -> list[str]:
    """Fetch projects from PyPI or a file.

    Args:
        sample_size: The number of projects to sample
        project_list_file: A file containing a list of projects
        use_top_packages: Whether to use top PyPI packages
        random_seed: The random seed

    Returns:
        A list of project names
    """
    if random_seed is not None:
        random.seed(random_seed)

    if use_top_packages:
        if sample_size is None:
            sample_size = 100  # Default to 100 top packages if not specified
        return fetch_top_pypi_packages(top_n=sample_size)
    if project_list_file is None:
        projects = fetch_all_pypi_projects()
        # Only do random sampling if not using top packages
        if sample_size is not None:
            projects = random.sample(projects, sample_size)
        return projects
    # Ensure project_list_file is a Path object
    file_path = Path(project_list_file) if project_list_file is not None else None
    if file_path is not None:
        content = file_path.read_text(encoding="utf-8")
        projects = content.splitlines()
        # Only do random sampling if not using top packages
        if sample_size is not None:
            projects = random.sample(projects, sample_size)
        return projects
    # This should not happen as we've already checked if project_list_file is None
    return []


def sample_pypi_projects(
    *,
    sample_size: int | None = None,
    random_seed: int | None = None,
    project_list_file: str | None = None,
    redirect_github_urls: bool = True,
    remove_duplicates: bool = True,
    remove_no_github_url_found: bool = True,
    use_top_packages: bool = False,
    languages: list[str] | None = None,
    min_language_percentage: float = 0.0,
) -> str:
    """Sample PyPI projects and fetch metadata.

    Args:
        sample_size: The number of projects to sample. If None, all projects are sampled.
                    When use_top_packages is True, this is the number of top packages to fetch.
        random_seed: The random seed.
        project_list_file: A file containing a list of projects
        redirect_github_urls: Whether to redirect GitHub URLs
        remove_duplicates: Whether to remove duplicates
        remove_no_github_url_found: Whether to remove projects with no GitHub URL found
        use_top_packages: Whether to use top PyPI packages from hugovk.github.io/top-pypi-packages/
        languages: A list of languages to filter by. Only projects that use at least one of these
            languages will be included.
        min_language_percentage: Minimum percentage (0.0-1.0) of a language in a project
        to be included. Only projects where the specified languages make up at least
        this percentage of the total lines of code will be included.

    Returns:
        The sampled projects as a CSV string
    """
    console.log(f"[bold green]Sampling {sample_size} PyPI projects...[/bold green]")
    console.log(f"[bold green]Random seed: {random_seed}[/bold green]")
    console.log(f"[bold green]Project list file: {project_list_file}[/bold green]")
    console.log(f"[bold green]Use top packages: {use_top_packages}[/bold green]")
    console.log(
        f"[bold green]Redirect GitHub URLs: {redirect_github_urls}[/bold green]"
    )
    console.log(f"[bold green]Remove duplicates: {remove_duplicates}[/bold green]")
    console.log(
        f"[bold green]Remove projects with no GitHub URL found: "
        f"{remove_no_github_url_found}[/bold green]"
    )
    console.log(
        f"[bold green]Filter by languages: {languages}[/bold green]"
    )
    console.log(
        f"[bold green]Minimum language percentage: {min_language_percentage:.1%}[/bold green]"
    )

    # 1. Fetch projects
    projects = _fetch_projects(
        sample_size=sample_size,
        project_list_file=project_list_file,
        use_top_packages=use_top_packages,
        random_seed=random_seed,
    )

    # 3. Fetch project data
    def fetch_project_data(proj_name: str) -> dict[str, Any]:
        """Fetch data for a project.

        Args:
            proj_name: The project name

        Returns:
            The project data
        """
        fetch_status, http_response_code, pypi_data = _get_pypi_metadata(proj_name)
        pypi_classifiers = try_default(lambda: pypi_data["info"]["classifiers"])
        latest_pypi_tag = try_default(lambda: _get_latest_pypi_tag(pypi_data))
        pypi_project_urls = try_default(lambda: pypi_data["info"]["project_urls"])

        # 5. Search for Github URL (+ redirect + to_lower)
        def to_lowercase(url: str) -> Callable[[], str]:
            def convert_to_lowercase() -> str:
                return url.lower()

            return convert_to_lowercase

        github_url = try_default(
            lambda: next(
                (url for tag, url in pypi_project_urls.items() if ("github" in tag.lower()
                                                                    or
                                                                   "source" in
                                                                   tag.lower())
                                                                   and _is_valid_github_url(url)),
                next(
                    url for _, url in pypi_project_urls.items() if _is_valid_github_url(url)
                )
            )
        )
        github_url = try_default(to_lowercase(github_url))
        if redirect_github_urls:
            github_url, github_url_status = try_default(lambda: resolve_url(github_url))
        else:
            github_url_status = None
        github_url = try_default(to_lowercase(github_url))

        # 6. Fetch git tags
        git_tags: list[str] = try_default(lambda: _get_git_tags(github_url))

        # 7. match PyPI and git tag
        matching_github_tag = try_default(
            lambda: _match_pypi_git_tag(pypi_version=latest_pypi_tag, git_tags=git_tags)
        )

        # 8. Fetch languages used in the repository
        github_languages = try_default(lambda: _fetch_github_languages(github_url))

        return {
            "Project_Name": proj_name,
            "Github_URL": github_url,
            "matching_github_tag": matching_github_tag,
            "PYPI_latest_tag": latest_pypi_tag,
            "funcs_to_trace": "",
            "tests_to_run": "",
            # other columns (ignored by FlaPy)
            "pypi_fetch_status": fetch_status,
            "pypi_http_response_code": http_response_code,
            "PYPI_classifiers": pypi_classifiers,
            "PYPI_project_urls": pypi_project_urls,
            "github_url_status": github_url_status,
            "git_tags": git_tags,
            "github_languages": github_languages,
        }

    if PARALLEL_REQUESTS > 1:
        with ThreadPoolExecutor(max_workers=PARALLEL_REQUESTS) as executor:
            project_details = pd.DataFrame(
                list(
                    tqdm(
                        executor.map(fetch_project_data, projects),
                        total=len(projects),
                        desc="Processing projects (parallel)",
                    )
                )
            )
    else:
        project_details = pd.DataFrame(
            [fetch_project_data(p) for p in tqdm(projects, desc="Processing projects (sequential)")]
        )

    if project_details.empty:
        return ""

    # Apply filters
    project_details = _filter_projects(
        project_details=project_details,
        remove_duplicates=remove_duplicates,
        remove_no_github_url_found=remove_no_github_url_found,
        languages=languages,
        min_language_percentage=min_language_percentage,
    )

    # Ensure the return value is a string
    return str(project_details.to_csv(index=False))


@click.command()
@click.option("--sample-size", type=int, help="Number of projects to sample")
@click.option("--random-seed", type=int, help="Random seed for reproducibility")
@click.option(
    "--project-list-file",
    type=click.Path(exists=True),
    help="Path to project list file",
)
@click.option(
    "--use-top-packages/--no-use-top-packages",
    default=False,
    help="Use top PyPI packages from hugovk.github.io/top-pypi-packages/",
)
@click.option(
    "--redirect-github-urls/--no-redirect-github-urls",
    default=True,
    help="Follow GitHub redirects",
)
@click.option(
    "--remove-duplicates/--keep-duplicates",
    default=True,
    help="Remove duplicate projects",
)
@click.option(
    "--remove-no-github-url-found/--keep-no-github-url-found",
    default=True,
    help="Remove projects without GitHub URLs",
)
@click.option(
    "--csv-output",
    type=click.Path(),
    help="Path to store the CSV output",
    default="output/repos.csv",
)
@click.option(
    "--languages",
    help="Comma-separated list of languages to filter by (e.g., 'C,C++,Python')",
)
@click.option(
    "--min-language-percentage",
    type=float,
    default=0.0,
    help="Minimum percentage (0.0-1.0) of a language in a project to be included",
)
def cli(
    sample_size: int | None,
    random_seed: int | None,
    project_list_file: str | None,
    *,
    use_top_packages: bool,
    redirect_github_urls: bool,
    remove_duplicates: bool,
    remove_no_github_url_found: bool,
    csv_output: str,
    languages: str | None,
    min_language_percentage: float,
) -> None:
    """CLI wrapper for sample_pypi_projects."""
    # Parse languages if provided
    language_list = None
    if languages:
        language_list = [lang.strip() for lang in languages.split(",")]

    csv = sample_pypi_projects(
        sample_size=sample_size,
        random_seed=random_seed,
        project_list_file=project_list_file,
        use_top_packages=use_top_packages,
        redirect_github_urls=redirect_github_urls,
        remove_duplicates=remove_duplicates,
        remove_no_github_url_found=remove_no_github_url_found,
        languages=language_list,
        min_language_percentage=min_language_percentage,
    )

    if not csv:
        console.log("[bold red]No projects found.[/bold red]")
        return

    Path(csv_output).write_text(csv, encoding="utf-8")
    console.log("[bold green]CSV output generated:[/bold green] " + csv_output)


if __name__ == "__main__":
    cli()
