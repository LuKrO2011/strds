from pathlib import Path

import pytest

from strds.provide import run_methods, run_pynguin, run_repositories
from strds.utils.pynguin_xml import read_xml


def test_integrate_pynguin(tmp_path):
    project_path = Path().absolute()
    if project_path.name == "tests":
        project_path /= ".."  # pragma: no cover
    dataset_path = project_path / "src" / "res" / "dataset.json"
    output = tmp_path / "output"
    expected_xml_path = project_path / "src" / "res" / "pynguin.xml"

    run_pynguin(dataset_path, output)

    actual = read_xml(output)
    expected = read_xml(expected_xml_path)
    assert actual == expected


@pytest.fixture
def file_with_type_annotations(tmp_path) -> Path:
    file_content = '''def to_bash_variable(param: str) -> str:
    """
        Convert a command variable in a bash variable
    """
    return param.upper().replace('-', '_')'''

    # original path: "mlvtools" / "helper.py" : "to_bash_variable"
    file_path = tmp_path / "to_bash_variable.py"
    file_path.write_text(file_content)
    return file_path


@pytest.fixture
def file_without_type_annotations(tmp_path) -> Path:
    file_content = '''def to_bash_variable(param):
    """
        Convert a command variable in a bash variable
    """
    return param.upper().replace('-', '_')'''

    # original path: "mlvtools" / "helper.py" : "to_bash_variable"
    file_path = tmp_path / "to_bash_variable.py"
    file_path.write_text(file_content)
    return file_path


def test_integrate_methods_with_type_annotations(tmp_path, file_with_type_annotations):
    project_path = Path().absolute()
    if project_path.name == "tests":
        project_path /= ".."  # pragma: no cover
    dataset_path = project_path / "src" / "res" / "dataset.json"
    output_dir = tmp_path / "output"

    run_methods(dataset_path, output_dir, without_type_annotations=False)

    assert output_dir.exists()
    assert (output_dir / "mlvtools" / "helper" / "to_bash_variable.py").exists()
    actual = (output_dir / "mlvtools" / "helper" / "to_bash_variable.py").read_text()
    expected = file_with_type_annotations.read_text()
    assert actual == expected


def test_integrate_methods_without_type_annotations(
    tmp_path, file_without_type_annotations
):
    project_path = Path().absolute()
    if project_path.name == "tests":
        project_path /= ".."  # pragma: no cover
    dataset_path = project_path / "src" / "res" / "dataset.json"
    output_dir = tmp_path / "output"

    run_methods(dataset_path, output_dir, without_type_annotations=True)

    assert output_dir.exists()
    assert (output_dir / "mlvtools" / "helper" / "to_bash_variable.py").exists()
    actual = (output_dir / "mlvtools" / "helper" / "to_bash_variable.py").read_text()
    expected = file_without_type_annotations.read_text()
    assert actual == expected


def test_integrate_repositories_with_type_annotations(
    tmp_path, file_with_type_annotations
):
    project_path = Path().absolute()
    if project_path.name == "tests":
        project_path /= ".."  # pragma: no cover
    dataset_path = project_path / "src" / "res" / "dataset.json"
    output_dir = tmp_path / "output"

    run_repositories(dataset_path, output_dir, without_type_annotations=False)

    assert output_dir.exists()
    assert (output_dir / "mlvtools" / "mlvtools" / "helper.py").exists()
    actual = (output_dir / "mlvtools" / "mlvtools" / "helper.py").read_text()
    expected = file_with_type_annotations.read_text()
    assert expected in actual


def test_integrate_repositories_without_type_annotations(
    tmp_path, file_without_type_annotations
):
    project_path = Path().absolute()
    if project_path.name == "tests":
        project_path /= ".."  # pragma: no cover
    dataset_path = project_path / "src" / "res" / "dataset.json"
    output_dir = tmp_path / "output"

    run_repositories(dataset_path, output_dir, without_type_annotations=True)

    assert output_dir.exists()
    assert (output_dir / "mlvtools" / "mlvtools" / "helper.py").exists()
    actual = (output_dir / "mlvtools" / "mlvtools" / "helper.py").read_text()
    expected = file_without_type_annotations.read_text()
    assert expected in actual
