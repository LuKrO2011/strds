from pathlib import Path

from strds.dataset import create_dataset
from strds.utils.filter import create_filters
from strds.utils.structure import load_from_json_file


def test_integrate(tmp_path: Path):
    project_path = Path().absolute()
    if project_path.name == "tests":
        project_path /= ".."  # pragma: no cover
    csv_file_path = project_path / "src" / "res" / "repos.csv"
    expected_json_path = project_path / "src" / "res" / "dataset.json"
    tmp_dir = tmp_path / "tmp"
    output = tmp_path / "output.json"
    filters = create_filters("NoStringTypeFilter,EmptyFilter")

    create_dataset(csv_file_path, tmp_dir=tmp_dir, output=output, filters=filters)

    actual = load_from_json_file(output)
    expected = load_from_json_file(expected_json_path)
    assert actual.sort() == expected.sort()
