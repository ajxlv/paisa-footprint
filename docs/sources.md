# Data sources (copy into docs/sources.md in the repo)

## BRSR filings list (NSE JSON API, found via DevTools on 13 Oct 2026)
- **All filings in a submission-date window:**
  `https://www.nseindia.com/api/corporate-bussiness-sustainabilitiy?index=equities&from_date=14-10-2025&to_date=14-10-2026`
  - Dates are `DD-MM-YYYY`. They filter on **submission date**, not fiscal year.
  - The spelling `bussiness-sustainabilitiy` is NSE's own typo. Don't "fix" it.
- **One company:**
  `https://www.nseindia.com/api/corporate-bussiness-sustainabilitiy?index=equities&symbol=BOSCHLTD&issuer=Bosch%20Limited`
- The response is about 77 kB of JSON for one year of filings. Field names are not yet documented, so inspect one response before writing code. Find the field that holds the XBRL `.xml` link.
- Access: the API needs a browser User-Agent plus the cookies NSE sets when you first load `https://www.nseindia.com/`. It fails from cloud servers.
- **Full history:** query one-year windows back to 2022 (BRSR became mandatory for the top 1,000 companies from FY2022-23 [Likely]), then de-duplicate. A company can file revisions, so keep the latest submission per company per fiscal year and record that you did.

## BRSR filings (RSS, recent items only)
- `https://nsearchives.nseindia.com/content/RSS/brsr.xml`
- Each item links to `https://nsearchives.nseindia.com/corporate/xbrl/BRSR_<id>_WebXMLFile_<timestamp>.xml`

## Cross-check
- Dataful BRSR emissions dataset: https://dataful.in/datasets/20264/ (comparison only, never the source)
