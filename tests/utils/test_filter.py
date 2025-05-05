"""Tests for the filter module."""

from pathlib import Path

from strds.utils.filter import (
    NonCoreModuleFilter,
    PrivateModuleFilter,
    TestModuleFilter,
)
from strds.utils.structure import Module, Repository


def test_public_modules_filter():
    """Test that PrivateModulesFilter removes non-public modules."""
    # Create a repository with both public and non-public modules
    repository = Repository(
        name="test_repo",
        url="https://github.com/test/test_repo",
        pypi_tag="1.0.0",
        git_commit_hash="abcdef",
        modules=[
            Module(name="public_module", file_path=Path("public_module.py")),
            Module(name="_private_module", file_path=Path("_private_module.py")),
            Module(name="__internal_module", file_path=Path("__internal_module.py")),
        ],
    )

    # Apply the PrivateModulesFilter
    filter_instance = PrivateModuleFilter()
    filtered_repository = filter_instance.apply(repository)

    # Verify that only the public module remains
    assert len(filtered_repository.modules) == 1
    assert filtered_repository.modules[0].name == "public_module"


def test_test_modules_filter():
    """Test that TestModulesFilter removes test modules."""
    # Create a repository with both test and non-test modules
    repository = Repository(
        name="test_repo",
        url="https://github.com/test/test_repo",
        pypi_tag="1.0.0",
        git_commit_hash="abcdef",
        modules=[
            Module(name="regular_module", file_path=Path("regular_module.py")),
            Module(name="test_module", file_path=Path("test_module.py")),
            Module(name="module_in_test", file_path=Path("test/module.py")),
            Module(name="test_in_subdir", file_path=Path("subdir/test/module.py")),
        ],
    )

    # Apply the TestModulesFilter
    filter_instance = TestModuleFilter()
    filtered_repository = filter_instance.apply(repository)

    # Verify that only the non-test module remains
    assert len(filtered_repository.modules) == 1
    assert filtered_repository.modules[0].name == "regular_module"


def test_non_core_modules_filter():
    """Test that NonCoreModuleFilter keeps only core modules."""
    # Create a repository with both core and non-core modules
    repository = Repository(
        name="test_repo",
        url="https://github.com/test/test_repo",
        pypi_tag="1.0.0",
        git_commit_hash="abcdef",
        modules=[
            Module(name="src.test_repo.core", file_path=Path("src/test_repo/core.py")),
            Module(name="test_repo.utils", file_path=Path("test_repo/utils.py")),
            Module(name="src.other.module", file_path=Path("src/other/module.py")),
            Module(name="unrelated.module", file_path=Path("unrelated/module.py")),
        ],
    )

    # Apply the NonCoreModuleFilter
    filter_instance = NonCoreModuleFilter()
    filtered_repository = filter_instance.apply(repository)

    # Verify that only the core modules remain
    assert len(filtered_repository.modules) == 2
    assert filtered_repository.modules[0].name == "src.test_repo.core"
    assert filtered_repository.modules[1].name == "test_repo.utils"
