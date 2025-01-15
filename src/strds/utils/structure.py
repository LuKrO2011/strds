"""Information about the data structures used for the dataset."""

import json
from abc import ABC
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from strds.utils.clone_projects import clone_repository

if TYPE_CHECKING:
    from strds.utils.filter import Filter


@dataclass
class Dataset:
    """A data structure representing a dataset."""

    repositories: list["Repository"] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "Dataset":  # type: ignore[type-arg]
        """Create a Dataset object from a dictionary."""
        return cls(
            repositories=[
                Repository.from_dict(repo) for repo in data.get("repositories", [])
            ]
        )

    def sort(self) -> "Dataset":
        """Sort the dataset."""
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
    def from_dict(cls, data: dict) -> "Repository":  # type: ignore[type-arg]
        """Create a Repository object from a dictionary."""
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
        repository = self
        for filter_ in filters:
            repository = filter_.apply(repository)
        return repository

    def sort(self) -> "Repository":
        """Sort the repository."""
        for module in self.modules:
            module.sort()
        self.modules = sorted(self.modules)
        return self

    def __lt__(self, other: "Repository") -> bool:
        return self.name < other.name


@dataclass
class Module:
    """A data structure representing a python module."""

    name: str
    file_path: Path  # relative
    functions: list["Function"] = field(default_factory=list)
    classes: list["Class"] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "Module":  # type: ignore[type-arg]
        """Create a Module object from a dictionary."""
        return cls(
            name=data["name"],
            file_path=Path(data["file_path"]),
            functions=[Function.from_dict(func) for func in data.get("functions", [])],
            classes=[Class.from_dict(cls) for cls in data.get("classes", [])],
        )

    def sort(self) -> "Module":
        """Sort the module."""
        for func in self.functions:
            func.sort()
        self.functions = sorted(self.functions)
        for cls in self.classes:
            cls.sort()
        self.classes = sorted(self.classes)
        return self

    def __lt__(self, other: "Module") -> bool:
        return self.name < other.name


@dataclass
class Locatable(ABC):
    """A data structure representing a locatable object."""

    name: str
    line_number: int
    col_offset: int

    def __lt__(self, other: "Locatable") -> bool:
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
    def from_dict(cls, data: dict) -> "Callable":  # type: ignore[type-arg]
        """Create a Callable object from a dictionary."""
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

    def sort(self: "Callable") -> "Callable":
        """Sort the callable."""
        self.parameters = sorted(self.parameters)
        return self


@dataclass
class Function(Callable):
    """A data structure representing a standalone function."""

    @classmethod
    def from_dict(cls, data: dict) -> "Function":  # type: ignore[type-arg]
        """Create a Function object from a dictionary."""
        return cls(**Callable.from_dict(data).__dict__)


@dataclass
class Method(Callable):
    """A data structure representing a method."""

    is_constructor: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> "Method":  # type: ignore[type-arg]
        """Create a Method object from a dictionary."""
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
    def from_dict(cls, data: dict) -> "Class":  # type: ignore[type-arg]
        """Create a Class object from a dictionary."""
        return cls(
            name=data["name"],
            methods=[Method.from_dict(method) for method in data.get("methods", [])],
            superclasses=data.get("superclasses", []),
            fields=data.get("fields", []),
        )

    def sort(self) -> "Class":
        """Sort the class."""
        for method in self.methods:
            method.sort()
        self.methods = sorted(self.methods)
        self.superclasses = sorted(self.superclasses)
        self.fields = sorted(self.fields)
        return self

    def __lt__(self, other: "Class") -> bool:
        return self.name < other.name


@dataclass
class Parameter(Locatable):
    """A data structure representing a parameter."""

    type: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "Parameter":  # type: ignore[type-arg]
        """Create a Parameter object from a dictionary."""
        return cls(
            name=data["name"],
            line_number=data["line_number"],
            col_offset=data["col_offset"],
            type=data.get("type"),
        )


class PathEncoder(json.JSONEncoder):
    """A JSON encoder that serializes Path objects to strings."""

    def default(self, o: object) -> Any:
        """Converts a Path object to a string."""
        if isinstance(o, Path):
            return str(o)
        return super().default(o)


def save_to_json_file(dataset: Dataset, file_path: Path) -> None:
    """Serializes a list of Repository objects into JSON and writes to a file."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with Path.open(file_path, "w", encoding="utf-8") as json_file:
        json.dump(asdict(dataset), json_file, cls=PathEncoder, indent=2)


def load_from_json_file(file_path: Path) -> Dataset:
    """Loads a JSON file and parses it into a list of Repository objects."""
    with Path.open(file_path, encoding="utf-8") as json_file:
        data = json.load(json_file)
        return Dataset.from_dict(data)


def clone(repository: Repository, output_dir: Path) -> Path:
    """Clones a repository into the output directory."""
    repo_dir = output_dir / repository.name
    clone_repository(repository.url, repository.git_commit_hash, repo_dir)
    return repo_dir
