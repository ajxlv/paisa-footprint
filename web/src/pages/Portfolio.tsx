import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api, type CompanySummary, type EvicIn, type HoldingIn, type PortfolioResult } from '../lib/api';
import { useApi } from '../lib/useApi';
import { INR_PER_CRORE, formatCrore, formatINR, formatNumber, formatPct, formatSig } from '../lib/format';
import { ErrorBox, IllustrativeBanner, Loading, PageHeader } from '../components/ui';

export interface Row {
  id: number;
  companyKey: string;
  valueInr: string;
  evicCrore: string;
  /** True for rows loaded from a synthetic demo portfolio; stays true until the row is removed. */
  illustrative: boolean;
}

let nextId = 1;
const emptyRow = (): Row => ({ id: nextId++, companyKey: '', valueInr: '', evicCrore: '', illustrative: false });

export function Portfolio() {
  const companies = useApi(api.companies);
  const [rows, setRows] = useState<Row[]>([emptyRow()]);
  const [result, setResult] = useState<PortfolioResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const illustrative = rows.some((r) => r.illustrative) || result?.contains_illustrative_inputs === true;

  async function loadExample() {
    setError(null);
    try {
      const demos = await api.demoPortfolios();
      const demo = demos.find((d) => d.id === 'portfolio_synthetic_a') ?? demos[0];
      if (!demo) throw new Error('No demo portfolio available');
      const index = new Map((companies.data ?? []).map((c) => [c.company_key, c]));
      const bySymbol = new Map((companies.data ?? []).map((c) => [(c.nse_symbol ?? '').toUpperCase(), c.company_key]));
      const evic = new Map(demo.evic.map((e) => [e.company_key, e.evic_inr]));
      setRows(
        demo.holdings.map((h) => {
          const key = index.has(h.isin_or_symbol) ? h.isin_or_symbol : bySymbol.get(h.isin_or_symbol.toUpperCase()) ?? h.isin_or_symbol;
          const e = evic.get(key);
          return { id: nextId++, companyKey: key, valueInr: String(h.value_inr), evicCrore: e ? String(e / INR_PER_CRORE) : '', illustrative: true };
        }),
      );
      setResult(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function compute() {
    setError(null);
    const valid = rows.filter((r) => r.companyKey && Number(r.valueInr) > 0);
    if (valid.length === 0) {
      setError('Add at least one holding with a company and a positive value.');
      return;
    }
    const holdings: HoldingIn[] = valid.map((r) => ({ isin_or_symbol: r.companyKey, value_inr: Number(r.valueInr) }));
    const evic: EvicIn[] = valid
      .filter((r) => Number(r.evicCrore) > 0)
      .map((r) => ({
        company_key: r.companyKey,
        evic_inr: Number(r.evicCrore) * INR_PER_CRORE,
        evic_source: r.illustrative ? 'illustrative demo value' : 'user-supplied',
        evic_is_illustrative: r.illustrative,
      }));
    setBusy(true);
    try {
      setResult(await api.compute(holdings, evic));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  const update = (id: number, patch: Partial<Row>) => setRows((rs) => rs.map((r) => (r.id === id ? { ...r, ...patch } : r)));

  return (
    <div className="space-y-8">
      <PageHeader title="Portfolio calculator">
        Enter holdings and each company's EVIC (enterprise value including cash, in ₹ crore). There is no real EVIC
        data in this build yet, so you supply it, or load the illustrative example.
      </PageHeader>

      {illustrative && (
        <IllustrativeBanner>
          The holdings and EVIC values in this example are made up for demonstration. Emissions come from real BRSR
          filings; the results are not a statement about any real portfolio.
        </IllustrativeBanner>
      )}

      {companies.loading && <Loading label="Loading companies…" />}
      {companies.error && <ErrorBox error={companies.error} />}
      {companies.data && (
        <HoldingsEditor
          rows={rows}
          companies={companies.data}
          onChange={update}
          onRemove={(id) => setRows((rs) => (rs.length > 1 ? rs.filter((r) => r.id !== id) : [emptyRow()]))}
        />
      )}

      <div className="flex flex-wrap gap-3">
        <button type="button" className="btn-secondary" onClick={() => setRows((rs) => [...rs, emptyRow()])}>Add holding</button>
        <button type="button" className="btn-secondary" onClick={loadExample} disabled={!companies.data}>Load illustrative example</button>
        <button type="button" className="btn-secondary" onClick={() => { setRows([emptyRow()]); setResult(null); }}>Clear</button>
        <button type="button" className="btn-primary" onClick={compute} disabled={busy}>{busy ? 'Computing…' : 'Compute'}</button>
      </div>

      {error && <div role="alert" className="text-sm text-red-700 dark:text-red-300">{error}</div>}
      {result && <Results result={result} />}
    </div>
  );
}

function HoldingsEditor({
  rows,
  companies,
  onChange,
  onRemove,
}: {
  rows: Row[];
  companies: CompanySummary[];
  onChange: (id: number, patch: Partial<Row>) => void;
  onRemove: (id: number) => void;
}) {
  return (
    <div className="overflow-x-auto rounded-lg border border-stone-200 dark:border-stone-800">
      <table className="table-base min-w-[640px]">
        <caption className="sr-only">Portfolio holdings</caption>
        <thead>
          <tr>
            <th scope="col">Company</th>
            <th scope="col">Value invested (₹)</th>
            <th scope="col">EVIC (₹ crore)</th>
            <th scope="col"><span className="sr-only">Actions</span></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={row.id}>
              <td>
                <label className="sr-only" htmlFor={`company-${row.id}`}>Company for holding {i + 1}</label>
                <select id={`company-${row.id}`} className="input" value={row.companyKey} onChange={(e) => onChange(row.id, { companyKey: e.target.value })}>
                  <option value="">Choose a company…</option>
                  {companies.map((c) => (
                    <option key={c.company_key} value={c.company_key}>
                      {c.company_name}{c.quality_flag === 'excluded' ? ' (no emissions data)' : ''}
                    </option>
                  ))}
                </select>
                {row.illustrative && <span className="mt-1 inline-block rounded bg-amber-100 px-1.5 text-[11px] text-amber-900 dark:bg-amber-950 dark:text-amber-200">illustrative</span>}
              </td>
              <td>
                <label className="sr-only" htmlFor={`value-${row.id}`}>Value invested in rupees for holding {i + 1}</label>
                <input id={`value-${row.id}`} className="input num" inputMode="decimal" value={row.valueInr} onChange={(e) => onChange(row.id, { valueInr: e.target.value })} />
                {Number(row.valueInr) > 0 && <span className="text-xs text-stone-500">{formatINR(Number(row.valueInr))}</span>}
              </td>
              <td>
                <label className="sr-only" htmlFor={`evic-${row.id}`}>EVIC in rupees crore for holding {i + 1}</label>
                <input id={`evic-${row.id}`} className="input num" inputMode="decimal" value={row.evicCrore} onChange={(e) => onChange(row.id, { evicCrore: e.target.value })} />
              </td>
              <td>
                <button type="button" className="text-sm text-stone-500 underline hover:text-red-700" onClick={() => onRemove(row.id)} aria-label={`Remove holding ${i + 1}`}>
                  Remove
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Results({ result }: { result: PortfolioResult }) {
  const lowCoverage = result.coverage_pct < 100;
  return (
    <section aria-labelledby="results-h" className="space-y-6">
      <h2 id="results-h" className="text-xl font-semibold">Results</h2>
      <div className="grid gap-4 md:grid-cols-3">
        <div className={`card md:row-span-2 ${lowCoverage ? 'border-amber-400 dark:border-amber-700' : ''}`}>
          <p className="text-sm text-stone-500 dark:text-stone-400">Coverage</p>
          <p className="mt-1 text-5xl font-semibold tabular-nums">{formatPct(result.coverage_pct)}</p>
          <p className="mt-2 text-sm text-stone-600 dark:text-stone-400">
            {formatCrore(result.covered_value_inr)} of {formatCrore(result.total_value_inr)} has reported emissions and an EVIC.
            {lowCoverage && ' Uncovered holdings are listed below and are not estimated.'}
          </p>
        </div>
        <Metric label="Financed emissions" value={formatNumber(result.financed_emissions_t, 4)} unit="tCO2e" />
        <Metric label="Carbon footprint" value={formatSig(result.carbon_footprint_t_per_crore, 6)} unit="tCO2e per ₹ crore invested" />
        <Metric
          label="WACI"
          value={formatSig(result.waci_t_per_crore_revenue, 6)}
          unit={`tCO2e per ₹ crore revenue · covers ${formatPct(result.waci_coverage_pct)} of value${
            result.waci_data_quality == null ? '' : ` · DQ ${result.waci_data_quality.toFixed(2)}`
          }`}
        />
        <Metric label="PCAF data quality" value={result.pcaf_data_quality === null ? '–' : result.pcaf_data_quality.toFixed(2)} unit="1 = assured, 2 = not assured (lower is better)" />
      </div>

      <div className="overflow-x-auto rounded-lg border border-stone-200 dark:border-stone-800">
        <table className="table-base min-w-[760px]">
          <caption className="px-3 pt-3 text-left text-sm font-medium">Per-holding breakdown (expand a row for the formula)</caption>
          <thead>
            <tr>
              <th scope="col">Company</th>
              <th scope="col" className="num">Value</th>
              <th scope="col" className="num">EVIC</th>
              <th scope="col" className="num">Attribution</th>
              <th scope="col" className="num">S1 + S2 (t)</th>
              <th scope="col" className="num">Financed (t)</th>
              <th scope="col" className="num">DQ</th>
            </tr>
          </thead>
          <tbody>
            {result.holdings.map((h, i) => (
              <tr key={`${h.company_key}-${i}`}>
                <td>
                  <details>
                    <summary className="cursor-pointer font-medium">{h.company_name}</summary>
                    <div className="mt-2 space-y-1 text-xs text-stone-600 dark:text-stone-400">
                      <p className="font-mono">attribution = value / EVIC = {formatINR(h.value_inr)} / {formatINR(h.evic_inr)} = {formatSig(h.attribution, 6)}</p>
                      <p className="font-mono">financed = {formatSig(h.attribution, 6)} × ({formatNumber(h.scope1_t)} + {formatNumber(h.scope2_t)}) = {formatNumber(h.financed_emissions_t, 6)} t</p>
                      <p>Emissions: {h.fiscal_year} BRSR · EVIC: {h.evic_source}{h.evic_is_illustrative ? ' (illustrative)' : ''}</p>
                      {!h.in_waci && <p>Not in WACI: {h.waci_exclusion_reason}</p>}
                      {h.revenue_corrected && (
                        <p className="text-amber-800 dark:text-amber-300">
                          Revenue corrected for scale (rule V2-fix); WACI data quality capped at 2.
                        </p>
                      )}
                      <Link to={`/companies/${h.company_key}`} className="underline">Where the emissions come from →</Link>
                    </div>
                  </details>
                </td>
                <td className="num">{formatINR(h.value_inr)}</td>
                <td className="num">{formatCrore(h.evic_inr, 0)}</td>
                <td className="num">{formatSig(h.attribution, 4)}</td>
                <td className="num">{formatNumber(h.scope1_t + h.scope2_t)}</td>
                <td className="num font-medium">{formatNumber(h.financed_emissions_t, 4)}</td>
                <td className="num">{h.pcaf_data_quality}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div>
        <h3 className="mb-2 font-semibold">Uncovered holdings ({result.uncovered.length})</h3>
        {result.uncovered.length === 0 ? (
          <p className="text-sm text-stone-600 dark:text-stone-400">Every holding is covered.</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {result.uncovered.map((u, i) => (
              <li key={i} className="rounded-md border border-stone-200 px-3 py-2 dark:border-stone-800">
                <span className="font-medium">{u.isin_or_symbol}</span> · {formatINR(u.value_inr)}
                <span className="block text-stone-600 dark:text-stone-400">{u.reason}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

function Metric({ label, value, unit }: { label: string; value: string; unit: string }) {
  return (
    <div className="card">
      <p className="text-sm text-stone-500 dark:text-stone-400">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
      <p className="mt-1 text-xs text-stone-500 dark:text-stone-400">{unit}</p>
    </div>
  );
}
