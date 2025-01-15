"""Main module for the CLI."""
import sys

from strds.provide import cli

if __name__ == "__main__":
    sys.exit(cli(sys.argv)) # pylint: disable=too-many-function-args
