import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import { useApi } from '../lib/useApi';
import { formatPct } from '../lib/format';
import { ErrorBox, StatTile } from '../components/ui';

export function Home() {
  const { data, error, loading } = useApi(api.validationSummary);
  return (
    <div>
      <section className="max-w-3xl">
        <p className="text-sm font-medium text-accent-800 dark:text-accent-300">Paisa Footprint</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-5xl">How much carbon does your money finance?</h1>
        <p className="mt-6 text-lg leading-8 text-stone-600 dark:text-stone-300">
          When you own shares in a company, you finance a slice of the greenhouse gases it emits: your financed
          emissions. PCAF, the standard banks and asset managers use, sets your slice as the value you hold divided
          by the company's total value including debt (EVIC). We apply it to companies' own BRSR filings to NSE, and
          every number traces back to the filing it came from.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link to="/companies" className="btn-primary">Explore companies</Link>
          <Link to="/portfolio" className="btn-secondary">Try the portfolio calculator</Link>
        </div>
        <p className="mt-6 rounded-md border border-stone-200 bg-stone-50 px-4 py-3 text-sm text-stone-600 dark:border-stone-800 dark:bg-stone-900 dark:text-stone-400">
          Week 1 build: data from 20 real BRSR filings (FY2025-26). Mutual fund rankings coming next.
        </p>
      </section>

      <section aria-label="Snapshot statistics" className="mt-12">
        {error && <ErrorBox error={error} />}
        {loading && (
          <div className="grid gap-4 sm:grid-cols-3" aria-busy="true">
            {[0, 1, 2].map((i) => (
              <div key={i} className="card h-28 animate-pulse" />
            ))}
          </div>
        )}
        {data && (
          <div className="grid gap-4 sm:grid-cols-3">
            <StatTile label="Companies parsed" value={String(data.companies)} sub="Real BRSR XBRL filings, FY2025-26" />
            <StatTile
              label="Reporting Scope 1 + 2"
              value={formatPct(data.pct_reporting_scope12, 0)}
              sub={`${data.reporting_scope12} of ${data.companies}; the rest say "not applicable"`}
            />
            <StatTile
              label="Data issues caught"
              value={String(data.issues_total)}
              sub={`Across ${data.rules.filter((r) => r.issues > 0).length} validator rules`}
            />
          </div>
        )}
      </section>
    </div>
  );
}
