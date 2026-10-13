"""`pf` command-line interface."""

import typer

app = typer.Typer(
    help="Paisa Footprint: financed emissions from BRSR filings.", no_args_is_help=True
)


@app.callback()
def main() -> None:
    """Paisa Footprint command-line tools."""


if __name__ == "__main__":
    app()
