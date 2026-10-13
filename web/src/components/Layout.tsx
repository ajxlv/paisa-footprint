import { NavLink, Outlet } from 'react-router-dom';
import { useState } from 'react';
import { useTheme } from '../lib/theme';

const NAV = [
  { to: '/companies', label: 'Companies' },
  { to: '/portfolio', label: 'Portfolio calculator' },
  { to: '/data-quality', label: 'Data quality' },
  { to: '/funds', label: 'Funds' },
  { to: '/methodology', label: 'Methodology' },
];

export function Layout() {
  const { theme, toggle } = useTheme();
  const [open, setOpen] = useState(false);
  return (
    <div className="flex min-h-screen flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-2 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2">
        Skip to content
      </a>
      <header className="border-b border-stone-200 dark:border-stone-800">
        <div className="container-page flex h-14 items-center justify-between gap-4">
          <NavLink to="/" className="flex items-center gap-2 font-semibold tracking-tight">
            <span aria-hidden="true" className="inline-block h-6 w-6 rounded-md bg-accent-900" />
            Paisa Footprint
          </NavLink>
          <nav aria-label="Main" className="hidden items-center gap-1 md:flex">
            {NAV.map((item) => (
              <NavLink key={item.to} to={item.to} className={navClass}>
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={toggle}
              className="rounded-md border border-stone-300 px-2.5 py-1.5 text-xs dark:border-stone-700"
              aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            >
              {theme === 'dark' ? 'Light' : 'Dark'}
            </button>
            <button
              type="button"
              className="rounded-md border border-stone-300 px-2.5 py-1.5 text-xs md:hidden dark:border-stone-700"
              aria-expanded={open}
              aria-controls="mobile-nav"
              onClick={() => setOpen((o) => !o)}
            >
              Menu
            </button>
          </div>
        </div>
        {open && (
          <nav id="mobile-nav" aria-label="Main" className="container-page flex flex-col pb-3 md:hidden">
            {NAV.map((item) => (
              <NavLink key={item.to} to={item.to} className={navClass} onClick={() => setOpen(false)}>
                {item.label}
              </NavLink>
            ))}
          </nav>
        )}
      </header>
      <main id="main" className="container-page flex-1 py-8 sm:py-12">
        <Outlet />
      </main>
      <footer className="border-t border-stone-200 py-6 text-sm text-stone-500 dark:border-stone-800 dark:text-stone-400">
        <div className="container-page flex flex-col justify-between gap-2 sm:flex-row">
          <p>Data: company BRSR filings on NSE · Method: PCAF · Open source</p>
          {/* Repository URL to be filled in once the repo is public. */}
          <a href="#" className="underline" aria-label="GitHub repository (link coming soon)">
            GitHub
          </a>
        </div>
      </footer>
    </div>
  );
}

function navClass({ isActive }: { isActive: boolean }) {
  return `rounded-md px-3 py-1.5 text-sm transition-colors ${
    isActive
      ? 'bg-accent-50 font-medium text-accent-900 dark:bg-accent-950 dark:text-accent-200'
      : 'text-stone-600 hover:text-stone-900 dark:text-stone-400 dark:hover:text-stone-100'
  }`;
}
