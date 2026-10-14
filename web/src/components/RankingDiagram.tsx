/**
 * "How rankings will work": an HTML diagram (no image files) that stacks on phones and runs left to
 * right on wider screens.
 */
export function RankingDiagram() {
  return (
    <figure className="card" aria-labelledby="ranking-diagram-caption">
      <figcaption id="ranking-diagram-caption" className="mb-5 font-medium">How a fund's numbers are built</figcaption>
      <div className="grid items-center gap-3 md:grid-cols-[1fr_auto_1.2fr_auto_1.6fr]">
        <Box title="Fund holdings" tone="neutral">
          Every equity line in the AMC's monthly portfolio, with its market value in ₹.
        </Box>
        <Arrow />
        <div className="space-y-3">
          <Box title="Covered" tone="good">
            The company files Scope 1 + 2 in BRSR, and its EVIC is known.
          </Box>
          <Box title="Uncovered" tone="warn">
            No reported emissions or no EVIC. Listed by name and <strong>not estimated</strong>.
          </Box>
        </div>
        <Arrow />
        <div className="space-y-3">
          <Box title="Coverage" tone="neutral" mono="covered ₹ ÷ all equity ₹">
            Shown next to every number. Below 50%, the fund is marked "insufficient coverage" and not ranked.
          </Box>
          <Box title="Carbon footprint" tone="neutral" mono="Σ (value ÷ EVIC) × (S1+S2) ÷ covered ₹ crore">
            Tonnes financed per ₹ crore invested. This is what the ranking sorts on.
          </Box>
          <Box title="WACI" tone="neutral" mono="Σ weight × (S1+S2) ÷ revenue (₹ crore)">
            How carbon-intensive the fund's companies are per rupee of sales. It needs no EVIC.
          </Box>
        </div>
      </div>
    </figure>
  );
}

function Box({ title, tone, mono, children }: { title: string; tone: 'neutral' | 'good' | 'warn'; mono?: string; children: React.ReactNode }) {
  const style = {
    neutral: 'border-stone-300 dark:border-stone-700',
    good: 'border-green-600 dark:border-green-500',
    warn: 'border-dashed border-amber-500',
  }[tone];
  return (
    <div className={`rounded-md border-2 ${style} bg-white px-3 py-2.5 text-sm dark:bg-stone-900`}>
      <p className="font-semibold">{title}</p>
      {mono && <p className="mt-1 font-mono text-[12px] text-stone-700 dark:text-stone-300">{mono}</p>}
      <p className="mt-1 text-stone-600 dark:text-stone-400">{children}</p>
    </div>
  );
}

function Arrow() {
  return (
    <div aria-hidden="true" className="text-center text-xl text-stone-400">
      <span className="md:hidden">↓</span>
      <span className="hidden md:inline">→</span>
    </div>
  );
}
