/** Mocked API payloads for component tests. SYNTHETIC: illustrative values, not real market data. */
import { vi } from "vitest";
import type { CompanySummary, DemoPortfolio } from '../lib/api';

export const companiesSynthetic: CompanySummary[] = [
  {
    company_key: 'INE584A01023', company_name: 'NMDC Limited', nse_symbol: 'NMDC', isin: 'INE584A01023',
    fiscal_year: 'FY2025-26', period_end: '2026-03-31', scope1_t: 112805, scope2_t: 85567, total_t: 198372,
    intensity_t_per_crore: 6.2868, assured: true, quality_flag: 'ok', issues: [],
  },
  {
    company_key: 'INE343B01030', company_name: 'RAJESH EXPORTS LIMITED', nse_symbol: 'RAJESHEXPO', isin: 'INE343B01030',
    fiscal_year: 'FY2025-26', period_end: '2026-03-31', scope1_t: null, scope2_t: null, total_t: null,
    intensity_t_per_crore: null, assured: null, quality_flag: 'excluded', issues: ['V9'],
  },
  {
    company_key: 'INE942C01045', company_name: 'GUJARAT THEMIS BIOSYN LIMITED', nse_symbol: 'GUJTHEM', isin: 'INE942C01045',
    fiscal_year: 'FY2025-26', period_end: '2026-03-31', scope1_t: 12487.99, scope2_t: 6228.92, total_t: 18716.91,
    intensity_t_per_crore: null, assured: null, quality_flag: 'review', issues: ['V1', 'V2', 'V3'],
  },
];

export const demoSynthetic: DemoPortfolio[] = [
  {
    id: 'portfolio_synthetic_a',
    description: 'ILLUSTRATIVE, NOT REAL MARKET DATA.',
    illustrative: true,
    holdings: [{ isin_or_symbol: 'INE584A01023', value_inr: 60000000 }],
    evic: [{ company_key: 'INE584A01023', evic_inr: 600000000000, evic_source: 'illustrative', evic_is_illustrative: true }],
  },
];

export function mockFetch(routes: Record<string, unknown>) {
  return vi.fn(async (url: string, _init?: RequestInit) => {
    const path = Object.keys(routes).find((p) => url.endsWith(p));
    if (!path) return new Response('not found', { status: 404 });
    return new Response(JSON.stringify(routes[path]), { status: 200, headers: { 'Content-Type': 'application/json' } });
  });
}
