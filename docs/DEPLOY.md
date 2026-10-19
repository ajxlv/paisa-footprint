# Deploying Paisa Footprint (instructions only; nothing has been deployed)

Two pieces:
- The **API** (FastAPI, read-only) runs as a Docker container on Render.
- The **web app** (static React build) is hosted on Vercel.

No accounts were created and nothing was deployed during the build. These steps are for you.

The API image builds the fixture snapshot (20 real BRSR filings) at image build time, so it works
with no external data. Both images were built and smoke-tested locally on 14 Oct 2026: `/health`
returned 20 companies, `/validation/summary` returned 14 problems / 26 notes / 6 companies,
`/demo/funds` returned the 3 illustrative funds, and the web image served deep links.

## 1. API on Render

1. Push the repo to GitHub (it already is: `ajxlv/paisa-footprint`).
2. Sign in at render.com, choose **New → Blueprint**, and pick the repo. Render reads
   `render.yaml`, which defines one free Docker web service called `paisa-footprint-api`, with
   health check `/health`.
3. When asked for `PF_CORS_ORIGINS`, enter the web app's URL from step 2 below, for example
   `https://paisa-footprint.vercel.app`. You can come back and set it after the first Vercel deploy.
4. Click **Apply**. The first build takes a few minutes. When it is done, open
   `https://<your-service>.onrender.com/health`: it should say `"companies": 20`.
5. `autoDeploy` is off, so new commits don't redeploy by themselves. Use **Manual Deploy** when you
   want to update.

Free Render services sleep when idle, so the first request after a while takes 30–60 seconds.

**Using a real snapshot later:** build it on your laptop (`docs/RUN_ON_LAPTOP.md`), then either
copy it into the image (add a `COPY data/snapshots/<YYYY-MM> /app/data/snapshots/<YYYY-MM>`
line and set `PF_SNAPSHOT_DIR` to match) or attach a Render disk. Snapshots are small.

## 2. Web app on Vercel

1. Sign in at vercel.com, choose **Add New → Project**, and import `ajxlv/paisa-footprint`.
2. Set **Root Directory** to `web`. `web/vercel.json` already sets the Vite build, the `dist`
   output and the single-page-app rewrite, so deep links like `/companies/INE584A01023` work.
3. Under **Environment Variables**, add `VITE_API_URL` = your Render URL, e.g.
   `https://paisa-footprint-api.onrender.com` (no trailing slash). Vite bakes this in at build
   time, so redeploy after changing it.
4. Deploy, then copy the Vercel URL into Render's `PF_CORS_ORIGINS` (step 1.3) and redeploy the API.

## 3. Check it

- Open the Vercel URL. The Home page tiles should read 20 companies, 75% reporting and 14 data
  problems.
- Open **Portfolio calculator → Load illustrative example → Compute**. You should see financed
  emissions of 83.2346 t and the amber illustrative banner.
- If pages show "Could not load data from the API": check `VITE_API_URL` on Vercel and
  `PF_CORS_ORIGINS` on Render, and remember the free API may be waking up.

## Alternative: one machine with Docker

```bash
docker compose up --build    # API on :8000, web on :8080
```
