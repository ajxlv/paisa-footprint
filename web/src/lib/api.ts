/** Typed client for the read-only Paisa Footprint API. */

export const API_URL = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/$/, '');

export type QualityFlag = 'ok' | 'review' | 'excluded';

export interface CompanySummary {
  company_key: string;
  company_name: string;
  nse_symbol: string | null;
  isin: string | null;
  fiscal_year: string;
  period_end: string;
  scope1_t: number | null;
  scope2_t: number | null;
  total_t: number | null;
  intensity_t_per_crore: number | null;
  assured: boolean | null;
  quality_flag: QualityFlag;
  issues: string[];
}

export interface ValueProvenance {
  element: string;
  context_ref: string;
  period_start: string | null;
  period_end: string;
  unit_raw: string | null;
  raw_value: string;
  transformation: string;
}

export interface CompanyYear {
  fiscal_year: string;
  is_current: boolean;
  period_start: string;
  period_end: string;
  scope1_t: number | null;
  scope2_t: number | null;
  revenue_inr: number | null;
  total_revenue_inr: number | null;
  intensity_reported_per_inr: number | null;
  intensity_t_per_crore: number | null;
  assured: boolean | null;
  quality_flag: QualityFlag;
  issues: string[];
  provenance: Record<string, ValueProvenance>;
}

export interface IssueOut {
  rule_id: string;
  severity: 'error' | 'warning' | 'info';
  field: string;
  fiscal_year: string;
  message: string;
  observed_value: string | null;
  suggested_fix: string | null;
  explanation: string;
}

export interface CompanyDetail {
  summary: CompanySummary;
  source_file: string;
  cin: string | null;
  exclusion_reason: string | null;
  years: CompanyYear[];
  issues: IssueOut[];
}

export interface RuleSummary {
  rule_id: string;
  description: string;
  issues: number;
  companies: number;
  example: string;
}

export interface ValidationSummary {
  companies: number;
  reporting_scope12: number;
  pct_reporting_scope12: number | null;
  assured: number;
  pct_assured_of_reporting: number | null;
  excluded_companies: number;
  issues_total: number;
  quality_flags: Record<QualityFlag, number>;
  rules: RuleSummary[];
  excluded: { company_name: string | null; fiscal_year: string | null; reason: string; is_current: boolean | null }[];
}

export interface HoldingIn {
  isin_or_symbol: string;
  value_inr: number;
}

export interface EvicIn {
  company_key: string;
  evic_inr: number;
  evic_source: string;
  evic_is_illustrative: boolean;
}

export interface DemoPortfolio {
  id: string;
  description: string;
  illustrative: boolean;
  holdings: HoldingIn[];
  evic: EvicIn[];
}

export interface HoldingResult {
  isin_or_symbol: string;
  company_key: string;
  company_name: string;
  fiscal_year: string;
  value_inr: number;
  evic_inr: number;
  evic_source: string;
  evic_is_illustrative: boolean;
  attribution: number;
  scope1_t: number;
  scope2_t: number;
  financed_emissions_t: number;
  revenue_inr: number | null;
  intensity_t_per_crore_revenue: number | null;
  in_waci: boolean;
  waci_exclusion_reason: string | null;
  pcaf_data_quality: number;
  formula: string;
}

export interface UncoveredHolding {
  isin_or_symbol: string;
  company_key: string | null;
  value_inr: number;
  reason: string;
}

export interface PortfolioResult {
  total_value_inr: number;
  covered_value_inr: number;
  coverage_pct: number;
  financed_emissions_t: number;
  carbon_footprint_t_per_crore: number | null;
  waci_t_per_crore_revenue: number | null;
  waci_value_inr: number;
  waci_coverage_pct: number;
  pcaf_data_quality: number | null;
  holdings: HoldingResult[];
  uncovered: UncoveredHolding[];
  contains_illustrative_inputs: boolean;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, init);
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === 'string') detail = body.detail;
    } catch {
      /* keep the status text */
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export const api = {
  companies: () => request<CompanySummary[]>('/companies'),
  company: (key: string) => request<CompanyDetail>(`/companies/${encodeURIComponent(key)}`),
  validationSummary: () => request<ValidationSummary>('/validation/summary'),
  demoPortfolios: () => request<DemoPortfolio[]>('/demo/portfolios'),
  methodology: () => request<{ markdown: string }>('/methodology'),
  compute: (holdings: HoldingIn[], evic: EvicIn[]) =>
    request<PortfolioResult>('/portfolio/compute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ holdings, evic }),
    }),
};
