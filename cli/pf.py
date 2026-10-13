"""`pf` command-line interface."""

from pathlib import Path

import typer

from pf_core.brsr.parser import parse_file

app = typer.Typer(
    help="Paisa Footprint: financed emissions from BRSR filings.", no_args_is_help=True
)


@app.callback()
def main() -> None:
    """Paisa Footprint command-line tools."""


@app.command()
def parse(file: Path = typer.Argument(..., exists=True, dir_okay=False)) -> None:
    """Parse one BRSR XBRL file and print it as JSON (values exactly as filed)."""
    typer.echo(parse_file(file).model_dump_json(indent=2))


if __name__ == "__main__":
    app()
