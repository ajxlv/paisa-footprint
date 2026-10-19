import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { Home } from '../pages/Home';
import { mockFetch, validationSummarySynthetic } from '../demo/synthetic-api-responses';

afterEach(() => vi.unstubAllGlobals());

describe('Home page', () => {
  it('headlines problems, not every informational note', async () => {
    vi.stubGlobal('fetch', mockFetch({ '/validation/summary': validationSummarySynthetic }));
    render(<Home />, { wrapper: MemoryRouter });
    expect(await screen.findByText('Data problems caught')).toBeInTheDocument();
    expect(screen.getByText('14')).toBeInTheDocument();
    expect(screen.getByText('in 6 companies · 26 informational notes')).toBeInTheDocument();
    expect(screen.queryByText('40')).not.toBeInTheDocument();
  });
});
