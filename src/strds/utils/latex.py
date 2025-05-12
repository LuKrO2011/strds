"""Utilities for LaTeX export."""

from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()


def export_to_latex(stats: list[dict[str, Any]], output_path: Path) -> None:
    """Export the statistics to a LaTeX table.

    Args:
        stats: A list of dictionaries containing statistics for each project
        output_path: Path to save the LaTeX table
    """
    # Get the template file path
    template_path = Path(__file__).parent.parent.parent / "res" / "templates" / "tex-table.tex"

    # Load the template
    template = template_path.read_text(encoding="utf-8")

    # Generate rows
    rows = ""
    for stat in stats:
        row = (
            f"{stat['project_name']} & "
            f"{stat['modules_count']} & "
            f"{stat['version_tag']} & "
            f"{stat['cc_percentage']:.2f}\\% \\\\\n"
        )
        rows += row

    # Replace the placeholder with the rows
    latex_table = template.replace("{rows}", rows)

    # Write to file
    output_path.write_text(latex_table, encoding="utf-8")
    console.log(f"[bold green]LaTeX table exported to:[/bold green] {output_path}")
