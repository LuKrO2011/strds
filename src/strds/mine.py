"""Mine PyPI + GitHub projects."""
import logging
import operator
import random
import re
import shlex
import shutil
import subprocess  # noqa: S404
import sys
import time
import typing
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
logging.basicConfig(level=logging.INFO, format="%(message)s",
                    handlers=[RichHandler(console=console)])

session = requests.Session()
session.mount("", requests.adapters.HTTPAdapter(max_retries=MAX_RETRIES))


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
        function: Callable,
        exception=Exception,
        error_return_val=None,
        log_error_info=None,
        finally_: Callable[[], Any] | None = None,
):
    """Helper function. Try-except is not allowed in lambdas.

    function: the function that shall be called. It must not have input parameters ->
    curry them first
    exception: type (class) of exception, that should be caught
    error_return_val: either a function that shall be called
    """
    try:
        if isinstance(error_return_val,
                      str) and error_return_val == "ERROR_MESSAGE_TUPLE":
            return "ok", function()
        return function()
    except exception as caught_exception:  # pylint: disable=broad-except
        if log_error_info is not None:
            console.log(
                f"[red]{type(caught_exception).__name__}: {caught_exception}[/red] | "
                f"{log_error_info}")
        if callable(error_return_val):
            return error_return_val(caught_exception)
        if isinstance(error_return_val, str) and error_return_val == "ERROR_MESSAGE":
            return f"{type(caught_exception).__name__}: {caught_exception}"
        if isinstance(error_return_val,
                      str) and error_return_val == "ERROR_MESSAGE_TUPLE":
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
    return [a.text for a in BeautifulSoup(response, "html.parser").find_all("a")]


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


def _get_latest_pypi_tag(pypi_json: dict) -> str:
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

    def get_upload_time(release: dict) -> str | None:
        try:
            return release[0]["upload_time"]
        except Exception:  # noqa: BLE001
            return None

    releases = [
        (r_k, get_upload_time(r_v))
        for r_k, r_v in releases.items()
    ]

    releases = [
        (release_tag, release_date)
        for release_tag, release_date in releases
        if release_date is not None
    ]
    if len(releases) == 0:
        raise ValueError("release list is empty")
    return max(releases, key=operator.itemgetter(1))[0]


def _is_valid_github_url(github_url: str) -> bool:
    """Check if a GitHub URL is valid.

    Args:
        github_url: The GitHub URL to check

    Returns:
        True if the URL is valid, False otherwise
    """
    return re.match(GITHUB_URL_REGEX, github_url) is not None


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
            check=True
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


def _match_pypi_git_tag(pypi_version, git_tags) -> str:
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


def resolve_url(url: str, max_retries=10, sleep_time=11) -> tuple[str, int]:
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


def sample_pypi_projects(
        *,
        sample_size: int | None = None,
        random_seed: int | None = None,
        project_list_file=None,
        redirect_github_urls: bool = True,
        remove_duplicates: bool = True,
        remove_no_github_url_found: bool = True,
) -> str:
    """Sample PyPI projects and fetch metadata.

    Args:
        sample_size: The number of projects to sample. If None, all projects are sampled.
        random_seed: The random seed.
        project_list_file: A file containing a list of projects
        redirect_github_urls: Whether to redirect GitHub URLs
        remove_duplicates: Whether to remove duplicates
        remove_no_github_url_found: Whether to remove projects with no GitHub URL found

    Returns:
        The sampled projects as a CSV string
    """
    if random_seed is not None:
        random.seed(random_seed)

    console.log(f"[bold green]Sampling {sample_size} PyPI projects...[/bold green]")
    console.log(f"[bold green]Random seed: {random_seed}[/bold green]")
    console.log(f"[bold green]Project list file: {project_list_file}[/bold green]")
    console.log(f"[bold green]Redirect GitHub URLs: {redirect_github_urls}[/bold green]")
    console.log(f"[bold green]Remove duplicates: {remove_duplicates}[/bold green]")
    console.log(
        f"[bold green]Remove projects with no GitHub URL found: "
        f"{remove_no_github_url_found}[/bold green]")

    # 1. Fetch projects
    if project_list_file is None:
        projects = fetch_all_pypi_projects()
    else:
        with Path(project_list_file).read_text(encoding="utf-8") as file:
            projects = file.read().splitlines()

    # 2. Random sampling
    if sample_size is not None:
        projects = random.sample(projects, sample_size)

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
        def to_lowercase(url: str) -> typing.Callable[[], str]:
            def convert_to_lowercase():
                return url.lower()

            return convert_to_lowercase

        github_url = try_default(
            lambda: next(
                url for _, url in pypi_project_urls.items() if _is_valid_github_url(url))
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
        }

    # Wrap the ThreadPoolExecutor in a tqdm progress bar
    with ThreadPoolExecutor(max_workers=10) as executor:
        project_details = pd.DataFrame(list(
            tqdm(executor.map(fetch_project_data, projects), total=len(projects),
                 desc="Processing projects")))

    # 8. Drop duplicates (some PyPI projects point to the same GitHub URL)
    if remove_duplicates:
        num_duplicates = project_details.duplicated("Github_URL").sum()
        console.log(
            f"[yellow]Dropped {num_duplicates} duplicated entries (same GitHub URL)["
            f"/yellow]")
        project_details = project_details[
            ~project_details.duplicated("Github_URL") | project_details[
                "Github_URL"].isna()]

    # 9. Remove cases where no Github URL was found
    if remove_no_github_url_found:
        num_no_github_url_found = project_details["Github_URL"].isna().sum()
        console.log(
            f"[yellow]Dropped {num_no_github_url_found} projects where no GitHub URL "
            f"was found[/yellow]")
        project_details = project_details[~project_details["Github_URL"].isna()]

    return project_details.to_csv(index=False)


@click.command()
@click.option("--sample-size", type=int, help="Number of projects to sample")
@click.option("--random-seed", type=int, help="Random seed for reproducibility")
@click.option("--project-list-file", type=click.Path(exists=True),
              help="Path to project list file")
@click.option("--redirect-github-urls/--no-redirect-github-urls", default=True,
              help="Follow GitHub redirects")
@click.option("--remove-duplicates/--keep-duplicates", default=True,
              help="Remove duplicate projects")
@click.option("--remove-no-github-url-found/--keep-no-github-url-found", default=True,
              help="Remove projects without GitHub URLs")
@click.option("--csv-output", type=click.Path(), help="Path to store the CSV output",
              default="output/repos.csv")
def cli(sample_size, random_seed, project_list_file,  # noqa: PLR0917
        redirect_github_urls, remove_duplicates, remove_no_github_url_found, csv_output):
    """CLI wrapper for sample_pypi_projects."""
    csv = sample_pypi_projects(
        sample_size=sample_size,
        random_seed=random_seed,
        project_list_file=project_list_file,
        redirect_github_urls=redirect_github_urls,
        remove_duplicates=remove_duplicates,
        remove_no_github_url_found=remove_no_github_url_found,
    )
    console.log("[bold green]CSV output generated:[/bold green] " + csv_output)
    Path(csv_output).write_text(csv, encoding="utf-8")


if __name__ == "__main__":
    cli()
