import type { NextApiRequest, NextApiResponse } from 'next';
import fs from 'fs';
import path from 'path';
import csv from 'csv-parse/sync';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  const limit = parseInt((req.query.limit as string) || '50', 10);
  try {
    const root = process.cwd();
    const csvPath = path.join(root, '..', 'data', 'trades_episodes.csv');
    if (!fs.existsSync(csvPath)) {
      return res.status(404).json({ error: 'episodes_not_found' });
    }
    const raw = fs.readFileSync(csvPath, 'utf-8');
    const records = csv.parse(raw, { columns: true });
    const rows = records.slice(-limit).reverse(); // latest first
    return res.status(200).json({ rows });
  } catch (err) {
    console.error('episodes api error:', err);
    return res.status(500).json({ error: 'internal_error' });
  }
}
