"""Providing parts of the dataset as specified by the user."""

from pathlib import Path

import click
import libcst as cst
from rich.console import Console

from strds.utils.pynguin_xml import create_pynguin_xmls
from strds.utils.structure import (
    Class,
    Dataset,
    Function,
    Method,
    Module,
    Repository,
    clone,
    load_from_json_file,
)

console = Console()


def remove_type_annotations(code: str) -> str:
    """Removes type annotations from a code snippet using libcst."""

    class RemoveAnnotationsTransformer(cst.CSTTransformer):
        """A transformer to remove type annotations from a code snippet."""

        def leave_AnnAssign(
                self, original_node: cst.AnnAssign, updated_node: cst.AnnAssign
        ) -> cst.BaseSmallStatement:
            return updated_node.with_changes(annotation=None)

        def leave_Param(
                self, original_node: cst.Param, updated_node: cst.Param
        ) -> cst.Param:
            return updated_node.with_changes(annotation=None)

        def leave_FunctionDef(
                self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
        ) -> cst.FunctionDef:
            return updated_node.with_changes(returns=None)

    try:
        tree = cst.parse_module(code)
        modified_tree = tree.visit(RemoveAnnotationsTransformer())
        return modified_tree.code
    except Exception as e:  # pylint: disable=broad-exception-caught
        console.print(f"[red]Failed to remove type annotations: {e}[/red]")
        return code


def extract_callables(
        dataset: Dataset, output_dir: Path, without_type_annotations: bool
) -> None:
    """Extract and store the methods from the repositories."""
    for repo in dataset.repositories:
        for module in repo.modules:
            for cls in module.classes:
                for method in cls.methods:
                    code = method.body
                    file_path = method_path(repo, module, cls, method)
                    save_callable(code, output_dir, file_path, without_type_annotations)

            for function in module.functions:
                code = function.body
                file_path = function_path(repo, module, function)
                save_callable(code, output_dir, file_path, without_type_annotations)


def method_path(repo: Repository, module: Module, cls: Class, method: Method) -> Path:
    """Creates a path for a method."""
    return Path(f"{repo.name}/{module.name}/{cls.name}/{method.name}.py")


def function_path(repo: Repository, module: Module, function: Function) -> Path:
    """Creates a path for a function."""
    return Path(f"{repo.name}/{module.name}/{function.name}.py")


def save_callable(
        code: str, output_dir: Path, file_path: Path, without_type_annotations: bool
) -> None:
    """Saves a callable to a file."""
    if without_type_annotations:
        code = remove_type_annotations(code)
    output_file = output_dir.joinpath(file_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(code)


def create_requirements_file(repo_dir: Path, repo: Repository) -> None:
    """Creates a ``requirements.txt`` file for the repository. Overwrite if exists."""
    output_file = repo_dir / "requirements.txt"
    output_file.write_text(f"{repo.name}=={repo.pypi_tag}")


def save_all_code(
        dataset: Dataset, output_dir: Path, without_type_annotations: bool
) -> None:
    """Clones all repositories and removes type annotations if specified."""
    for repo in dataset.repositories:
        repo_dir = clone(repo, output_dir)
        if without_type_annotations:
            for file in repo_dir.rglob("*.py"):
                console.log(f"Removing type annotations from {file}")
                code = file.read_text()
                code = remove_type_annotations(code)
                file.write_text(code)
        create_requirements_file(repo_dir, repo)


def run_methods(
        dataset: Path, output_dir: Path, without_type_annotations: bool
) -> None:
    """Runs the provide methods command."""
    console.log(f"Loading dataset from {dataset}")
    loaded_dataset = load_from_json_file(dataset)
    output_dir.mkdir(parents=True, exist_ok=True)
    extract_callables(loaded_dataset, output_dir, without_type_annotations)


def run_repositories(
        dataset: Path, output_dir: Path, without_type_annotations: bool
) -> None:
    """Runs the provide repositories command."""
    console.log(f"Loading dataset from {dataset}")
    loaded_dataset = load_from_json_file(dataset)
    output_dir.mkdir(parents=True, exist_ok=True)
    save_all_code(loaded_dataset, output_dir, without_type_annotations)


def run_pynguin(dataset: Path, output_path: Path) -> None:
    """Runs the provide pynguin command."""
    console.log(f"Loading dataset from {dataset}")
    loaded_dataset = load_from_json_file(dataset)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.is_file():
        output_path.unlink()
    create_pynguin_xmls(loaded_dataset, output_path)


@click.group()
def cli() -> None:
    """CLI for providing methods or full code from the dataset."""


@cli.command()
@click.option(
    "--dataset",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to the dataset JSON file.",
)
@click.option(
    "--output-dir",
    default="output",
    type=click.Path(file_okay=False, path_type=Path),
    help="Directory to store all code.",
)
@click.option(
    "--without-type-annotations",
    is_flag=True,
    default=False,
    help="Remove type annotations from the provided methods.",
)
def methods(dataset: Path, output_dir: Path, without_type_annotations: bool) -> None:
    """Provides the methods as they are stored in the JSON."""
    run_methods(dataset, output_dir, without_type_annotations)


@cli.command()
@click.option(
    "--dataset",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to the dataset JSON file.",
)
@click.option(
    "--output-dir",
    default="output",
    type=click.Path(file_okay=False, path_type=Path),
    help="Directory to store all code.",
)
@click.option(
    "--without-type-annotations",
    is_flag=True,
    default=False,
    help="Remove type annotations from the code.",
)
def repositories(
        dataset: Path, output_dir: Path, without_type_annotations: bool
) -> None:
    """Clones the projects to provide all code."""
    run_repositories(dataset, output_dir, without_type_annotations)


@cli.command()
@click.option(
    "--dataset",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to the dataset JSON file.",
)
@click.option(
    "--output-path",
    default="output",
    type=click.Path(file_okay=True, path_type=Path),
    help="Path to the pynguin.xml file.",
)
def pynguin(dataset: Path, output_path: Path) -> None:
    """Creates a directory with pynguin .xml files."""
    run_pynguin(dataset, output_path)


if __name__ == "__main__":
    cli()
