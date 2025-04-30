import type { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  const promUrl = process.env.NEXT_PUBLIC_PROM_URL;
  if (!promUrl) {
    return res.status(500).json({ error: 'Prometheus URL not configured' });
  }

  try {
    const promRes = await fetch(
      `${promUrl}/api/v1/query?query=dynasty_cumulative_pnl`
    );
    if (!promRes.ok) {
      return res.status(promRes.status).json({ error: promRes.statusText });
    }
    const data = await promRes.json();
    const pnl = data?.data?.result?.[0]?.value?.[1];

    res.setHeader('Cache-Control', 's-maxage=15, stale-while-revalidate=30');
    return res.status(200).json({ pnl });
  } catch (err) {
    return res.status(500).json({ error: 'Failed to query Prometheus' });
  }
}
