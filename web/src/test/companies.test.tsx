import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, afterEach } from 'vitest';
import { CompaniesTable } from '../components/CompaniesTable';
import { Companies } from '../pages/Companies';
import { companiesSynthetic, mockFetch } from '../demo/synthetic-api-responses';

afterEach(() => vi.unstubAllGlobals());

describe('CompaniesTable', () => {
  it('renders one row per company with Indian-formatted numbers', () => {
    render(<CompaniesTable companies={companiesSynthetic} />, { wrapper: MemoryRouter });
    const rows = screen.getAllByRole('row').slice(1);
    expect(rows).toHaveLength(3);
    const nmdc = screen.getByRole('link', { name: 'NMDC Limited' }).closest('tr')!;
    expect(within(nmdc).getByText('1,12,805')).toBeInTheDocument();
    expect(within(nmdc).getByText('1,98,372')).toBeInTheDocument();
    const rajesh = screen.getByRole('link', { name: 'RAJESH EXPORTS LIMITED' }).closest('tr')!;
    expect(within(rajesh).getByText('excluded')).toBeInTheDocument();
  });

  it('filters by search text', async () => {
    render(<CompaniesTable companies={companiesSynthetic} />, { wrapper: MemoryRouter });
    await userEvent.type(screen.getByRole('searchbox'), 'gujthem');
    expect(screen.getAllByRole('row').slice(1)).toHaveLength(1);
    expect(screen.getByText('GUJARAT THEMIS BIOSYN LIMITED')).toBeInTheDocument();
  });

  it('sorts by total with missing values last', async () => {
    render(<CompaniesTable companies={companiesSynthetic} />, { wrapper: MemoryRouter });
    await userEvent.click(screen.getByRole('button', { name: /Total/ }));
    const names = screen.getAllByRole('link').map((a) => a.textContent);
    expect(names).toEqual(['NMDC Limited', 'GUJARAT THEMIS BIOSYN LIMITED', 'RAJESH EXPORTS LIMITED']);
  });
});

describe('Companies page', () => {
  it('loads rows from the API', async () => {
    vi.stubGlobal('fetch', mockFetch({ '/companies': companiesSynthetic }));
    render(<Companies />, { wrapper: MemoryRouter });
    expect(await screen.findByRole('link', { name: 'NMDC Limited' })).toBeInTheDocument();
  });

  it('shows an error state when the API is down', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('Failed to fetch'); }));
    render(<Companies />, { wrapper: MemoryRouter });
    expect(await screen.findByRole('alert')).toHaveTextContent('Failed to fetch');
  });
});
