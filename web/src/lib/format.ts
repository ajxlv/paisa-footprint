/**
 * Indian number formatting, shared by every page.
 * Grouping is done by hand (last three digits, then pairs) so output never depends on the
 * browser's ICU data: 12345678 -> "1,23,45,678".
 */

export const INR_PER_CRORE = 1e7;

function groupIndian(integerDigits: string): string {
  if (integerDigits.length <= 3) return integerDigits;
  const last3 = integerDigits.slice(-3);
  const rest = integerDigits.slice(0, -3);
  return `${rest.replace(/\B(?=(\d{2})+(?!\d))/g, ',')},${last3}`;
}

/** 12345678.9 -> "1,23,45,678.9" (at most `maxDecimals`, trailing zeros trimmed). */
export function formatIndian(value: number, maxDecimals = 2): string {
  if (!Number.isFinite(value)) return '–';
  const negative = value < 0;
  const fixed = Math.abs(value).toFixed(maxDecimals);
  const [int, frac = ''] = fixed.split('.');
  const trimmed = frac.replace(/0+$/, '');
  return `${negative ? '-' : ''}${groupIndian(int)}${trimmed ? `.${trimmed}` : ''}`;
}

/** Rupees with Indian grouping: 12345678 -> "₹1,23,45,678". */
export function formatINR(value: number | null | undefined, maxDecimals = 0): string {
  if (value === null || value === undefined) return '–';
  return `₹${formatIndian(value, maxDecimals)}`;
}

/** Rupees expressed in crore: 300000000 -> "₹30 crore". */
export function formatCrore(value: number | null | undefined, maxDecimals = 2): string {
  if (value === null || value === undefined) return '–';
  return `₹${formatIndian(value / INR_PER_CRORE, maxDecimals)} crore`;
}

/** Tonnes or other quantities; missing is shown as an en dash, never as 0. */
export function formatNumber(value: number | null | undefined, maxDecimals = 2): string {
  if (value === null || value === undefined) return '–';
  return formatIndian(value, maxDecimals);
}

/** Small or large values with sensible precision (for intensities and attribution shares). */
export function formatSig(value: number | null | undefined, digits = 4): string {
  if (value === null || value === undefined) return '–';
  if (value === 0) return '0';
  const abs = Math.abs(value);
  if (abs >= 1000) return formatIndian(value, 1);
  if (abs < 0.001) return value.toExponential(digits - 1);
  return String(Number(value.toPrecision(digits)));
}

export function formatPct(value: number | null | undefined, decimals = 1): string {
  if (value === null || value === undefined) return '–';
  return `${value.toFixed(decimals)}%`;
}
