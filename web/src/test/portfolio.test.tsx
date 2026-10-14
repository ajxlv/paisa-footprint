import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { Portfolio } from '../pages/Portfolio';
import { companiesSynthetic, demoSynthetic, mockFetch } from '../demo/synthetic-api-responses';

afterEach(() => vi.unstubAllGlobals());

describe('Portfolio calculator', () => {
  it('has no illustrative banner before synthetic data is loaded', async () => {
    vi.stubGlobal('fetch', mockFetch({ '/companies': companiesSynthetic }));
    render(<Portfolio />, { wrapper: MemoryRouter });
    await screen.findByLabelText('Company for holding 1');
    expect(screen.queryByText('Illustrative data, not real market data')).not.toBeInTheDocument();
  });

  it('shows the illustrative banner when the example loads', async () => {
    vi.stubGlobal('fetch', mockFetch({ '/companies': companiesSynthetic, '/demo/portfolios': demoSynthetic }));
    render(<Portfolio />, { wrapper: MemoryRouter });
    await screen.findByLabelText('Company for holding 1');
    await userEvent.click(screen.getByRole('button', { name: 'Load illustrative example' }));
    expect(await screen.findByText('Illustrative data, not real market data')).toBeInTheDocument();
    expect(screen.getByLabelText('Company for holding 1')).toHaveValue('INE584A01023');
    expect(screen.getByLabelText('EVIC in rupees crore for holding 1')).toHaveValue('60000');
  });

  it('sends demo EVIC flagged as illustrative', async () => {
    const fetch = mockFetch({
      '/companies': companiesSynthetic,
      '/demo/portfolios': demoSynthetic,
      '/portfolio/compute': {
        total_value_inr: 60000000, covered_value_inr: 60000000, coverage_pct: 100, financed_emissions_t: 19.8372,
        carbon_footprint_t_per_crore: 3.3062, waci_t_per_crore_revenue: 6.2868, waci_value_inr: 60000000,
        waci_coverage_pct: 100, pcaf_data_quality: 1, holdings: [], uncovered: [], contains_illustrative_inputs: true,
      },
    });
    vi.stubGlobal('fetch', fetch);
    render(<Portfolio />, { wrapper: MemoryRouter });
    await screen.findByLabelText('Company for holding 1');
    await userEvent.click(screen.getByRole('button', { name: 'Load illustrative example' }));
    await screen.findByText('Illustrative data, not real market data');
    await userEvent.click(screen.getByRole('button', { name: 'Compute' }));
    expect(await screen.findByText('100.0%')).toBeInTheDocument();
    const call = fetch.mock.calls.find(([url]) => String(url).endsWith('/portfolio/compute'));
    const body = JSON.parse(String((call?.[1] as RequestInit).body));
    expect(body.evic[0]).toMatchObject({ evic_inr: 600000000000, evic_is_illustrative: true });
  });
});
