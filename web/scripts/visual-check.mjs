/**
 * Screenshots + axe accessibility scan of every page, against a running API and `vite preview`.
 *
 *   uvicorn api.main:app --port 8000 &   (from the repo root, after pf build-snapshot)
 *   npm run build && npx vite preview --port 4173 &
 *   node scripts/visual-check.mjs [--shots ../docs/screenshots] [--base http://localhost:4173]
 *
 * Uses the system Chromium when PW_CHROMIUM is set (e.g. /opt/pw-browsers/chromium).
 */
import { chromium } from 'playwright';
import AxeBuilder from '@axe-core/playwright';
import { mkdirSync } from 'node:fs';

const arg = (name, fallback) => {
  const i = process.argv.indexOf(name);
  return i > 0 ? process.argv[i + 1] : fallback;
};
const base = arg('--base', 'http://localhost:4173');
const shots = arg('--shots', '');
if (shots) mkdirSync(shots, { recursive: true });

const PAGES = [
  ['home', '/'],
  ['companies', '/companies'],
  ['company-titan', '/companies/INE280A01028'],
  ['portfolio', '/portfolio', async (page) => {
    await page.getByRole('button', { name: 'Load illustrative example' }).click();
    await page.getByRole('button', { name: 'Compute' }).click();
    await page.getByText('Per-holding breakdown').waitFor();
  }],
  ['data-quality', '/data-quality'],
  ['methodology', '/methodology', null, { shot: false }],
  ['funds', '/funds', async (page) => {
    await page.getByRole('button', { name: 'Load illustrative fund' }).click();
    await page.getByText('Illustrative funds (synthetic)').waitFor();
  }, { shot: false }],
];
const VIEWPORTS = [['desktop', 1280, 900], ['phone', 390, 844]];

const browser = await chromium.launch(process.env.PW_CHROMIUM ? { executablePath: process.env.PW_CHROMIUM } : {});
const summary = [];
for (const [vpName, width, height] of VIEWPORTS) {
  const context = await browser.newContext({ viewport: { width, height } });
  const page = await context.newPage();
  for (const [name, path, act, opts = {}] of PAGES) {
    await page.goto(base + path, { waitUntil: 'networkidle' });
    if (act) await act(page);
    await page.mouse.move(0, 0); // no stray hover tooltips in screenshots
    await page.waitForTimeout(600); // let charts finish their entry animation
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    if (shots && opts.shot !== false) await page.screenshot({ path: `${shots}/${name}-${vpName}.png`, fullPage: true });
    const axe = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
    const count = (impact) => axe.violations.filter((v) => v.impact === impact).length;
    summary.push({ page: name, viewport: vpName, critical: count('critical'), serious: count('serious'),
      moderate: count('moderate'), minor: count('minor'), horizontalOverflowPx: Math.max(0, overflow) });
    for (const v of axe.violations.filter((v) => ['critical', 'serious'].includes(v.impact))) {
      console.log(`[${vpName}] ${name}: ${v.impact} ${v.id} — ${v.help} (${v.nodes.length} nodes)`);
      for (const n of v.nodes.slice(0, 3)) console.log('    ', n.target.join(' '), n.failureSummary?.split('\n')[1] ?? '');
    }
  }
  await context.close();
}
await browser.close();
console.table(summary);
