"""CLI to parse a Python repository and output its information as dataset."""

import ast
import shutil
from pathlib import Path

import click
from rich.console import Console

from strds.clone_projects import LocalProject, clone_projects
from strds.filter import Filter, FilterFactory
from strds.structure import (
    Class,
    Function,
    Method,
    Module,
    Parameter,
    Repository,
    save_to_json_file,
)

console = Console()


def _col_offset_param(node: ast.AST) -> int:
    """Returns the column offset of the parameter node.

    We add 1 to the column offset to make it 1-indexed so that it matches the cursor
    position.
    """
    return node.col_offset + 1


def _col_offset_callable(node: ast.AST) -> int:
    """Returns the column offset of the callable (method/function) node.

    We add 1 and len("def ") = 4 to the row offset to make it 1-indexed and to account
    for the "def " keyword. Therewith it matches the cursor position at the start of
    the function name.
    """
    return node.col_offset + 1 + len("def ")


def _line_offset(node: ast.AST) -> int:
    """Returns the line offset of the node."""
    return node.lineno


def parse_parameter(node: ast.arg) -> Parameter:
    """Parses an AST argument node into a Parameter dataclass."""
    return Parameter(
        name=node.arg,
        line_number=_line_offset(node),
        col_offset=_col_offset_param(node),
        type=ast.unparse(node.annotation) if node.annotation else None,
    )


def parse_function(node: ast.FunctionDef, file: Path) -> Function:
    """Parses an AST function node into a Function dataclass."""
    body, parameters, return_type, signature = extract_info(file, node)
    return Function(
        name=node.name,
        line_number=_line_offset(node),
        col_offset=_col_offset_callable(node),
        parameters=parameters,
        return_type=return_type,
        body=body,
        signature=signature,
        full_signature=signature,
    )


def parse_class(node: ast.ClassDef, file: Path) -> Class:
    """Parses an AST class node into a Class dataclass."""
    methods = []
    fields = []
    for item in node.body:
        if isinstance(item, ast.FunctionDef):
            methods.append(parse_method(item, file, node.name))
        elif isinstance(item, ast.Assign):
            fields.extend(
                [target.id for target in item.targets if isinstance(target, ast.Name)]
            )
    superclasses = [base.id for base in node.bases if isinstance(base, ast.Name)]
    return Class(
        name=node.name,
        methods=methods,
        superclasses=superclasses,
        fields=fields,
    )


def parse_method(node: ast.FunctionDef, file: Path, class_name: str) -> Method:
    """Parses an AST method node into a Method dataclass."""
    body, parameters, return_type, signature = extract_info(file, node)
    return Method(
        name=node.name,
        line_number=_line_offset(node),
        col_offset=_col_offset_callable(node),
        parameters=parameters,
        return_type=return_type,
        body=body,
        signature=f"{class_name}.{signature}",
        full_signature=f"{class_name}.{signature}",
        is_constructor=node.name == "__init__",
    )


def craft_signature(
    name: str, parameters: list[Parameter], return_type: str | None
) -> str:
    """Crafts a function signature from its name and parameters."""
    signature = "("
    if parameters:
        for i, param in enumerate(parameters):
            if param.type:
                signature += f"{param.name}: {param.type}"
            else:
                signature += param.name
            if i < len(parameters) - 1:
                signature += ", "
    signature += ")"
    if return_type:
        signature += f" -> {return_type}"
    return f"{name}{signature}"


def extract_info(
    file: Path, node: ast.FunctionDef
) -> tuple[str, list[Parameter], str, str | None]:
    """Extracts body, parameters, return type, and signature from a function node."""
    parameters = [parse_parameter(arg) for arg in node.args.args]
    body = ast.get_source_segment(Path(file).read_text(), node) or ""
    return_type = ast.unparse(node.returns) if node.returns else None
    signature = craft_signature(node.name, parameters, return_type)
    return body, parameters, return_type, signature


def parse_module(file_path: Path, relative_to: Path) -> Module:
    """Parses a Python file into a Module dataclass."""
    with file_path.open("r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=str(file_path))

    functions = []
    classes = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            functions.append(parse_function(node, file_path))
        elif isinstance(node, ast.ClassDef):
            classes.append(parse_class(node, file_path))
    return Module(
        name=file_path.stem,
        file_path=file_path.relative_to(relative_to),
        functions=functions,
        classes=classes,
    )


def parse_repository(project: LocalProject) -> Repository:
    """Parses a repository into a Repository dataclass."""
    modules = []
    for file_path in project.path.rglob("*.py"):
        try:
            module = parse_module(file_path, relative_to=project.path)
            modules.append(module)
        except SyntaxError as e:
            console.log(f"SyntaxError: {file_path}: {e}")
        except Exception as e:
            console.log(f"Error parsing {file_path}: {e}")
    return Repository(
        name=project.project.project_name,
        url=project.project.github_url,
        pypi_tag=project.project.matching_github_tag or project.project.pypi_latest_tag,
        modules=modules,
        git_commit_hash=project.git_commit_hash,
    )


def create_dataset(
    csv_file: Path,
    tmp_dir: Path,
    keep_tmp_dir: bool = False,
    output: Path = Path("output.json"),
    filters: list[Filter] = None,
) -> None:
    """Create a dataset from the given CSV file."""
    projects: list[LocalProject] = clone_projects(csv_file, tmp_dir)
    repositories = []
    for project in projects:
        console.log(f"Parsing: {project.path}")
        repository = parse_repository(project)
        repository = repository.apply(filters)
        if repository.modules:
            repositories.append(repository)
        else:
            console.log(f"No modules left after filtering: {project.path}")
    save_to_json_file(repositories, output)
    if not keep_tmp_dir:
        shutil.rmtree(tmp_dir)


@click.command()
@click.option(
    "--csv-file",
    help="The path to the CSV file containing the project definitions.",
    metavar="<csv>",
    required=True,
    type=click.Path(exists=True, dir_okay=False, resolve_path=True, path_type=Path),
)
@click.option(
    "--tmp-dir",
    help="The temporary directory to clone the repositories.",
    metavar="<dir>",
    required=True,
    type=click.Path(file_okay=False, resolve_path=True, path_type=Path),
)
@click.option(
    "--keep-tmp-dir",
    help="Keep the temporary directory after the execution.",
    is_flag=True,
    default=False,
)
@click.option(
    "--output",
    help="The output JSON file path.",
    metavar="<json>",
    default="output.json",
    type=click.Path(dir_okay=False, writable=True, resolve_path=True, path_type=Path),
)
@click.option(
    "--filters",
    help="A comma separated list of the filters to apply.",
    metavar="<filters>",
    default="NoStringTypeFilter,EmptyFilter",
    type=str,
)
def cli(csv_file: Path, tmp_dir: Path, keep_tmp_dir: bool, output: Path, filters: str):
    """Parse a Python repository and output its information as dataset."""
    filters = [FilterFactory().from_string(f) for f in filters.split(",")]
    create_dataset(csv_file, tmp_dir, keep_tmp_dir, output, filters)


if __name__ == "__main__":
    cli()
