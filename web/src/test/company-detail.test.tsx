import { render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { CompanyDetail } from '../pages/CompanyDetail';
import { companyDetailCorrectedSynthetic, mockFetch } from '../demo/synthetic-api-responses';

afterEach(() => vi.unstubAllGlobals());

describe('Company detail provenance', () => {
  it('marks a V2-fix revenue correction with a Corrected chip and shows the value used', async () => {
    vi.stubGlobal('fetch', mockFetch({ '/companies/INE942C01045': companyDetailCorrectedSynthetic }));
    render(
      <MemoryRouter initialEntries={['/companies/INE942C01045']}>
        <Routes>
          <Route path="/companies/:key" element={<CompanyDetail />} />
        </Routes>
      </MemoryRouter>,
    );
    const panel = (await screen.findByText('Where this number comes from')).closest('section')!;
    const row = within(panel).getByText('RevenueFromOperations').closest('tr')!;
    expect(within(row).getByText('Corrected')).toBeInTheDocument();
    expect(within(row).getByText('165.82')).toBeInTheDocument();
    expect(within(row).getByText(/1,65,82,00,000/)).toBeInTheDocument();
  });
});
