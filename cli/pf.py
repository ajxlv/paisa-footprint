"""`pf` command-line interface."""

import csv
from collections import Counter
from pathlib import Path

import typer

from pf_core.brsr.parser import parse_directory, parse_file
from pf_core.brsr.validators import RULE_DESCRIPTIONS, validate
from pf_core.pcaf.engine import compute_portfolio
from pf_core.pcaf.inputs import (
    company_index,
    emissions_from_snapshot,
    load_evic_csv,
    load_portfolio_csv,
)
from pf_core.snapshot import build_snapshot, load_snapshot

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


@app.command()
def compute(
    portfolio: Path = typer.Option(
        ..., exists=True, dir_okay=False, help="isin_or_symbol,value_inr"
    ),
    evic: Path = typer.Option(..., exists=True, dir_okay=False, help="company_key,evic_inr,..."),
    snapshot: Path = typer.Option(Path("data/snapshots/fixtures"), exists=True, file_okay=False),
    out: Path = typer.Option(Path("portfolio_result.json"), help="JSON output path."),
) -> None:
    """Compute PCAF financed emissions for a portfolio CSV."""
    snap = load_snapshot(snapshot)
    holdings = load_portfolio_csv(portfolio, company_index(snap))
    result = compute_portfolio(holdings, emissions_from_snapshot(snap), load_evic_csv(evic))
    out.write_text(result.model_dump_json(indent=2), encoding="utf-8")

    if result.contains_illustrative_inputs:
        typer.echo("!! ILLUSTRATIVE INPUTS: results use made-up EVIC, not real market data !!")
    typer.echo(f"{'company':<46} {'value ₹':>16} {'attribution':>12} {'financed t':>12} DQ")
    for h in result.holdings:
        typer.echo(
            f"{h.company_name[:46]:<46} {h.value_inr:>16,.0f} {h.attribution:>12.6g} "
            f"{h.financed_emissions_t:>12,.4f} {h.pcaf_data_quality}"
        )
    for u in result.uncovered:
        typer.echo(f"UNCOVERED {u.isin_or_symbol} (₹{u.value_inr:,.0f}): {u.reason}")
    typer.echo(f"Financed emissions   {result.financed_emissions_t:,.4f} tCO2e")
    typer.echo(f"Coverage             {result.coverage_pct:.1f}% of ₹{result.total_value_inr:,.0f}")
    if result.carbon_footprint_t_per_crore is not None:
        typer.echo(f"Carbon footprint     {result.carbon_footprint_t_per_crore:,.4f} tCO2e / ₹ cr")
    if result.waci_t_per_crore_revenue is not None:
        typer.echo(f"WACI                 {result.waci_t_per_crore_revenue:,.4f} tCO2e / ₹ cr rev")
    if result.pcaf_data_quality is not None:
        typer.echo(f"PCAF data quality    {result.pcaf_data_quality:.2f}")
    typer.echo(f"JSON written to {out}")


if __name__ == "__main__":
    app()
