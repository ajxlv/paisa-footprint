# Run the NSE bulk download on your laptop (Windows PowerShell)

NSE blocks cloud servers, so the full BRSR download has to run from your own machine. This page
takes you from a fresh clone to a snapshot of every BRSR filing since 2022, and says what to paste
back into the project thread.

Everything here only **reads** from NSE: about one request per second, with pauses and retries if
NSE pushes back. Expect 1,000–3,000 files and roughly an hour. You can stop at any time and re-run
the same command: files already downloaded are skipped.

## 1. One-time setup

```powershell
git clone https://github.com/ajxlv/paisa-footprint.git
cd paisa-footprint
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -e ".[dev]"
pytest -q                              # should end with "passed"; nothing here touches the network
```

If you already have the repo: `git pull`, then `.\.venv\Scripts\Activate.ps1` and `pip install -e ".[dev]"`.

## 2. Download the filings

```powershell
pf fetch-brsr --out data/raw/brsr --from 2022-01-01
```

What it does:
1. Opens `https://www.nseindia.com/` once to get NSE's cookies.
2. Asks the BRSR API for each one-year window of submission dates, from 2022-01-01 to today.
3. Saves every `.xml` link it finds to `data/raw/brsr/`.

It also writes:
- `data/raw/brsr/manifest.csv`: one row per link (company, symbol, url, submission date if found,
  download time, SHA-256, status: `downloaded` / `skipped_existing` / `failed`).
- `data/raw/brsr/_response_schema.json`: the field names NSE's API actually returned. **Open this
  file and paste its `keys` list into the thread**, so the extractor can be made exact.

If the API keeps failing (HTTP 401/403), use the RSS feed instead. It covers recent filings only:

```powershell
pf fetch-brsr --out data/raw/brsr --source rss
```

## 3. Validate and build a snapshot

```powershell
pf validate data/raw/brsr --out data/raw/brsr_validation_report.csv
pf build-snapshot --input data/raw/brsr --out data/snapshots/2026-10
```

Use the current year and month for the snapshot folder name (`YYYY-MM`).

`pf build-snapshot` keeps the latest submission per company per fiscal year. Older revisions are
listed in `excluded.parquet` as `superseded`, with the file that replaced them. Nothing is
silently dropped.

To look at the result in the app:

```powershell
$env:PF_SNAPSHOT_DIR = "data/snapshots/2026-10"
uvicorn api.main:app
```

## 4. What to paste back into the project thread

Copy these from the terminal output:

1. From `pf fetch-brsr`: **Links found / Downloaded / Already on disk / Failed**, plus any `FAILED` lines.
2. The `keys` list from `data/raw/brsr/_response_schema.json`.
3. From `pf validate`: the first line (**Parsed N filings, M failed to parse**), the `FAILED`
   lines if any, and the **per-rule table** (rule, issues).
4. From `pf build-snapshot`: the whole summary block (`files_seen`, `files_parsed`,
   `files_failed`, `files_superseded`, `parsed_company_years`, `clean_company_years`,
   `excluded_company_years`, `duplicate_company_years`, `issues`).

Do **not** paste the XML files or commit `data/`. It is git-ignored on purpose.

## Troubleshooting

| Symptom | What to do |
|---|---|
| `Links found 0` | Open `_response_schema.json`. If it is missing, the API returned nothing for any window; try `--source rss`. If it exists, paste it into the thread: the link field may need adding. |
| Many `failed` rows | Re-run the same command later; only the failed and missing files are retried. |
| `Failed to parse` in `pf validate` | Paste the file names. Some NSE files may be HTML error pages saved as `.xml`; they are reported, never ignored. |
