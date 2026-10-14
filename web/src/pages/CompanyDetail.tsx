import { Link, useParams } from 'react-router-dom';
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api, type CompanyYear } from '../lib/api';
import { useApi } from '../lib/useApi';
import { formatINR, formatNumber, formatSig } from '../lib/format';
import { RULE_TEXT, TRANSFORM_HINT } from '../lib/rules';
import { useChartColors } from '../lib/themeContext';
import { ErrorBox, Loading, QualityBadge, SeverityBadge, StatTile } from '../components/ui';

const FIELD_LABELS: Record<string, string> = {
  scope1_t: 'Scope 1 (tCO2e)',
  scope2_t: 'Scope 2 (tCO2e)',
  revenue_from_operations_inr: 'Revenue from operations (₹)',
  total_revenue_inr: 'Total revenue (₹)',
  intensity_reported_per_inr: 'Reported intensity (per ₹)',
};

export function CompanyDetail() {
  const { key = '' } = useParams();
  const { data, error, loading } = useApi(() => api.company(key), key);

  if (loading) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  if (!data) return null;
  const { summary, years } = data;
  const current = years.find((y) => y.is_current) ?? years[0];

  return (
    <div className="space-y-10">
      <div>
        <Link to="/companies" className="text-sm text-accent-800 hover:underline dark:text-accent-300">← All companies</Link>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">{summary.company_name}</h1>
        <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-stone-500 dark:text-stone-400">
          {summary.nse_symbol && <span>NSE: {summary.nse_symbol.toUpperCase()}</span>}
          {summary.isin && <span>ISIN: {summary.isin}</span>}
          {data.cin && <span>CIN: {data.cin}</span>}
          <QualityBadge flag={summary.quality_flag} />
        </p>
        <p className="mt-1 break-all text-xs text-stone-500">Source: {data.source_file}</p>
        {data.exclusion_reason && (
          <p className="mt-4 rounded-md bg-stone-100 px-4 py-3 text-sm dark:bg-stone-900">
            <strong>Excluded from emissions:</strong> {data.exclusion_reason}
          </p>
        )}
      </div>

      <section aria-label="Current year figures" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label={`Scope 1, ${current.fiscal_year}`} value={formatNumber(current.scope1_t)} sub="tCO2e" />
        <StatTile label={`Scope 2, ${current.fiscal_year}`} value={formatNumber(current.scope2_t)} sub="tCO2e" />
        <StatTile label="Scope 1 + 2" value={formatNumber(summary.total_t)} sub="tCO2e" />
        <StatTile
          label="Intensity"
          value={formatSig(current.intensity_t_per_crore)}
          sub={current.intensity_t_per_crore === null ? 'Withheld: revenue or emissions unusable' : 'tCO2e per ₹ crore of revenue'}
        />
      </section>

      <YearsSection years={years} />
      <ProvenancePanel years={years} />

      <section aria-labelledby="issues-h">
        <h2 id="issues-h" className="mb-3 text-lg font-semibold">Data issues ({data.issues.length})</h2>
        {data.issues.length === 0 ? (
          <p className="text-sm text-stone-600 dark:text-stone-400">No validator flagged this filing.</p>
        ) : (
          <ul className="space-y-3">
            {data.issues.map((issue, i) => (
              <li key={i} className="card">
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="font-mono font-semibold">{issue.rule_id}</span>
                  <SeverityBadge severity={issue.severity} />
                  <span className="text-stone-500">{issue.fiscal_year}</span>
                  <span className="font-medium">{RULE_TEXT[issue.rule_id]?.title}</span>
                </div>
                <p className="mt-2 text-sm">{issue.message}</p>
                <p className="mt-2 text-sm text-stone-600 dark:text-stone-400">{RULE_TEXT[issue.rule_id]?.plain ?? issue.explanation}</p>
                {issue.suggested_fix && <p className="mt-2 text-xs text-stone-500">Suggested: {issue.suggested_fix}</p>}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function YearsSection({ years }: { years: CompanyYear[] }) {
  const colors = useChartColors();
  const ordered = [...years].sort((a, b) => a.period_end.localeCompare(b.period_end));
  const hasData = ordered.some((y) => y.scope1_t !== null || y.scope2_t !== null);
  const chartData = [
    { scope: 'Scope 1', ...Object.fromEntries(ordered.map((y) => [y.fiscal_year, y.scope1_t])) },
    { scope: 'Scope 2', ...Object.fromEntries(ordered.map((y) => [y.fiscal_year, y.scope2_t])) },
  ];
  return (
    <section aria-labelledby="years-h" className="grid gap-6 lg:grid-cols-2">
      <div className="min-w-0">
        <h2 id="years-h" className="mb-3 text-lg font-semibold">Both filed years</h2>
        <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Both filed years, scrollable">
          <table className="table-base">
            <thead>
              <tr>
                <th scope="col">Year</th>
                <th scope="col" className="num">Scope 1 (t)</th>
                <th scope="col" className="num">Scope 2 (t)</th>
                <th scope="col" className="num">Revenue</th>
                <th scope="col" className="num">t / ₹ cr</th>
              </tr>
            </thead>
            <tbody>
              {[...ordered].reverse().map((y) => (
                <tr key={y.fiscal_year}>
                  <th scope="row" className="whitespace-nowrap text-left font-normal">
                    {y.fiscal_year}
                    <span className="block text-xs text-stone-500">{y.period_start} to {y.period_end}</span>
                  </th>
                  <td className="num">{formatNumber(y.scope1_t)}</td>
                  <td className="num">{formatNumber(y.scope2_t)}</td>
                  <td className="num">
                    {formatINR(y.revenue_inr_resolved)}
                    {y.revenue_corrected && <CorrectedChip />}
                  </td>
                  <td className="num">{formatSig(y.intensity_t_per_crore)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <figure className="card min-w-0">
        <figcaption className="mb-2 text-sm font-medium">Year-on-year change (tCO2e)</figcaption>
        {hasData ? (
          <div className="h-56">
            <ResponsiveContainer>
              <BarChart data={chartData} margin={{ left: 8, right: 8 }} barGap={2}>
                <CartesianGrid vertical={false} stroke={colors.grid} />
                <XAxis dataKey="scope" tick={{ fill: colors.text, fontSize: 12 }} stroke={colors.grid} />
                <YAxis tick={{ fill: colors.text, fontSize: 11 }} tickFormatter={(v: number) => formatNumber(v, 0)} stroke={colors.grid} width={72} />
                <Tooltip formatter={(v) => (typeof v === 'number' ? `${formatNumber(v)} t` : 'not reported')} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                {ordered.map((y, i) => (
                  <Bar
                    key={y.fiscal_year}
                    dataKey={y.fiscal_year}
                    fill={i === ordered.length - 1 ? colors.scope1 : colors.muted}
                    radius={[4, 4, 0, 0]}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <p className="py-8 text-sm text-stone-500">No emissions reported in either year.</p>
        )}
      </figure>
    </section>
  );
}

function CorrectedChip() {
  return (
    <span
      className="ml-1.5 inline-block rounded bg-amber-100 px-1.5 py-0.5 align-middle font-sans text-[11px] font-medium text-amber-900 dark:bg-amber-950 dark:text-amber-200"
      title="Scale corrected by rule V2-fix; see Transformation"
    >
      Corrected
    </span>
  );
}

function ProvenancePanel({ years }: { years: CompanyYear[] }) {
  return (
    <section aria-labelledby="prov-h">
      <h2 id="prov-h" className="text-lg font-semibold">Where this number comes from</h2>
      <p className="mb-4 mt-1 text-sm text-stone-600 dark:text-stone-400">
        Each figure as filed in the XBRL, with the element, context, period, raw value and unit, and the value we
        actually use. {TRANSFORM_HINT} An amber <span className="font-medium">Corrected</span> chip marks a
        revenue figure rescaled by rule V2-fix.
      </p>
      <div className="space-y-6">
        {years.map((y) => (
          <div
            key={y.fiscal_year}
            className="overflow-x-auto rounded-lg border border-stone-200 dark:border-stone-800"
            tabIndex={0}
            role="region"
            aria-label={`Provenance for ${y.fiscal_year}, scrollable`}
          >
            <table className="table-base min-w-[880px]">
              <caption className="px-3 pt-3 text-left text-sm font-medium">{y.fiscal_year}</caption>
              <thead>
                <tr>
                  <th scope="col">Figure</th>
                  <th scope="col">XBRL element</th>
                  <th scope="col">Context · period</th>
                  <th scope="col" className="num">Raw value</th>
                  <th scope="col">Raw unit</th>
                  <th scope="col" className="num">Value used</th>
                  <th scope="col">Transformation</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(y.provenance).map(([field, p]) => (
                  <tr key={field}>
                    <th scope="row" className="text-left font-normal">{FIELD_LABELS[field] ?? field}</th>
                    <td className="max-w-[15rem] break-all font-mono text-xs">{p.element}</td>
                    <td className="whitespace-nowrap text-xs">
                      {p.context_ref}
                      <span className="block text-stone-500">{p.period_start ? `${p.period_start} to ` : ''}{p.period_end}</span>
                    </td>
                    <td className="num font-mono text-xs">{p.raw_value}</td>
                    <td className="font-mono text-xs">{p.unit_raw ?? '–'}</td>
                    <td className="num font-mono text-xs">
                      {p.value_used === null || p.value_used === undefined ? '–' : formatNumber(p.value_used, 10)}
                      {p.corrected && <CorrectedChip />}
                    </td>
                    <td className="text-xs">{p.transformation}</td>
                  </tr>
                ))}
                {Object.keys(y.provenance).length === 0 && (
                  <tr><td colSpan={7} className="text-sm text-stone-500">No emissions or revenue facts filed for this year.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        ))}
      </div>
    </section>
  );
}
