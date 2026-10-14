/** Plain-English explanations of each validator, shown wherever an issue appears. */
/**
 * `problem` rules flag something a human should check (severity warning/error);
 * `info` rules record something handled by design (severity info) and are not problems.
 */
export type RuleKind = 'problem' | 'info';

export const RULE_KIND: Record<string, RuleKind> = {
  V1: 'info',
  V2: 'problem',
  'V2-fix': 'problem',
  V3: 'problem',
  V4: 'problem',
  V5: 'problem',
  V6: 'info',
  V7: 'problem',
  V9: 'info',
  V10: 'problem',
};

export const RULE_TEXT: Record<string, { title: string; plain: string }> = {
  V1: {
    title: '"MtCO2e" read as metric tonnes',
    plain:
      'Strictly, "Mt" means megatonnes (a million tonnes). The values make clear filers mean metric tonnes, so we read them as tonnes and flag it. If that reading implies more than 50,000 tCO2e per ₹ crore of revenue, it becomes a warning.',
  },
  V2: {
    title: 'Revenue at the wrong scale',
    plain:
      'A listed company cannot have revenue under ₹10 lakh. This is almost always ₹ crore typed into a rupee field, which makes the reported intensity wrong by a factor of about 10 million. We flag it, keep the filed number, and leave the company out of WACI. We do not rescale it.',
  },
  V3: {
    title: 'Two revenue figures disagree',
    plain:
      'BRSR asks for revenue from operations and total revenue. Total revenue adds other income, so it is normally a little higher. A gap of more than 2× points to a typing or scale error in one of them (or unusually large other income).',
  },
  V4: {
    title: 'Zero used for "not reported"',
    plain:
      'A year with zero Scope 1 and zero Scope 2 next to a year with real emissions almost certainly means the data was not filed. We treat it as missing, never as zero emissions.',
  },
  V5: {
    title: 'Big year-on-year jump',
    plain:
      'Emissions rarely double or halve in a year. A change above 2× may be real (an acquisition, a new plant) or a boundary change, so we flag it for review and never correct it.',
  },
  V6: {
    title: 'Fiscal year not April–March',
    plain: 'Some companies close their books in June or December. We carry the real dates through instead of assuming April–March.',
  },
  V7: {
    title: 'Holding not matched to a company',
    plain: 'A holding whose ISIN or symbol matches no company is listed as uncovered, never silently dropped.',
  },
  V9: {
    title: 'GHG disclosure marked "not applicable"',
    plain: 'The company says emissions disclosure does not apply to it. It is excluded from emissions and counts as a coverage gap. We do not estimate it.',
  },
  V10: {
    title: 'Reported intensity does not add up',
    plain:
      'The reported intensity should equal (Scope 1 + Scope 2) ÷ revenue. A difference above 1% means one of the inputs is mistyped. No real filing triggers this yet.',
  },
};

export const TRANSFORM_HINT =
  'Transformation records exactly what we did to the filed value. "none" means it is used as filed.';
