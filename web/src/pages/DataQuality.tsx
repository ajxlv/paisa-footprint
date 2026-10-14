import { Link } from 'react-router-dom';
import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api, type RuleSummary } from '../lib/api';
import { useApi } from '../lib/useApi';
import { RULE_KIND, RULE_TEXT } from '../lib/rules';
import { useChartColors } from '../lib/theme';
import { ErrorBox, Loading, PageHeader, StatTile } from '../components/ui';
import { formatPct } from '../lib/format';

export function DataQuality() {
  const { data, error, loading } = useApi(api.validationSummary);
  const colors = useChartColors();
  if (loading) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  if (!data) return null;

  const problemRules = data.rules.filter((r) => (RULE_KIND[r.rule_id] ?? 'problem') === 'problem');
  const infoRules = data.rules.filter((r) => RULE_KIND[r.rule_id] === 'info');

  return (
    <div className="space-y-12">
      <PageHeader title="Data quality">
        BRSR filings contain real reporting errors: revenue typed at the wrong scale, zeros standing in for missing
        data, figures that jump implausibly. Every filing passes through validators built from errors found in these
        20 real filings. <strong>Problems</strong> need a human to check them; <strong>informational notes</strong>{' '}
        record something we handle by design and are not problems.
      </PageHeader>

      <section className="grid gap-4 sm:grid-cols-3" aria-label="Quality summary">
        <StatTile label="Data problems" value={String(data.issues_problems)} sub="errors and warnings, both filed years" />
        <StatTile label="Companies with problems" value={String(data.companies_with_problems)} sub={`of ${data.companies} parsed`} />
        <StatTile label="Informational notes" value={String(data.issues_info)} sub="handled by design; not problems" />
      </section>

      <section aria-labelledby="problems-h" className="space-y-5">
        <div>
          <h2 id="problems-h" className="flex items-center gap-2 text-xl font-semibold">
            <span aria-hidden="true" className="inline-block h-3 w-3 rounded-full bg-amber-500" />
            Problems
          </h2>
          <p className="mt-1 text-sm text-stone-600 dark:text-stone-400">
            Severity error or warning. Flagged and explained, never silently corrected.
          </p>
        </div>
        <figure className="card">
          <figcaption className="mb-4 text-sm font-medium">Problems per rule (issues across both filed years)</figcaption>
          <div className="h-60">
            <ResponsiveContainer>
              <BarChart data={problemRules} margin={{ top: 16, left: 0, right: 8 }}>
                <CartesianGrid vertical={false} stroke={colors.grid} />
                <XAxis dataKey="rule_id" tick={{ fill: colors.text, fontSize: 12 }} stroke={colors.grid} />
                <YAxis allowDecimals={false} tick={{ fill: colors.text, fontSize: 11 }} stroke={colors.grid} width={32} />
                <Tooltip
                  cursor={{ fill: colors.grid, opacity: 0.4 }}
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null;
                    const r = payload[0].payload as RuleSummary;
                    return (
                      <div className="max-w-xs rounded-md border border-stone-200 bg-white px-3 py-2 text-xs shadow-sm dark:border-stone-700 dark:bg-stone-900">
                        <p className="font-medium">{r.rule_id}: {RULE_TEXT[r.rule_id]?.title}</p>
                        <p>{r.problems} problems · {r.companies} companies</p>
                      </div>
                    );
                  }}
                />
                <Bar dataKey="problems" name="Problems" fill={colors.scope1} radius={[4, 4, 0, 0]}>
                  <LabelList dataKey="problems" position="top" fill={colors.text} fontSize={11} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </figure>
        <RuleCards rules={problemRules} kind="problem" />
      </section>

      <section aria-labelledby="info-h" className="space-y-5">
        <div>
          <h2 id="info-h" className="flex items-center gap-2 text-xl font-semibold">
            <span aria-hidden="true" className="inline-block h-3 w-3 rounded-full bg-sky-500" />
            Informational notes
          </h2>
          <p className="mt-1 text-sm text-stone-600 dark:text-stone-400">
            Severity info. Recorded so every transformation is visible; these do not count as problems.
          </p>
        </div>
        <RuleCards rules={infoRules} kind="info" />
      </section>

      <section aria-labelledby="cov-h" className="max-w-3xl text-sm leading-6 text-stone-700 dark:text-stone-300">
        <h2 id="cov-h" className="mb-2 text-xl font-semibold text-stone-900 dark:text-stone-100">Coverage and assurance</h2>
        <p>
          {data.reporting_scope12} of {data.companies} companies ({formatPct(data.pct_reporting_scope12, 0)}) report Scope 1 and
          Scope 2. Of those, {data.assured} ({formatPct(data.pct_assured_of_reporting, 0)}) say their GHG figures were assured by a
          third party, which earns PCAF data-quality score 1; the rest score 2. Companies that do not report are left out and shown
          as a coverage gap, never estimated. See the <Link to="/methodology" className="underline">methodology</Link>.
        </p>
      </section>
    </div>
  );
}

function RuleCards({ rules, kind }: { rules: RuleSummary[]; kind: 'problem' | 'info' }) {
  const border = kind === 'problem' ? 'border-l-amber-500' : 'border-l-sky-500';
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {rules.map((r) => {
        const count = kind === 'problem' ? r.problems : r.info;
        return (
          <article key={r.rule_id} className={`card border-l-4 ${border}`}>
            <div className="flex items-baseline justify-between gap-3">
              <h3 className="font-semibold">
                <span className="font-mono">{r.rule_id}</span> · {RULE_TEXT[r.rule_id]?.title ?? r.description}
              </h3>
              <span className="whitespace-nowrap text-sm tabular-nums text-stone-500">
                {count} {kind === 'problem' ? (count === 1 ? 'problem' : 'problems') : count === 1 ? 'note' : 'notes'} · {r.companies} co.
              </span>
            </div>
            <p className="mt-2 text-sm leading-6 text-stone-700 dark:text-stone-300">{RULE_TEXT[r.rule_id]?.plain}</p>
            {kind === 'info' && r.problems > 0 && (
              <p className="mt-2 text-xs text-amber-800 dark:text-amber-300">Also raised {r.problems} warning(s) on this rule.</p>
            )}
            <p className="mt-3 rounded-md bg-stone-50 px-3 py-2 text-sm text-stone-700 dark:bg-stone-800/60 dark:text-stone-300">
              <span className="font-medium">{r.issues > 0 ? 'Real example: ' : 'Note: '}</span>
              {r.example}
            </p>
          </article>
        );
      })}
    </div>
  );
}
