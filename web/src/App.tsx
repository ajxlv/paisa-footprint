import { Route, Routes } from 'react-router-dom';
import { Layout } from './components/Layout';
import { Home } from './pages/Home';
import { Companies } from './pages/Companies';
import { CompanyDetail } from './pages/CompanyDetail';
import { Portfolio } from './pages/Portfolio';
import { DataQuality } from './pages/DataQuality';
import { Methodology } from './pages/Methodology';
import { Funds } from './pages/Funds';
import { NotFound } from './pages/NotFound';

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="companies" element={<Companies />} />
        <Route path="companies/:key" element={<CompanyDetail />} />
        <Route path="portfolio" element={<Portfolio />} />
        <Route path="data-quality" element={<DataQuality />} />
        <Route path="methodology" element={<Methodology />} />
        <Route path="funds" element={<Funds />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
