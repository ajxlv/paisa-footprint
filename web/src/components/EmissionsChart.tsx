import { useState } from 'react';
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { CompanySummary } from '../lib/api';
import { formatNumber } from '../lib/format';
import { useChartColors } from '../lib/theme';

/**
 * Scope 1 + 2 per reporting company. Linear scale stacks S1 and S2; a log axis cannot stack
 * meaningfully, so log mode shows the total as a single bar (and says so).
 */
export function EmissionsChart({ companies }: { companies: CompanySummary[] }) {
  const colors = useChartColors();
  const [log, setLog] = useState(false);
  const data = companies
    .filter((c) => c.total_t !== null && c.total_t > 0)
    .sort((a, b) => (b.total_t ?? 0) - (a.total_t ?? 0))
    .map((c) => ({
      name: (c.nse_symbol ?? c.company_name).toUpperCase(),
      full: c.company_name,
      scope1: c.scope1_t,
      scope2: c.scope2_t,
      total: c.total_t,
    }));

  return (
    <figure className="card">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <figcaption>
          <p className="font-medium">Scope 1 + Scope 2 emissions, FY2025-26 (tCO2e)</p>
          <p className="text-xs text-stone-500 dark:text-stone-400">
            {data.length} reporting companies. Companies marked "not applicable" have no bar.
          </p>
        </figcaption>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={log} onChange={(e) => setLog(e.target.checked)} />
          Log scale
        </label>
      </div>
      <div className="h-[420px] w-full">
        <ResponsiveContainer>
          <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16, top: 4, bottom: 4 }} barCategoryGap={3}>
            <CartesianGrid horizontal={false} stroke={colors.grid} />
            <XAxis
              type="number"
              scale={log ? 'log' : 'linear'}
              domain={log ? [0.01, 'auto'] : [0, 'auto']}
              allowDataOverflow={log}
              tick={{ fill: colors.text, fontSize: 11 }}
              tickFormatter={(v: number) => formatNumber(v, 2)}
              stroke={colors.grid}
            />
            <YAxis type="category" dataKey="name" width={96} tick={{ fill: colors.text, fontSize: 11 }} stroke={colors.grid} interval={0} />
            <Tooltip
              cursor={{ fill: colors.grid, opacity: 0.4 }}
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const row = payload[0].payload as (typeof data)[number];
                return (
                  <div className="rounded-md border border-stone-200 bg-white px-3 py-2 text-xs shadow-sm dark:border-stone-700 dark:bg-stone-900">
                    <p className="mb-1 font-medium">{row.full}</p>
                    <p>Scope 1: {formatNumber(row.scope1)} t</p>
                    <p>Scope 2: {formatNumber(row.scope2)} t</p>
                    <p className="font-medium">Total: {formatNumber(row.total)} t</p>
                  </div>
                );
              }}
            />
            {log ? (
              <Bar dataKey="total" name="Scope 1 + 2 (total)" fill={colors.scope1} radius={[0, 4, 4, 0]} />
            ) : (
              <>
                <Legend wrapperStyle={{ fontSize: 12, color: colors.text }} />
                <Bar dataKey="scope1" name="Scope 1" stackId="s" fill={colors.scope1} stroke={colors.surface} strokeWidth={1} />
                <Bar dataKey="scope2" name="Scope 2" stackId="s" fill={colors.scope2} stroke={colors.surface} strokeWidth={1} radius={[0, 4, 4, 0]} />
              </>
            )}
          </BarChart>
        </ResponsiveContainer>
      </div>
      {log && <p className="mt-2 text-xs text-stone-500">Log scale shows totals only: stacked segments are not meaningful on a log axis.</p>}
    </figure>
  );
}
