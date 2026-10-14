import { Link } from 'react-router-dom';
import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api } from '../lib/api';
import { useApi } from '../lib/useApi';
import { RULE_TEXT } from '../lib/rules';
import { useChartColors } from '../lib/theme';
import { ErrorBox, Loading, PageHeader, StatTile } from '../components/ui';
import { formatPct } from '../lib/format';

export function DataQuality() {
  const { data, error, loading } = useApi(api.validationSummary);
  const colors = useChartColors();
  return (
    <div className="space-y-10">
      <PageHeader title="Data quality">
        BRSR filings contain real reporting errors: revenue typed at the wrong scale, "MtCO2e" used to mean tonnes,
        zeros standing in for missing data. Every filing passes through validators built from errors found in these 20
        real filings. Problems are flagged and explained; only two are fixed automatically, and the rest are never
        silently corrected.
      </PageHeader>
      {loading && <Loading />}
      {error && <ErrorBox error={error} />}
      {data && (
        <>
          <section className="grid gap-4 sm:grid-cols-3" aria-label="Quality summary">
            <StatTile label="Quality ok" value={String(data.quality_flags.ok)} sub="companies, current year" />
            <StatTile label="Needs review" value={String(data.quality_flags.review)} sub="usable, but a warning or error applies" />
            <StatTile label="Excluded" value={String(data.quality_flags.excluded)} sub="no usable emissions" />
          </section>

          <figure className="card">
            <figcaption className="mb-1 font-medium">Companies flagged per rule</figcaption>
            <p className="mb-4 text-xs text-stone-500 dark:text-stone-400">
              Out of {data.companies} companies; {data.issues_total} issues in total across both filed years.
            </p>
            <div className="h-72">
              <ResponsiveContainer>
                <BarChart data={data.rules} margin={{ top: 16, left: 0, right: 8 }}>
                  <CartesianGrid vertical={false} stroke={colors.grid} />
                  <XAxis dataKey="rule_id" tick={{ fill: colors.text, fontSize: 12 }} stroke={colors.grid} />
                  <YAxis allowDecimals={false} tick={{ fill: colors.text, fontSize: 11 }} stroke={colors.grid} width={32} />
                  <Tooltip
                    cursor={{ fill: colors.grid, opacity: 0.4 }}
                    content={({ active, payload }) => {
                      if (!active || !payload?.length) return null;
                      const r = payload[0].payload as (typeof data.rules)[number];
                      return (
                        <div className="max-w-xs rounded-md border border-stone-200 bg-white px-3 py-2 text-xs shadow-sm dark:border-stone-700 dark:bg-stone-900">
                          <p className="font-medium">{r.rule_id}: {RULE_TEXT[r.rule_id]?.title}</p>
                          <p>{r.companies} companies · {r.issues} issues</p>
                        </div>
                      );
                    }}
                  />
                  <Bar dataKey="companies" name="Companies flagged" fill={colors.scope1} radius={[4, 4, 0, 0]}>
                    <LabelList dataKey="companies" position="top" fill={colors.text} fontSize={11} />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </figure>

          <section aria-labelledby="rules-h">
            <h2 id="rules-h" className="mb-4 text-xl font-semibold">The rules, with real examples</h2>
            <div className="grid gap-4 md:grid-cols-2">
              {data.rules.map((r) => (
                <article key={r.rule_id} className="card">
                  <div className="flex items-baseline justify-between gap-3">
                    <h3 className="font-semibold"><span className="font-mono">{r.rule_id}</span> · {RULE_TEXT[r.rule_id]?.title ?? r.description}</h3>
                    <span className="whitespace-nowrap text-sm tabular-nums text-stone-500">{r.companies} co. · {r.issues} {r.issues === 1 ? 'issue' : 'issues'}</span>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-stone-700 dark:text-stone-300">{RULE_TEXT[r.rule_id]?.plain}</p>
                  <p className="mt-3 rounded-md bg-stone-50 px-3 py-2 text-sm text-stone-700 dark:bg-stone-800/60 dark:text-stone-300">
                    <span className="font-medium">{r.issues > 0 ? 'Real example: ' : 'Note: '}</span>{r.example}
                  </p>
                </article>
              ))}
            </div>
          </section>

          <section aria-labelledby="cov-h" className="max-w-3xl text-sm leading-6 text-stone-700 dark:text-stone-300">
            <h2 id="cov-h" className="mb-2 text-xl font-semibold text-stone-900 dark:text-stone-100">Coverage and assurance</h2>
            <p>
              {data.reporting_scope12} of {data.companies} companies ({formatPct(data.pct_reporting_scope12, 0)}) report Scope 1 and
              Scope 2. Of those, {data.assured} ({formatPct(data.pct_assured_of_reporting, 0)}) say their figures were assured by a third
              party, which earns PCAF data-quality score 1; the rest score 2. Companies that do not report are left out and shown
              as a coverage gap, never estimated. See the <Link to="/methodology" className="underline">methodology</Link>.
            </p>
          </section>
        </>
      )}
    </div>
  );
}
