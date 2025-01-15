"""Module for filters that can be applied to a Repository."""

import inspect
import sys
from abc import ABC, abstractmethod

from strds.utils.structure import Repository


class Filter(ABC):
    """Abstract base class for all filters."""

    @abstractmethod
    def apply(self, repository: Repository) -> Repository:
        """Apply the filter to a Repository and return the filtered result."""
        pass


class EmptyFilter(Filter):
    """Filter that removes empty modules and empty classes.

    A class is empty, if it has no methods.
    A module is empty if, it has no functions and no classes.
    """

    def apply(self, repository: Repository) -> Repository:
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


# TODO: Also consider dicts, lists etc. using strings
class NoStringTypeFilter(Filter):
    """Removes all functions and methods without a 'str' parameter or return type."""

    def apply(self, repository: Repository) -> Repository:
        for module in repository.modules:
            module.functions = [
                func
                for func in module.functions
                if any(
                    param.type == "str" for param in func.parameters
                ) or func.return_type == "str"
            ]
            for cls in module.classes:
                cls.methods = [
                    method
                    for method in cls.methods
                    if any(
                        param.type == "str" for param in method.parameters
                    ) or method.return_type == "str"
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


class FilterFactory:
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
