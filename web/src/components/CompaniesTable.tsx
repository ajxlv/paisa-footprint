import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import type { CompanySummary } from '../lib/api';
import { formatNumber, formatSig } from '../lib/format';
import { QualityBadge } from './ui';

type SortKey = 'company_name' | 'fiscal_year' | 'scope1_t' | 'scope2_t' | 'total_t' | 'intensity_t_per_crore' | 'quality_flag';

const COLUMNS: { key: SortKey; label: string; numeric?: boolean }[] = [
  { key: 'company_name', label: 'Company' },
  { key: 'fiscal_year', label: 'FY' },
  { key: 'scope1_t', label: 'Scope 1 (t)', numeric: true },
  { key: 'scope2_t', label: 'Scope 2 (t)', numeric: true },
  { key: 'total_t', label: 'Total (t)', numeric: true },
  { key: 'intensity_t_per_crore', label: 'tCO2e / ₹ cr revenue', numeric: true },
  { key: 'quality_flag', label: 'Data quality' },
];

/** Sortable, searchable company table. Missing values always sort last and show as "–". */
export function CompaniesTable({ companies }: { companies: CompanySummary[] }) {
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: 'company_name', dir: 1 });

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = companies.filter(
      (c) => !q || c.company_name.toLowerCase().includes(q) || (c.nse_symbol ?? '').toLowerCase().includes(q),
    );
    return [...filtered].sort((a, b) => compare(a[sort.key], b[sort.key], sort.dir));
  }, [companies, query, sort]);

  const toggle = (key: SortKey) =>
    setSort((s) => (s.key === key ? { key, dir: s.dir === 1 ? -1 : 1 } : { key, dir: key === 'company_name' ? 1 : -1 }));

  return (
    <div>
      <label className="mb-3 block max-w-sm text-sm">
        <span className="mb-1 block text-stone-600 dark:text-stone-400">Search companies</span>
        <input
          type="search"
          className="input"
          placeholder="Name or NSE symbol"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </label>
      <div className="overflow-x-auto rounded-lg border border-stone-200 dark:border-stone-800">
        <table className="table-base min-w-[760px]">
          <caption className="sr-only">Companies with Scope 1 and Scope 2 emissions, sortable by column</caption>
          <thead>
            <tr>
              {COLUMNS.map((col) => (
                <th
                  key={col.key}
                  scope="col"
                  className={col.numeric ? 'num' : undefined}
                  aria-sort={sort.key === col.key ? (sort.dir === 1 ? 'ascending' : 'descending') : 'none'}
                >
                  <button type="button" onClick={() => toggle(col.key)} className="inline-flex items-center gap-1 font-medium">
                    {col.label}
                    <span aria-hidden="true" className="text-xs">{sort.key === col.key ? (sort.dir === 1 ? '▲' : '▼') : ''}</span>
                  </button>
                </th>
              ))}
              <th scope="col">Assured</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <tr key={c.company_key} className="hover:bg-stone-50 dark:hover:bg-stone-900/60">
                <td>
                  <Link to={`/companies/${c.company_key}`} className="font-medium text-accent-900 underline-offset-2 hover:underline dark:text-accent-300">
                    {c.company_name}
                  </Link>
                  {c.nse_symbol && <span className="ml-2 text-xs text-stone-500">{c.nse_symbol.toUpperCase()}</span>}
                </td>
                <td className="whitespace-nowrap">{c.fiscal_year}</td>
                <td className="num">{formatNumber(c.scope1_t)}</td>
                <td className="num">{formatNumber(c.scope2_t)}</td>
                <td className="num font-medium">{formatNumber(c.total_t)}</td>
                <td className="num">{formatSig(c.intensity_t_per_crore)}</td>
                <td><QualityBadge flag={c.quality_flag} /></td>
                <td aria-label={c.assured === true ? 'assured' : c.assured === false ? 'not assured' : 'assurance not filed'}>
                  {c.assured === true ? '✓' : '–'}
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={8} className="py-6 text-center text-stone-500">No companies match "{query}".</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-stone-500 dark:text-stone-400">
        "–" means not reported (never zero). Intensity is withheld where revenue fails validation (rule V2).
      </p>
    </div>
  );
}

function compare(a: unknown, b: unknown, dir: 1 | -1): number {
  if (a === null || a === undefined) return b === null || b === undefined ? 0 : 1;
  if (b === null || b === undefined) return -1;
  if (typeof a === 'number' && typeof b === 'number') return (a - b) * dir;
  return String(a).localeCompare(String(b)) * dir;
}
