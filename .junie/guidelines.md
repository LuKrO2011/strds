# STRDS Project Development Guidelines

This document provides essential development guidelines for the STRDS project.

## Testing Guidelines

### Writing Tests

1. **Test File Naming**: Name test files with the prefix `test_` followed by the name of the module being tested.

2. **Test Function Naming**: Name test functions with the prefix `test_` followed by a descriptive name of what is being tested.

3. **Using Fixtures**: Use pytest fixtures for setup and teardown. The project uses fixtures like `tmp_path` for temporary directory management.

## Additional Development Information

### Code Style

The project enforces a strict code style using several tools:

1. **Black**: For code formatting.
   ```bash
   make black
   ```

2. **isort**: For import sorting.
   ```bash
   make isort
   ```

3. **mypy**: For type checking.
   ```bash
   make mypy
   ```

4. **ruff**: For linting.
   ```bash
   make ruff
   ```

5. **pyupgrade**: For upgrading Python syntax.
   ```bash
   make pyupgrade
   ```

6. **Run all style checks**:
   ```bash
   make check-style
   ```

7. **Run all checks (style, safety, tests)**:
   ```bash
   make check
   ```

### Documentation Style

The project uses Google-style docstrings. Example:

```python
def function_name(param1: type, param2: type) -> return_type:
    """Short description of the function.

    Longer description if needed.

    Args:
        param1: Description of param1.
        param2: Description of param2.

    Returns:
        Description of the return value.

    Raises:
        ExceptionType: When and why this exception is raised.
    """
    # Function implementation
```


### Debugging

1. **Logging**: The project uses the standard Python logging module with rich formatting. Tests have logging enabled with the `log_cli` option.

2. **Coverage**: Use the coverage report to identify untested code paths.

3. **Pre-commit Hooks**: The project uses pre-commit hooks to enforce code quality. Run them manually with:
   ```bash
   poetry run pre-commit run --all-files
   ```
