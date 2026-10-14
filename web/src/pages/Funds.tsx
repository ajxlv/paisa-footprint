import { useState } from 'react';
import { fundsApi, type FundResult } from '../lib/api';
import { useApi } from '../lib/useApi';
import { ErrorBox, IllustrativeBanner, Loading, PageHeader } from '../components/ui';
import { FundsTable } from '../components/FundsTable';
import { RankingDiagram } from '../components/RankingDiagram';

export function Funds() {
  const real = useApi(fundsApi.funds);
  const [demo, setDemo] = useState<FundResult[] | null>(null);
  const [demoError, setDemoError] = useState<string | null>(null);
  const [loadingDemo, setLoadingDemo] = useState(false);

  async function loadDemo() {
    setLoadingDemo(true);
    setDemoError(null);
    try {
      setDemo(await fundsApi.demoFunds());
    } catch (err) {
      setDemoError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoadingDemo(false);
    }
  }

  const hasReal = real.data?.available === true && real.data.funds.length > 0;

  return (
    <div className="space-y-10">
      {hasReal ? (
        <PageHeader title="Mutual funds">
          Indian equity funds ranked by the carbon their portfolios finance (lowest footprint first). Coverage is shown beside
          every number; funds under 50% coverage are listed but not ranked.
        </PageHeader>
      ) : (
        <PageHeader title="Mutual funds: coming next">
          This page will rank Indian equity mutual funds by the carbon their portfolios finance. No real fund data has been
          loaded yet, so there are no real rankings here. The pipeline is built: it is waiting for the AMCs' monthly portfolio
          files and real EVIC data.
        </PageHeader>
      )}

      {real.loading && <Loading label="Checking for fund data…" />}
      {real.error && <ErrorBox error={real.error} />}
      {hasReal && real.data && (
        <FundsTable funds={real.data.funds} linkBase="/funds" caption="Funds from the current snapshot" />
      )}

      {!hasReal && !real.loading && (
        <section aria-labelledby="how-h" className="space-y-4">
          <h2 id="how-h" className="text-xl font-semibold">How rankings will work</h2>
          <p className="max-w-3xl text-sm leading-6 text-stone-700 dark:text-stone-300">
            A fund is a portfolio, so it goes through exactly the same PCAF arithmetic as the portfolio calculator. Three
            numbers matter, and they answer different questions: the <strong>carbon footprint</strong> (how much carbon each
            ₹ crore in the fund finances), <strong>WACI</strong> (how carbon-intensive its companies are per rupee of sales),
            and <strong>coverage</strong> (how much of the fund we can actually measure).
          </p>
          <RankingDiagram />
        </section>
      )}

      <section aria-labelledby="demo-h" className="space-y-4">
        <h2 id="demo-h" className="text-xl font-semibold">Try it with an illustrative fund</h2>
        <p className="max-w-3xl text-sm text-stone-600 dark:text-stone-400">
          Runs a synthetic AMC workbook (made-up schemes and holdings, real BRSR emissions, illustrative EVIC) through the real
          engine. It is shown separately and never mixed with real funds.
        </p>
        {!demo && (
          <button type="button" className="btn-secondary" onClick={loadDemo} disabled={loadingDemo}>
            {loadingDemo ? 'Loading…' : 'Load illustrative fund'}
          </button>
        )}
        {demoError && <ErrorBox error={demoError} />}
        {demo && (
          <>
            <IllustrativeBanner>
              These funds, their holdings and the EVIC values are made up. Only the companies' emissions are real BRSR data.
              Nothing here describes a real mutual fund.
            </IllustrativeBanner>
            <FundsTable funds={demo} linkBase="/funds/illustrative" caption="Illustrative funds (synthetic)" />
          </>
        )}
      </section>
    </div>
  );
}
