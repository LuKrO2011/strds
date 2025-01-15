"""Information about the data structures used for the dataset."""

import json
from abc import ABC
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from strds.utils.clone_projects import clone_repository

if TYPE_CHECKING:
    from strds.utils.filter import Filter


@dataclass
class Dataset:
    """A data structure representing a dataset."""

    repositories: list["Repository"] = field(default_factory=list)

    def sort(self):
        for repo in self.repositories:
            repo.sort()
        self.repositories = sorted(self.repositories)
        return self


@dataclass
class Repository:
    """A data structure representing a repository."""

    name: str  # == pypi_name
    url: str  # GitHub URL
    pypi_tag: str
    git_commit_hash: str
    modules: list["Module"] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "Repository":
        return cls(
            name=data["name"],
            pypi_tag=data["pypi_tag"],
            url=data["url"],
            git_commit_hash=data["git_commit_hash"],
            modules=[Module.from_dict(module) for module in data.get("modules", [])],
        )

    def apply(self, filters: list["Filter"]) -> "Repository":
        """Apply a list of filters to the repository.

        Args:
            filters (List[Filter]): A list of filters to apply.

        Returns:
            Repository: The filtered repository.
        """
        for filter_ in filters:
            self = filter_.apply(self)
        return self

    def sort(self):
        for module in self.modules:
            module.sort()
        self.modules = sorted(self.modules)
        return self

    def __lt__(self, other):
        return self.name < other.name


@dataclass
class Module:
    """A data structure representing a python module."""

    name: str
    file_path: Path  # relative
    functions: list["Function"] = field(default_factory=list)
    classes: list["Class"] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "Module":
        return cls(
            name=data["name"],
            file_path=Path(data["file_path"]),
            functions=[Function.from_dict(func) for func in data.get("functions", [])],
            classes=[Class.from_dict(cls) for cls in data.get("classes", [])],
        )

    def sort(self):
        for func in self.functions:
            func.sort()
        self.functions = sorted(self.functions)
        for cls in self.classes:
            cls.sort()
        self.classes = sorted(self.classes)
        return self

    def __lt__(self, other):
        return self.name < other.name


@dataclass
class Locatable(ABC):
    """A data structure representing a locatable object."""

    name: str
    line_number: int
    col_offset: int

    def __lt__(self, other):
        return self.name < other.name


@dataclass
class Callable(Locatable):
    """A data structure representing a callable object."""

    parameters: list["Parameter"]
    return_type: str | None
    body: str
    signature: str
    full_signature: str
    annotations: str | None = ""

    @classmethod
    def from_dict(cls, data: dict) -> "Callable":
        return cls(
            name=data["name"],
            line_number=data["line_number"],
            col_offset=data["col_offset"],
            parameters=[
                Parameter.from_dict(param) for param in data.get("parameters", [])
            ],
            return_type=data.get("return_type"),
            body=data["body"],
            signature=data["signature"],
            full_signature=data["full_signature"],
            annotations=data.get("annotations", ""),
        )

    def sort(self):
        self.parameters = sorted(self.parameters)
        return self


@dataclass
class Function(Callable):
    """A data structure representing a standalone function."""

    @classmethod
    def from_dict(cls, data: dict) -> "Function":
        return cls(**Callable.from_dict(data).__dict__)


@dataclass
class Method(Callable):
    """A data structure representing a method."""

    is_constructor: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> "Method":
        return cls(
            **Callable.from_dict(data).__dict__,
            is_constructor=data.get("is_constructor", False),
        )


@dataclass
class Class:
    """A data structure representing a class."""

    name: str
    methods: list[Method] = field(default_factory=list)
    superclasses: list[str] = field(default_factory=list)
    fields: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "Class":
        return cls(
            name=data["name"],
            methods=[Method.from_dict(method) for method in data.get("methods", [])],
            superclasses=data.get("superclasses", []),
            fields=data.get("fields", []),
        )

    def sort(self):
        for method in self.methods:
            method.sort()
        self.methods = sorted(self.methods)
        self.superclasses = sorted(self.superclasses)
        self.fields = sorted(self.fields)
        return self

    def __lt__(self, other):
        return self.name < other.name


@dataclass
class Parameter(Locatable):
    """A data structure representing a parameter."""

    type: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "Parameter":
        return cls(
            name=data["name"],
            line_number=data["line_number"],
            col_offset=data["col_offset"],
            type=data.get("type"),
        )


class PathEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Path):
            return str(obj)
        return super().default(obj)


def save_to_json_file(repositories: list[Repository], file_path: Path):
    """Serializes a list of Repository objects into JSON and writes to a file."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as json_file:
        json.dump(
            [asdict(repo) for repo in repositories],
            json_file,
            indent=4,
            ensure_ascii=False,
            cls=PathEncoder,
        )


def load_from_json_file(file_path: Path) -> Dataset:
    """Loads a JSON file and parses it into a list of Repository objects."""
    with open(file_path, encoding="utf-8") as json_file:
        data = json.load(json_file)
        repositories = [Repository.from_dict(repo) for repo in data]
        return Dataset(repositories=repositories).sort()


def clone(repository: Repository, output_dir: Path) -> Path:
    """Clones a repository into the output directory."""
    repo_dir = output_dir / repository.name
    clone_repository(repository.url, repository.git_commit_hash, repo_dir)
    return repo_dir
