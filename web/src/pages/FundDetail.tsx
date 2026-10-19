import { Link, useParams } from 'react-router-dom';
import { fundsApi } from '../lib/api';
import { useApi } from '../lib/useApi';
import { formatCrore, formatINR, formatNumber, formatPct, formatSig } from '../lib/format';
import { ErrorBox, IllustrativeBanner, Loading, StatTile } from '../components/ui';

export function FundDetail({ illustrative = false }: { illustrative?: boolean }) {
  const { key = '' } = useParams();
  const load = illustrative ? () => fundsApi.demoFund(key) : () => fundsApi.fund(key);
  const { data, error, loading } = useApi(load, `${illustrative}-${key}`);
  if (loading) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  if (!data) return null;

  return (
    <div className="space-y-10">
      <div>
        <Link to="/funds" className="text-sm text-accent-800 hover:underline dark:text-accent-300">← All funds</Link>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">{data.scheme_name}</h1>
        <p className="mt-2 text-sm text-stone-500 dark:text-stone-400">
          {data.amc} · as of {data.as_of_date ?? 'unknown date'} · source {data.source_file}
        </p>
      </div>
      {(data.illustrative || data.contains_illustrative_inputs) && (
        <IllustrativeBanner>This fund and its holdings are synthetic; EVIC values are illustrative.</IllustrativeBanner>
      )}
      {data.status !== 'ranked' && (
        <p className="rounded-md border border-amber-400 bg-amber-50 px-4 py-3 text-sm text-amber-950 dark:border-amber-700 dark:bg-amber-950/50 dark:text-amber-100">
          <strong>{data.status === 'insufficient coverage' ? 'Insufficient coverage:' : 'Not ranked:'}</strong> only{' '}
          {formatPct(data.coverage_pct)} of this fund's equity value has reported emissions and an EVIC, so it is not ranked.
          The footprint below describes only the covered part.
        </p>
      )}

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-label="Fund metrics">
        <StatTile label="Coverage" value={formatPct(data.coverage_pct)} sub={`of ${formatCrore(data.equity_value_inr)} equity`} />
        <StatTile label="Carbon footprint" value={formatSig(data.carbon_footprint_t_per_crore, 5)} sub="tCO2e per ₹ crore invested (covered part)" />
        <StatTile label="WACI" value={formatSig(data.waci_t_per_crore_revenue, 5)} sub="tCO2e per ₹ crore revenue" />
        <StatTile label="PCAF data quality" value={data.pcaf_data_quality == null ? '–' : data.pcaf_data_quality.toFixed(2)} sub="1 = assured, 2 = not assured" />
      </section>

      <section aria-labelledby="top-h">
        <h2 id="top-h" className="mb-3 text-lg font-semibold">Top contributors to financed emissions</h2>
        <div className="overflow-x-auto rounded-lg border border-stone-200 dark:border-stone-800">
          <table className="table-base min-w-[640px]">
            <thead>
              <tr>
                <th scope="col">Company</th>
                <th scope="col" className="num">Value</th>
                <th scope="col" className="num">Attribution</th>
                <th scope="col" className="num">Financed (t)</th>
                <th scope="col" className="num">Share</th>
              </tr>
            </thead>
            <tbody>
              {data.top_contributors.map((h) => (
                <tr key={h.company_key}>
                  <td><Link to={`/companies/${h.company_key}`} className="hover:underline">{h.company_name}</Link></td>
                  <td className="num">{formatINR(h.value_inr)}</td>
                  <td className="num">{formatSig(h.attribution, 4)}</td>
                  <td className="num font-medium">{formatNumber(h.financed_emissions_t, 4)}</td>
                  <td className="num">{data.financed_emissions_t > 0 ? formatPct((h.financed_emissions_t / data.financed_emissions_t) * 100) : '–'}</td>
                </tr>
              ))}
              {data.top_contributors.length === 0 && (
                <tr><td colSpan={5} className="text-sm text-stone-500">No covered holdings.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-labelledby="unc-h">
        <h2 id="unc-h" className="mb-3 text-lg font-semibold">Uncovered holdings ({data.uncovered.length})</h2>
        <ul className="space-y-2 text-sm">
          {data.uncovered.map((u, i) => (
            <li key={i} className="rounded-md border border-stone-200 px-3 py-2 dark:border-stone-800">
              <span className="font-medium">{u.isin_or_symbol}</span> · {formatINR(u.value_inr)}
              <span className="block text-stone-600 dark:text-stone-400">{u.reason}</span>
            </li>
          ))}
          {data.uncovered.length === 0 && <li className="text-stone-600 dark:text-stone-400">Every equity holding is covered.</li>}
        </ul>
        {data.non_equity_value_inr > 0 && (
          <p className="mt-3 text-sm text-stone-600 dark:text-stone-400">
            Plus {formatCrore(data.non_equity_value_inr)} in debt, cash and other non-equity lines, which are not attributed.
          </p>
        )}
      </section>

      {data.issues.length > 0 && (
        <section aria-labelledby="fi-h">
          <h2 id="fi-h" className="mb-3 text-lg font-semibold">Portfolio file checks</h2>
          <ul className="space-y-2 text-sm">
            {data.issues.map((i, n) => (
              <li key={n} className="rounded-md border-l-4 border-amber-500 bg-stone-50 px-3 py-2 dark:bg-stone-900">
                <span className="font-mono font-semibold">{i.rule_id}</span> {i.message}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
