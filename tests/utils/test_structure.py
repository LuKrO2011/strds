import json
from pathlib import Path

from strds.utils.structure import (
    Dataset,
    Repository,
    load_from_json_file,
    save_to_json_file,
)


def test_save_and_load_json_file(tmp_path: Path):
    """Test saving and loading a Dataset to/from a JSON file."""
    # Create a simple Dataset
    dataset = Dataset(
        repositories=[
            Repository(
                name="test-repo",
                url="https://github.com/test/test-repo",
                pypi_tag="v1.0.0",
                git_commit_hash="abc123",
                modules=[],
            )
        ]
    )

    # Save to a temporary file
    output_file = tmp_path / "test_dataset.json"
    save_to_json_file(dataset, output_file)

    # Verify the file exists
    assert output_file.exists()

    # Verify the file contains valid JSON
    with output_file.open(encoding="utf-8") as f:
        data = json.load(f)
        assert "repositories" in data
        assert len(data["repositories"]) == 1
        assert data["repositories"][0]["name"] == "test-repo"

    # Load the file back
    loaded_dataset = load_from_json_file(output_file)

    # Verify the loaded dataset matches the original
    assert len(loaded_dataset.repositories) == 1
    assert loaded_dataset.repositories[0].name == "test-repo"
    assert loaded_dataset.repositories[0].url == "https://github.com/test/test-repo"
    assert loaded_dataset.repositories[0].git_commit_hash == "abc123"
