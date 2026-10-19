import { lazy, Suspense } from 'react';
import { Route, Routes } from 'react-router-dom';
import { Layout } from './components/Layout';
import { Loading } from './components/ui';
import { Home } from './pages/Home';
import { NotFound } from './pages/NotFound';

// Pages that pull in Recharts or the Markdown renderer load on demand, keeping first paint small.
const Companies = lazy(() => import('./pages/Companies').then((m) => ({ default: m.Companies })));
const CompanyDetail = lazy(() => import('./pages/CompanyDetail').then((m) => ({ default: m.CompanyDetail })));
const Portfolio = lazy(() => import('./pages/Portfolio').then((m) => ({ default: m.Portfolio })));
const DataQuality = lazy(() => import('./pages/DataQuality').then((m) => ({ default: m.DataQuality })));
const Methodology = lazy(() => import('./pages/Methodology').then((m) => ({ default: m.Methodology })));
const Funds = lazy(() => import('./pages/Funds').then((m) => ({ default: m.Funds })));
const FundDetail = lazy(() => import('./pages/FundDetail').then((m) => ({ default: m.FundDetail })));

export function App() {
  return (
    <Suspense fallback={<Loading />}>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="companies" element={<Companies />} />
          <Route path="companies/:key" element={<CompanyDetail />} />
          <Route path="portfolio" element={<Portfolio />} />
          <Route path="data-quality" element={<DataQuality />} />
          <Route path="methodology" element={<Methodology />} />
          <Route path="funds" element={<Funds />} />
          <Route path="funds/illustrative/:key" element={<FundDetail illustrative />} />
          <Route path="funds/:key" element={<FundDetail />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
