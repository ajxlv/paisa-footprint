import { PageHeader } from '../components/ui';

export function Funds() {
  return (
    <div className="max-w-3xl">
      <PageHeader title="Mutual funds: coming next">
        This page will rank Indian equity mutual funds by the carbon their portfolios finance. It is not built yet, and
        there is no fund data in this build: nothing here is real or simulated.
      </PageHeader>
      <div className="card space-y-4 text-sm leading-6 text-stone-700 dark:text-stone-300">
        <h2 className="text-base font-semibold text-stone-900 dark:text-stone-100">What the next milestone adds</h2>
        <ol className="ml-5 list-decimal space-y-2">
          <li>Ingest the monthly portfolio disclosures that SEBI requires every AMC to publish, starting with three AMCs.</li>
          <li>Match each holding to a company by ISIN, reporting any that do not match (rule V7).</li>
          <li>Check that each fund's holdings add up to 95–105% of its NAV (rule V8).</li>
          <li>Add real EVIC (market capitalisation plus total debt) for listed companies.</li>
        </ol>
        <h2 className="pt-2 text-base font-semibold text-stone-900 dark:text-stone-100">The planned ranking table</h2>
        <p>
          One row per fund, with carbon footprint (tCO2e per ₹ crore invested), WACI, coverage shown next to every number,
          and the PCAF data-quality score. Each fund will open into the same per-holding "why this number" breakdown the
          portfolio calculator uses.
        </p>
      </div>
    </div>
  );
}
