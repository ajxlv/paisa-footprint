/** Mocked API payloads for component tests. SYNTHETIC: illustrative values, not real market data. */
import { vi } from "vitest";
import type { CompanyDetail, CompanySummary, DemoPortfolio, FundResult, FundsResponse, ValidationSummary } from '../lib/api';

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
    // Longest matching suffix wins, so '/demo/funds' is not mistaken for '/funds'.
    const path = Object.keys(routes)
      .filter((p) => url.endsWith(p))
      .sort((a, b) => b.length - a.length)[0];
    if (!path) return new Response('not found', { status: 404 });
    return new Response(JSON.stringify(routes[path]), { status: 200, headers: { 'Content-Type': 'application/json' } });
  });
}

/** Shape of GET /validation/summary with the fixture snapshot's headline counts. */
export const validationSummarySynthetic: ValidationSummary = {
  companies: 20,
  reporting_scope12: 15,
  pct_reporting_scope12: 75,
  assured: 6,
  pct_assured_of_reporting: 40,
  excluded_companies: 5,
  issues_problems: 14,
  issues_info: 26,
  companies_with_problems: 6,
  issues_total: 40,
  quality_flags: { ok: 11, review: 4, excluded: 5 },
  rules: [],
  excluded: [],
};

/** A company detail payload with one V2-fix correction (values shaped like the fixture's). */
export const companyDetailCorrectedSynthetic: CompanyDetail = {
  summary: companiesSynthetic[2],
  source_file: 'BRSR_synthetic.xml',
  cin: null,
  exclusion_reason: null,
  issues: [],
  years: [
    {
      fiscal_year: 'FY2025-26', is_current: true, period_start: '2025-04-01', period_end: '2026-03-31',
      scope1_t: 12487.99, scope2_t: 6228.92, revenue_inr: 165.82, total_revenue_inr: 1658227981,
      revenue_inr_resolved: 1658200000, total_revenue_inr_resolved: 1658227981, revenue_resolution: 'inferred_crore',
      revenue_note: 'RevenueFromOperations 165.82 interpreted as ₹ crore', revenue_corrected: true,
      intensity_reported_per_inr: 112.87, intensity_t_per_crore: 112.87, assured: null, quality_flag: 'review',
      issues: ['V2-fix'],
      provenance: {
        revenue_from_operations_inr: {
          element: 'RevenueFromOperations', context_ref: 'DCYMain', period_start: '2025-04-01', period_end: '2026-03-31',
          unit_raw: 'iso4217:INR', raw_value: '165.82', transformation: 'corrected ×1e+07 (rule V2-fix)',
          value_used: 1658200000, corrected: true,
        },
      },
    },
  ],
};

/** GET /funds when no fund snapshot exists. */
export const fundsEmptySynthetic: FundsResponse = { available: false, snapshot_dir: 'data/snapshots/fixtures', funds: [] };

/** GET /demo/funds shape: one ILLUSTRATIVE fund (made-up scheme). */
export const demoFundsSynthetic: FundResult[] = [
  {
    fund_key: 'illustrative-amc-illustrative-large-cap-fund-2026-03-31', amc: 'Illustrative AMC',
    scheme_name: 'Illustrative Large Cap Fund', as_of_date: '2026-03-31', source_file: 'amc_portfolio_synthetic.xlsx',
    illustrative: true, status: 'ranked', rank: 1, equity_value_inr: 255000000, non_equity_value_inr: 45000000,
    coverage_pct: 94.1, carbon_footprint_t_per_crore: 5.345, waci_t_per_crore_revenue: 7.238, financed_emissions_t: 128.29,
    pcaf_data_quality: 1.12, contains_illustrative_inputs: true, top_contributors: [], uncovered: [], issues: [],
  },
];
