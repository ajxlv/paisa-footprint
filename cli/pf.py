"""`pf` command-line interface."""

import csv
from collections import Counter
from pathlib import Path

import typer

from pf_core.brsr.parser import parse_directory, parse_file
from pf_core.brsr.validators import RULE_DESCRIPTIONS, validate
from pf_core.snapshot import build_snapshot

app = typer.Typer(
    help="Paisa Footprint: financed emissions from BRSR filings.", no_args_is_help=True
)

REPORT_COLUMNS = [
    "source_file",
    "company_name",
    "company_key",
    "rule_id",
    "severity",
    "field",
    "fiscal_year",
    "message",
    "observed_value",
    "suggested_fix",
]


@app.callback()
def main() -> None:
    """Paisa Footprint command-line tools."""


@app.command()
def parse(file: Path = typer.Argument(..., exists=True, dir_okay=False)) -> None:
    """Parse one BRSR XBRL file and print it as JSON (values exactly as filed)."""
    typer.echo(parse_file(file).model_dump_json(indent=2))


@app.command("validate")
def validate_cmd(
    directory: Path = typer.Argument(..., exists=True, file_okay=False),
    out: Path = typer.Option(Path("validation_report.csv"), help="CSV report path."),
) -> None:
    """Run validators over every filing in DIRECTORY and write a CSV report."""
    filings, failures = parse_directory(directory)
    counts: Counter[str] = Counter()
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=REPORT_COLUMNS)
        writer.writeheader()
        for filing in filings:
            for issue in validate(filing):
                counts[issue.rule_id] += 1
                writer.writerow(
                    {
                        "source_file": filing.source_file,
                        "company_name": filing.company_name,
                        "company_key": filing.company_key,
                        **issue.model_dump(),
                    }
                )
    typer.echo(f"Parsed {len(filings)} filings, {len(failures)} failed to parse.")
    for name, reason in failures.items():
        typer.echo(f"  FAILED {name}: {reason}")
    typer.echo(f"{'rule':<5} {'issues':>6}  description")
    for rule, description in RULE_DESCRIPTIONS.items():
        typer.echo(f"{rule:<5} {counts[rule]:>6}  {description}")
    typer.echo(f"Report written to {out}")


@app.command("build-snapshot")
def build_snapshot_cmd(
    input: Path = typer.Option(..., "--input", exists=True, file_okay=False),
    out: Path = typer.Option(Path("data/snapshots/fixtures"), "--out"),
) -> None:
    """Parse, validate and normalise filings into a Parquet snapshot."""
    summary = build_snapshot(input, out)
    typer.echo(f"Snapshot written to {out}")
    for key, value in summary.model_dump().items():
        typer.echo(f"  {key:<24} {value}")


if __name__ == "__main__":
    app()
