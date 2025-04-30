import type { NextApiRequest, NextApiResponse } from 'next';
import fs from 'fs';
import path from 'path';

const STORE = path.join(process.cwd(), '..', 'data', 'device_tokens.json');

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') return res.status(405).end();
  const { token, os } = req.body as { token: string; os: string };
  if (!token) return res.status(400).json({ error: 'missing_token' });
  let arr: any[] = [];
  if (fs.existsSync(STORE)) arr = JSON.parse(fs.readFileSync(STORE, 'utf-8'));
  if (!arr.find((d) => d.token === token)) arr.push({ token, os });
  fs.writeFileSync(STORE, JSON.stringify(arr));
  res.status(200).json({ ok: true });
}
