"""Module for filters that can be applied to a Repository."""

import inspect
import sys
from abc import ABC, abstractmethod

from strds.utils.structure import Repository


class Filter(ABC):  # pylint: disable=too-few-public-methods
    """Abstract base class for all filters."""

    @abstractmethod
    def apply(self, repository: Repository) -> Repository:
        """Apply the filter to a Repository and return the filtered result."""


class EmptyFilter(Filter):  # pylint: disable=too-few-public-methods
    """Filter that removes empty modules and empty classes.

    A class is empty, if it has no methods.
    A module is empty if, it has no functions and no classes.
    """

    def apply(self, repository: Repository) -> Repository:
        """Apply the filter to a Repository and return the filtered result."""
        # Remove empty classes
        for module in repository.modules:
            module.classes = [cls for cls in module.classes if cls.methods]

        # Remove empty modules
        repository.modules = [
            module
            for module in repository.modules
            if module.classes or module.functions
        ]
        return repository


class NoStringTypeFilter(Filter):  # pylint: disable=too-few-public-methods
    """Removes all functions and methods without a 'str' parameter or return type.

    Does not consider list[str], dict[str, str] etc.
    """

    def apply(self, repository: Repository) -> Repository:
        """Apply the filter to a Repository and return the filtered result."""
        for module in repository.modules:
            module.functions = [
                func
                for func in module.functions
                if any(param.type == "str" for param in func.parameters)
                or func.return_type == "str"
            ]
            for cls in module.classes:
                cls.methods = [
                    method
                    for method in cls.methods
                    if any(param.type == "str" for param in method.parameters)
                    or method.return_type == "str"
                ]
        return repository


class PublicModulesFilter(Filter):  # pylint: disable=too-few-public-methods
    """Removes all non-public modules.

    In Python, modules that start with an underscore are considered non-public
    (private, package private, internal, etc.).
    """

    def apply(self, repository: Repository) -> Repository:
        """Apply the filter to a Repository and return the filtered result."""
        repository.modules = [
            module for module in repository.modules if not module.name.startswith("_")
        ]
        return repository


class TestModulesFilter(Filter):  # pylint: disable=too-few-public-methods
    """Removes all test modules.

    Identifies tests by checking module and package names.
    Test modules typically have names starting with 'test_' or are located in
    packages/directories that start with 'test'.
    """

    def apply(self, repository: Repository) -> Repository:
        """Apply the filter to a Repository and return the filtered result."""
        repository.modules = [
            module
            for module in repository.modules
            if not module.name.startswith("test_")
            and not str(module.file_path).startswith("test")
            and "/test" not in str(module.file_path)
        ]
        return repository


def get_all_filters() -> dict[str, type[Filter]]:
    """Discover all Filter subclasses in the current module dynamically.

    Returns:
        dict[str, type[Filter]]: A mapping from filter name to the Filter class.
    """
    current_module = sys.modules[__name__]
    filters = {}
    for name, obj in inspect.getmembers(current_module, inspect.isclass):
        if issubclass(obj, Filter) and obj is not Filter:
            filters[name.lower()] = obj
    return filters


class FilterFactory:  # pylint: disable=too-few-public-methods
    """Factory class to create filters dynamically from a string."""

    _filters = get_all_filters()

    @classmethod
    def from_string(cls, filter_name: str) -> Filter:
        """Create a filter object from a string."""
        filter_class = cls._filters.get(filter_name.lower())
        if not filter_class:
            raise ValueError(f"Unknown filter: {filter_name}")
        return filter_class()


def create_filters(filter_names: list[str] | str) -> list[Filter]:
    """Create a list of filters from a list of filter names."""
    if isinstance(filter_names, str):
        filter_names = filter_names.split(",")
    return [FilterFactory.from_string(name) for name in filter_names]
