import { describe, expect, it } from 'vitest';
import { formatCrore, formatINR, formatIndian, formatNumber, formatSig } from '../lib/format';

describe('Indian number formatting', () => {
  it('groups lakhs and crores', () => {
    expect(formatINR(12345678)).toBe('₹1,23,45,678');
    expect(formatINR(300000000)).toBe('₹30,00,00,000');
    expect(formatIndian(1000)).toBe('1,000');
    expect(formatIndian(100000)).toBe('1,00,000');
    expect(formatIndian(999)).toBe('999');
  });

  it('keeps decimals and negatives', () => {
    expect(formatIndian(236495.41)).toBe('2,36,495.41');
    expect(formatIndian(-1234567.5)).toBe('-12,34,567.5');
    expect(formatNumber(3878)).toBe('3,878');
  });

  it('expresses rupees in crore', () => {
    expect(formatCrore(300000000)).toBe('₹30 crore');
    expect(formatCrore(15000000000000, 0)).toBe('₹15,00,000 crore');
  });

  it('shows missing as an en dash, never zero', () => {
    expect(formatNumber(null)).toBe('–');
    expect(formatINR(undefined)).toBe('–');
    expect(formatSig(null)).toBe('–');
    expect(formatNumber(0)).toBe('0');
  });

  it('formats small values with significant digits', () => {
    expect(formatSig(0.0001)).toBe('1.000e-4');
    expect(formatSig(2.77448697, 6)).toBe('2.77449');
  });
});
