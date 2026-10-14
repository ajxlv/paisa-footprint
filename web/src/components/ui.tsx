import type { ReactNode } from 'react';
import type { QualityFlag } from '../lib/api';

export function Loading({ label = 'Loading…' }: { label?: string }) {
  return (
    <p role="status" className="py-10 text-sm text-stone-500 dark:text-stone-400">
      {label}
    </p>
  );
}

export function ErrorBox({ error }: { error: string }) {
  return (
    <div role="alert" className="rounded-md border border-red-300 bg-red-50 p-4 text-sm text-red-900 dark:border-red-900 dark:bg-red-950/50 dark:text-red-200">
      <p className="font-medium">Could not load data from the API.</p>
      <p className="mt-1">{error}</p>
      <p className="mt-2 text-red-800/80 dark:text-red-300/80">
        Is the API running? Start it with <code>uvicorn api.main:app</code>.
      </p>
    </div>
  );
}

const FLAG_STYLE: Record<QualityFlag, string> = {
  ok: 'bg-green-100 text-green-900 dark:bg-green-950 dark:text-green-200',
  review: 'bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200',
  excluded: 'bg-stone-200 text-stone-700 dark:bg-stone-800 dark:text-stone-300',
};
const FLAG_ICON: Record<QualityFlag, string> = { ok: '✓', review: '!', excluded: '–' };

export function QualityBadge({ flag }: { flag: QualityFlag }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${FLAG_STYLE[flag]}`}>
      <span aria-hidden="true">{FLAG_ICON[flag]}</span>
      {flag}
    </span>
  );
}

export function IllustrativeBanner({ children }: { children?: ReactNode }) {
  return (
    <div role="note" className="rounded-md border border-amber-400 bg-amber-50 px-4 py-3 text-sm text-amber-950 dark:border-amber-700 dark:bg-amber-950/50 dark:text-amber-100">
      <p className="font-semibold">Illustrative data, not real market data</p>
      {children && <p className="mt-1">{children}</p>}
    </div>
  );
}

export function StatTile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="card">
      <p className="text-sm text-stone-500 dark:text-stone-400">{label}</p>
      <p className="mt-1 text-3xl font-semibold tabular-nums tracking-tight">{value}</p>
      {sub && <p className="mt-1 text-xs text-stone-500 dark:text-stone-400">{sub}</p>}
    </div>
  );
}

export function PageHeader({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="mb-8 max-w-3xl">
      <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h1>
      {children && <div className="mt-3 leading-7 text-stone-600 dark:text-stone-400">{children}</div>}
    </div>
  );
}

const SEVERITY_STYLE = {
  error: 'bg-red-100 text-red-900 dark:bg-red-950 dark:text-red-200',
  warning: 'bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200',
  info: 'bg-sky-100 text-sky-900 dark:bg-sky-950 dark:text-sky-200',
};

export function SeverityBadge({ severity }: { severity: keyof typeof SEVERITY_STYLE }) {
  return <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${SEVERITY_STYLE[severity]}`}>{severity}</span>;
}
