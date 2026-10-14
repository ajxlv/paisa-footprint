"""`pf` command-line interface."""

import csv
from collections import Counter
from datetime import date, datetime
from pathlib import Path

import typer

from pf_core.brsr.fetch import fetch_brsr
from pf_core.brsr.parser import parse_directory, parse_file
from pf_core.brsr.validators import RULE_DESCRIPTIONS, validate
from pf_core.funds.ingest import (
    parse_amc_dir,
    rank_snapshot_funds,
    write_funds,
    write_rankings,
)
from pf_core.pcaf.engine import compute_portfolio
from pf_core.pcaf.evic import load_evic_real
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
    evic: Path | None = typer.Option(
        None, exists=True, dir_okay=False, help="Illustrative EVIC CSV (company_key,evic_inr,...)."
    ),
    evic_real: Path | None = typer.Option(
        None,
        "--evic-real",
        exists=True,
        dir_okay=False,
        help="Real EVIC CSV (data_templates/evic_template.csv); overrides --evic per company.",
    ),
    snapshot: Path = typer.Option(Path("data/snapshots/fixtures"), exists=True, file_okay=False),
    out: Path = typer.Option(Path("portfolio_result.json"), help="JSON output path."),
) -> None:
    """Compute PCAF financed emissions for a portfolio CSV."""
    if evic is None and evic_real is None:
        raise typer.BadParameter("Give --evic (illustrative) and/or --evic-real (real data).")
    snap = load_snapshot(snapshot)
    emissions = emissions_from_snapshot(snap)
    financials = load_evic_csv(evic) if evic else {}
    if evic_real is not None:
        fy_end = {k: e.period_end for k, e in emissions.items() if e.period_end is not None}
        real, evic_issues = load_evic_real(evic_real, fy_end)
        financials.update(real)
        for issue in evic_issues:
            label = f"EVIC {issue.severity.upper()} {issue.rule_id} {issue.company_key}"
            typer.echo(f"{label}: {issue.message}")
    holdings = load_portfolio_csv(portfolio, company_index(snap))
    result = compute_portfolio(holdings, emissions, financials)
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


@app.command("fetch-brsr")
def fetch_brsr_cmd(
    out: Path = typer.Option(Path("data/raw/brsr"), "--out", help="Where XBRL files are saved."),
    from_: str = typer.Option("2022-01-01", "--from", help="First submission date, YYYY-MM-DD."),
    to: str = typer.Option("", "--to", help="Last submission date (default: today)."),
    source: str = typer.Option("api", "--source", help="'api' (full history) or 'rss' (recent)."),
) -> None:
    """Download BRSR XBRL filings from NSE (run on a laptop: NSE blocks cloud servers)."""
    if source not in ("api", "rss"):
        raise typer.BadParameter("--source must be 'api' or 'rss'")
    start = datetime.strptime(from_, "%Y-%m-%d").date()
    end = datetime.strptime(to, "%Y-%m-%d").date() if to else date.today()
    summary = fetch_brsr(out, start, end, source="api" if source == "api" else "rss")
    typer.echo(f"Links found        {summary.links_found}")
    typer.echo(f"Downloaded         {summary.downloaded}")
    typer.echo(f"Already on disk    {summary.skipped_existing}")
    typer.echo(f"Failed             {summary.failed}")
    for url, reason in summary.failures.items():
        typer.echo(f"  FAILED {url}: {reason}")
    typer.echo(
        f"Manifest: {out / 'manifest.csv'}  Response schema: {out / '_response_schema.json'}"
    )


@app.command("ingest-funds")
def ingest_funds_cmd(
    input: Path = typer.Option(Path("data/raw/amc"), "--input", exists=True, file_okay=False),
    out: Path = typer.Option(..., "--out", help="e.g. data/snapshots/2026-10/funds.parquet"),
) -> None:
    """Parse AMC portfolio workbooks (data/raw/amc/<amc>/<YYYY-MM>.xlsx) into funds.parquet."""
    portfolios, issues, failures = parse_amc_dir(input)
    write_funds(portfolios, issues, out)
    typer.echo(f"Schemes parsed: {len(portfolios)}   files failed: {len(failures)}")
    for name, reason in failures.items():
        typer.echo(f"  FAILED {name}: {reason}")
    for p in portfolios:
        tag = " [ILLUSTRATIVE]" if p.illustrative else ""
        typer.echo(f"  {p.amc} | {p.scheme_name} | {p.as_of_date} | {len(p.holdings)} lines{tag}")
    for issue in issues:
        typer.echo(f"  {issue.rule_id} {issue.fund_key}: {issue.message}")
    typer.echo(f"Written {out}")


@app.command("rank-funds")
def rank_funds_cmd(
    snapshot: Path = typer.Option(..., exists=True, file_okay=False, help="Holds funds.parquet"),
    evic: Path | None = typer.Option(None, exists=True, dir_okay=False),
    evic_real: Path | None = typer.Option(None, "--evic-real", exists=True, dir_okay=False),
) -> None:
    """Rank funds by footprint, with coverage beside every number."""
    if evic is None and evic_real is None:
        raise typer.BadParameter("Give --evic (illustrative) and/or --evic-real (real data).")
    financials = load_evic_csv(evic) if evic else {}
    if evic_real is not None:
        financials.update(load_evic_real(evic_real)[0])
    results = rank_snapshot_funds(snapshot, financials)
    path = write_rankings(results, snapshot)
    typer.echo(f"{'rank':>4}  {'fund':<40} {'t/₹cr':>9} {'WACI':>9} {'cover':>6} {'DQ':>4}  status")
    for r in sorted(results, key=lambda r: (r.illustrative, r.rank is None, r.rank or 0)):
        fp = (
            f"{r.carbon_footprint_t_per_crore:9.3f}"
            if r.carbon_footprint_t_per_crore
            else f"{'–':>9}"
        )
        waci = f"{r.waci_t_per_crore_revenue:9.3f}" if r.waci_t_per_crore_revenue else f"{'–':>9}"
        dq = f"{r.pcaf_data_quality:4.2f}" if r.pcaf_data_quality else f"{'–':>4}"
        tag = " [ILLUSTRATIVE]" if r.contains_illustrative_inputs else ""
        rank = str(r.rank) if r.rank else "–"
        typer.echo(
            f"{rank:>4}  {r.scheme_name[:40]:<40} {fp} {waci} {r.coverage_pct:5.1f}% {dq}  "
            f"{r.status}{tag}"
        )
    typer.echo(f"Rankings written to {path}")


if __name__ == "__main__":
    app()
