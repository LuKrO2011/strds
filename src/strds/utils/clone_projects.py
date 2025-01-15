import shutil
from dataclasses import dataclass
from pathlib import Path

import click
import git
from rich.console import Console

from strds.utils.flapy_csv_utils import FlaPyProject, parse_csv

CONSOLE = Console()


@dataclass
class LocalProject:
    project: FlaPyProject
    path: Path
    git_commit_hash: str


def get_target_path(output_path: Path, project: FlaPyProject) -> Path:
    """Get the target path for a project.

    Args:
        output_path: The output path.
        project: The project.

    Returns:
        The target path.
    """
    return output_path.joinpath(project.project_name)


def clone_repository(
    repo_url: str,
    version: str,
    target: Path,
    *,
    flapy_style: bool = False,
    overwrite: bool = False,
) -> None:
    """Clone a repository and checkout a specific version.

    Args:
        repo_url: The URL of the repository.
        version: The version to checkout.
        target: The target directory to clone the repository to.
        flapy_style: Whether to use flapy style for checking out versions.
        overwrite: Whether to overwrite the target directory if it exists.
    """
    if target.exists():
        if overwrite:
            CONSOLE.print(f"[yellow]Overwriting existing directory {target}[/]")
            shutil.rmtree(target)
            repo = git.Repo.clone_from(url=repo_url, to_path=target)
        else:
            CONSOLE.print(
                f"Directory {target} exists. Skipping cloning/checkout of {repo_url}."
            )
            return
    else:
        CONSOLE.print(f"Cloning {repo_url} to {target}")
        repo = git.Repo.clone_from(url=repo_url, to_path=target)

    if flapy_style:
        __checkout_flapy_style(repo, version)
    else:
        __checkout(repo, version)


def __checkout(repo: git.Repo, version: str, *, hard: bool = False) -> None:
    """Checkout a specific version in a repository.

    Args:
        repo: The repository to checkout the version in.
        version: The version to checkout.
        hard: Whether to do a hard reset instead of a checkout.
    """
    checkout_variants = [
        version,
        f"v{version}",
        f"tags/{version}",
        f"tags/v{version}",
        f"origin/{version}",
        f"origin/v{version}",
    ]

    for variant in checkout_variants:
        try:
            if hard:
                repo.git.reset("--hard", variant)
            else:
                repo.git.checkout(variant)
            CONSOLE.print(f"Successfully checked out {variant}")
            return
        except git.GitCommandError:
            pass

    CONSOLE.print(f"Could not checkout version {version}; using default branch.")


def __checkout_flapy_style(repo: git.Repo, version: str) -> None:
    """Checkout a specific version in a repository in the flapy style.

    Flapy uses 'git reset --hard version'.

    Args:
        repo: The repository to checkout the version in.
        version: The version to checkout.
    """
    try:
        repo.git.reset("--hard", version)
        CONSOLE.print(f"Successfully checked out {version}")
        return
    except git.GitCommandError:
        pass

    CONSOLE.print(f"Could not checkout version {version}; using default branch.")


def clone_projects(
    csv_file: Path,
    output_path: Path,
    flapy_style: bool = False,
    overwrite: bool = False,
) -> list[LocalProject]:
    """Clone projects from a CSV file."""
    projects = parse_csv(csv_file)
    local_projects = []
    output_path.mkdir(parents=True, exist_ok=True)
    for project in projects:
        target_path = get_target_path(output_path, project)
        try:
            clone_repository(
                project.github_url,
                project.matching_github_tag or project.pypi_latest_tag or "master",
                target_path,
                flapy_style=flapy_style,
                overwrite=overwrite,
            )
            commit_hash = git.Repo(target_path).head.commit.hexsha
            local_projects.append(
                LocalProject(
                    project=project, path=target_path, git_commit_hash=commit_hash
                )
            )
        except (ValueError, git.GitCommandError) as e:
            CONSOLE.print(e)

    return local_projects


@click.command()
@click.option(
    "--csv-file",
    help="The path to the CSV file containing the project definitions.",
    metavar="<csv>",
    required=True,
    type=click.Path(exists=True, dir_okay=False, resolve_path=True, path_type=Path),
)
@click.option(
    "--output-path",
    help="The path where projects should be cloned to.",
    metavar="<output>",
    required=True,
    type=click.Path(file_okay=False, dir_okay=True, resolve_path=True, path_type=Path),
)
@click.option(
    "--flapy-style",
    help="Use flapy style for checking out versions.",
    is_flag=True,
    default=False,
)
@click.option(
    "--overwrite",
    help="Overwrite existing project directories if they already exist.",
    is_flag=True,
    default=False,
)
def cli(
    csv_file: Path, output_path: Path, *, flapy_style: bool, overwrite: bool
) -> None:
    """Clone projects from a CSV file and validate the presence of module files.

    Args:
        csv_file: The path to the CSV file.
        output_path: The path to the output directory.
        flapy_style: Whether to use flapy style for checking out versions.
        overwrite: Whether to overwrite existing project directories.
    """
    clone_projects(csv_file, output_path, flapy_style, overwrite)


if __name__ == "__main__":
    cli()
