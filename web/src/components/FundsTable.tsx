import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import type { FundResult } from '../lib/api';
import { formatPct, formatSig } from '../lib/format';

type SortKey = 'rank' | 'scheme_name' | 'amc' | 'carbon_footprint_t_per_crore' | 'waci_t_per_crore_revenue' | 'coverage_pct' | 'pcaf_data_quality';

const COLUMNS: { key: SortKey; label: string; numeric?: boolean }[] = [
  { key: 'rank', label: 'Rank', numeric: true },
  { key: 'scheme_name', label: 'Fund' },
  { key: 'amc', label: 'AMC' },
  { key: 'carbon_footprint_t_per_crore', label: 'Footprint (t / ₹ cr)', numeric: true },
  { key: 'waci_t_per_crore_revenue', label: 'WACI', numeric: true },
  { key: 'coverage_pct', label: 'Coverage', numeric: true },
  { key: 'pcaf_data_quality', label: 'DQ', numeric: true },
];

/** Sortable fund table. Coverage sits beside every footprint; unranked funds sort last. */
export function FundsTable({ funds, linkBase, caption }: { funds: FundResult[]; linkBase: string; caption: string }) {
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: 'rank', dir: 1 });
  const rows = useMemo(() => [...funds].sort((a, b) => compare(a[sort.key], b[sort.key], sort.dir)), [funds, sort]);
  const toggle = (key: SortKey) => setSort((s) => (s.key === key ? { key, dir: s.dir === 1 ? -1 : 1 } : { key, dir: 1 }));
  return (
    <div className="overflow-x-auto rounded-lg border border-stone-200 dark:border-stone-800">
      <table className="table-base min-w-[860px]">
        <caption className="px-3 pt-3 text-left text-sm font-medium">{caption}</caption>
        <thead>
          <tr>
            {COLUMNS.map((col) => (
              <th key={col.key} scope="col" className={col.numeric ? 'num' : undefined}
                aria-sort={sort.key === col.key ? (sort.dir === 1 ? 'ascending' : 'descending') : 'none'}>
                <button type="button" onClick={() => toggle(col.key)} className="inline-flex items-center gap-1 font-medium">
                  {col.label}
                  <span aria-hidden="true" className="text-xs">{sort.key === col.key ? (sort.dir === 1 ? '▲' : '▼') : ''}</span>
                </button>
              </th>
            ))}
            <th scope="col">As of</th>
            <th scope="col">Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((f) => (
            <tr key={f.fund_key}>
              <td className="num">{f.rank ?? '–'}</td>
              <td>
                <Link to={`${linkBase}/${f.fund_key}`} className="font-medium text-accent-900 hover:underline dark:text-accent-300">
                  {f.scheme_name}
                </Link>
              </td>
              <td>{f.amc}</td>
              <td className="num font-medium">{formatSig(f.carbon_footprint_t_per_crore)}</td>
              <td className="num">{formatSig(f.waci_t_per_crore_revenue)}</td>
              <td className={`num ${f.coverage_pct < 50 ? 'text-amber-800 dark:text-amber-300' : ''}`}>{formatPct(f.coverage_pct)}</td>
              <td className="num">{f.pcaf_data_quality == null ? '–' : f.pcaf_data_quality.toFixed(2)}</td>
              <td className="whitespace-nowrap">{f.as_of_date ?? '–'}</td>
              <td>
                {f.status === 'ranked' ? (
                  <span className="text-green-800 dark:text-green-300">ranked</span>
                ) : (
                  <span className="rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-900 dark:bg-amber-950 dark:text-amber-200">{f.status}</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function compare(a: unknown, b: unknown, dir: 1 | -1): number {
  if (a === null || a === undefined) return b === null || b === undefined ? 0 : 1;
  if (b === null || b === undefined) return -1;
  if (typeof a === 'number' && typeof b === 'number') return (a - b) * dir;
  return String(a).localeCompare(String(b)) * dir;
}
