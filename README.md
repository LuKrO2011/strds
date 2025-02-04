# Strds: String Dataset Creation Tool

This tool allows users to process and analyze Python repositories to create structured datasets for further analysis.


## Features

- **Dataset Creation:** Parse repositories to generate structured datasets in JSON format similar to
  the [methods2test](https://github.com/microsoft/methods2test) format.
- **Flexible Filters:** Apply customizable filters during dataset creation.
- **Provide Code Samples:** Allows to provide the relevant methods only or the entire repository code with the
  dependencies in a `requirements.txt` file to allow for dynamic analysis.

---

## Installation

You can either use Poetry or pip to install the required dependencies. We recommend using Poetry for a clean and
isolated environment on your local machine.

To set up the project and its dependencies, follow these steps:

1. Clone this repository to your local machine:

   ```bash
   git clone https://gitlab.infosun.fim.uni-passau.de/se2/pynguin/strds.git
   cd strds
   ```

2. Install Python 3.13 and pip, if you haven't already.

    - Windows: [Python](https://www.python.org/downloads/release/python), [Pip](https://pip.pypa.io/en/stable/installation/)
    - Ubuntu:
      ```bash
      sudo apt-get update
      sudo apt-get install -y python3.13 python3-pip
      ```
   - MacOS:
       ```bash
       brew install python@3.13
       ```

3. Create a virtual environment and install the project's dependencies using Poetry:

    ```bash
    poetry install
    ```

4. Activate the virtual environment:

    ```bash
    poetry shell
    ```

5. For Developers only: Activate pre-commit hooks:

    ```bash
    pre-commit install
    ```

---

## Command Line Interface (CLI)


### 1. Dataset Mining

Mines repositories from [PyPi](https://pypi.org/) and [GitHub](https://github.com/) to a CSV file.

```bash
poetry run mine --sample-size <size> --random-seed <seed> --project-list-file <file> [--redirect-github-urls] [--remove-duplicates] [--remove-no-github-url-found] [--csv-output <file>]
```

Options:

- `--sample-size`: Number of projects to sample. If not set, all projects are mined.
- `--random-seed`: Random seed for reproducibility.
- `--project-list-file`: Path to the project list file. If not set, all projects are considered.
- `--redirect-github-urls`: Follow GitHub redirects (default: `True`).
- `--remove-duplicates`: Remove duplicate projects (default: `True`).
- `--remove-no-github-url-found`: Remove projects without GitHub URLs (default: `True`).
- `--csv-output`: Path to store the CSV output (default: `output/repos.csv`).

Example:

```bash
poetry run mine --sample-size 10 --random-seed 42 --csv-output output/repos.csv
```

### 2. Dataset Creation

Creates a json file for the dataset.

```bash
poetry run dataset --csv-file <csv> --tmp-dir <dir> [--keep-tmp-dir] [--output <json>] [--filters <filters>]
```

Options:

- `--csv-file`: Path to the CSV file containing project definitions (required).
- `--tmp-dir`: Temporary directory to clone repositories (required).
- `--keep-tmp-dir`: Retain the temporary directory after execution (optional).
- `--output`: Path to the output JSON file (default: `output.json`).
- `--filters`: Comma-separated list of filters to apply (default: `NoStringTypeFilter,EmptyFilter`).

Example:

```bash
poetry run dataset --csv-file src/res/repos.csv --tmp-dir tmp --output output/dataset.json
```

---

### 3. Provide Dataset

Form the dataset json file the tool can provide relevant methods only or the entire repository code along with the
dependencies in a `requirements.txt` file.

#### Providing Methods

```bash
poetry run provide methods --dataset <dataset> [--output-dir <dir>] [--without-type-annotations]
```

Options:

- `--dataset`: Path to the dataset JSON file (required).
- `--output-dir`: Directory to store extracted methods (default: `all_code`).
- `--without-type-annotations`: Remove type annotations from methods (optional).

Example:

```bash
poetry run provide methods --dataset src/res/dataset.json --output-dir output
```

#### Providing Repositories

```bash
poetry run provide repositories --dataset <dataset> [--output-dir <dir>]
```

Options:

- `--dataset`: Path to the dataset JSON file (required).
- `--output-dir`: Directory to store extracted repository code (default: `all_code`).
- `--without-type-annotations`: Remove type annotations from the code (optional).

Example:

```bash
poetry run provide repositories --dataset src/res/dataset.json --output-dir output
```

---

## Dataset Structure

### Repository

```yaml
repository:
  name: string  # Name of the repository (matches the PyPI name)
  url: string  # Repository URL
  pypi_tag: string  # PyPI release tag of the repository
  git_commit_hash: string  # Specific commit hash of the repository
  modules: list  # List of modules in the repository
```

### Module

```yaml
module:
  name: string  # Module name
  file_path: string  # Relative path to the file containing the module
  functions: list  # List of standalone functions in the module
  classes: list  # List of classes in the module
```

### Function

```yaml
function:
  identifier: string  # Function name
  parameters: list  # List of parameters of the function
  annotations: string  # Function annotations
  return: string | null  # Return type of the function
  body: string  # Source code of the function
  signature: string  # Function signature (name + parameters + return type)
  full_signature: string  # Full function signature (annotations + name + parameters + return type)
  file: string  # Relative path to the file containing the function
```

### Class

```yaml
class:
  identifier: string  # Class name
  methods: list  # List of methods in the class
  superclasses: list  # Superclasses of the class
  fields: list  # Class fields (attributes)
  file: string  # Relative path to the file containing the class
```

### Method

```yaml
method:
  identifier: string  # Method name
  parameters: list  # List of parameters of the method
  annotations: string  # Method annotations
  return: string | null  # Return type of the method
  body: string  # Source code of the method
  signature: string  # Method signature (name + parameters + return type)
  full_signature: string  # Full method signature (annotations + name + parameters + return type)
  constructor: boolean  # Whether the method is a constructor
```

### Parameter

```yaml
parameter:
  identifier: string  # Parameter name
  type: string | null  # Type annotation of the parameter
  line_number: int  # Line number of the parameter definition
  col_offset: int  # Column offset of the parameter definition
```
