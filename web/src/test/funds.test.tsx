import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { Funds } from '../pages/Funds';
import { demoFundsSynthetic, fundsEmptySynthetic, mockFetch } from '../demo/synthetic-api-responses';

afterEach(() => vi.unstubAllGlobals());

describe('Funds page', () => {
  it('shows an honest empty state with the ranking explainer and no real table', async () => {
    vi.stubGlobal('fetch', mockFetch({ '/funds': fundsEmptySynthetic }));
    render(<Funds />, { wrapper: MemoryRouter });
    expect(await screen.findByText('How rankings will work')).toBeInTheDocument();
    expect(screen.getByText('Mutual funds: coming next')).toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
    expect(screen.queryByText('Illustrative data, not real market data')).not.toBeInTheDocument();
  });

  it('loads the illustrative fund behind the amber banner, in its own table', async () => {
    vi.stubGlobal('fetch', mockFetch({ '/funds': fundsEmptySynthetic, '/demo/funds': demoFundsSynthetic }));
    render(<Funds />, { wrapper: MemoryRouter });
    await userEvent.click(await screen.findByRole('button', { name: 'Load illustrative fund' }));
    expect(await screen.findByText('Illustrative data, not real market data')).toBeInTheDocument();
    expect(screen.getAllByRole('table')).toHaveLength(1);
    expect(screen.getByText('Illustrative funds (synthetic)')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Illustrative Large Cap Fund' })).toHaveAttribute(
      'href',
      '/funds/illustrative/illustrative-amc-illustrative-large-cap-fund-2026-03-31',
    );
    expect(screen.getByText('94.1%')).toBeInTheDocument();
  });
});
