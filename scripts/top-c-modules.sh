#!/bin/bash

# Set the project root directory
PROJECT_ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

# Mine the top 30 PyPI packages with C/C++ dependencies
poetry run mine --use-top-packages --sample-size 30 --languages "C,C++" --min-language-percentage=0.01 --csv-output "$PROJECT_ROOT_DIR/output/repos.csv"

# Create a dataset using the correct filters
poetry run dataset --csv-file "$PROJECT_ROOT_DIR/output/repos.csv" --tmp-dir "$PROJECT_ROOT_DIR/tmp" --filters "PrivateModuleFilter,TestModuleFilter,NonCoreModuleFilter,EmptyFilter" --output "$PROJECT_ROOT_DIR/output/dataset.json" --keep-tmp-dir

# Create a Pynguin dataset
poetry run provide pynguin --dataset "$PROJECT_ROOT_DIR/output/dataset.json" --output-path "$PROJECT_ROOT_DIR/output/c-modules.xml"
