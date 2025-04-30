// lp-portal/pages/api/summary.ts
import type { NextApiRequest, NextApiResponse } from 'next';
import fs from 'fs';
import path from 'path';
import parquet from 'parquets';

export default async function handler(
  _req: NextApiRequest,
  res: NextApiResponse,
) {
  try {
    const root = process.cwd(); // monorepo root when running `npm dev`
    const parquetPath = path.join(root, '..', 'data', 'daily_summary.parquet');
    if (!fs.existsSync(parquetPath)) {
      return res.status(404).json({ error: 'summary_not_found' });
    }
    const reader = await parquet.ParquetReader.openFile(parquetPath);
    const cursor = reader.getCursor();
    const rows: Record<string, unknown>[] = [];
    let record = await cursor.next();
    while (record) {
      rows.push(record);
      record = await cursor.next();
    }
    await reader.close();
    return res.status(200).json({ rows });
  } catch (err) {
    console.error('summary api error:', err);
    return res.status(500).json({ error: 'internal_error' });
  }
}
