# Dynasty LP Portal (MVP)

* Next.js 14 / TypeScript / Supabase Auth (magic‑link)
* Reads Prometheus `/api/v1/query?query=dynasty_cumulative_pnl` for live PnL
* Lists PDFs stored in Supabase bucket `reports`

### Local dev
```bash
cd lp-portal
cp .env.example .env.local    # fill SUPABASE keys + PROM_URL
npm install                   # or yarn install, or pnpm install
npm run dev                   # or yarn dev, or pnpm dev
```

### Docker
Build and run the portal in production‐like mode:

```bash
# From project root
docker compose build lp-portal
docker compose up lp-portal
# Portal available at http://localhost:3000
```

The compose file also builds the trading engine container so both can run side-by-side.

### Notes

*   Assumes Prometheus endpoint (`PROM_URL`) is publicly accessible or proxied.
*   Requires a Supabase project with:
    *   Auth configured (Magic Link recommended for simplicity).
    *   A storage bucket named `reports` with appropriate access policies (e.g., public read access or restricted access via RLS based on logged-in user).
*   The API route `/api/report` acts as a secure proxy to download reports from Supabase storage, preventing direct exposure of bucket details or signed URLs if policies are strict.
*   Basic UI, needs styling (e.g., Tailwind CSS which is common with Next.js).
*   Error handling in frontend fetch calls could be improved.
*   Needs environment variables set up correctly (`.env.local`) for Supabase URL/Key and Prometheus URL.
