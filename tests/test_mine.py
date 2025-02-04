from strds.mine import sample_pypi_projects


def test_sample_pypi_projects():
    csv = sample_pypi_projects(
        sample_size=1,
        random_seed=42,
        project_list_file=None,
        redirect_github_urls=True,
        remove_duplicates=False,
        remove_no_github_url_found=True,
    )
    assert csv
