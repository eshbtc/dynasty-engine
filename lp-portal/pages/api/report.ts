/// <reference types="node" /> // Add reference for Node.js types like Buffer

import type { NextApiRequest, NextApiResponse } from 'next';
import { createClient } from '@supabase/supabase-js';
import { Buffer } from 'buffer'; // Explicitly import Buffer

// Server-side credentials only: expose SERVICE KEY via env var (not NEXT_PUBLIC_)
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseServiceKey = process.env.SUPABASE_SERVICE_KEY; // Use the secret service key

if (!supabaseUrl || !supabaseServiceKey) {
  // Log error server-side, return generic error to client
  console.error('Supabase URL or Service Key is not defined in environment variables.');
  // Avoid throwing here in production, send a 500 response instead
  // throw new Error('Server configuration error.');
}

// Create a Supabase client instance specifically for this API route using the service key
// Handle potential missing config gracefully
const supaAdmin = supabaseUrl && supabaseServiceKey ? createClient(supabaseUrl, supabaseServiceKey) : null;

export default async function handler(req: NextApiRequest, res: NextApiResponse) {

  if (!supaAdmin) {
    return res.status(500).json({ error: 'Server configuration error.' });
  }

  // Basic security: Check if user is authenticated (implement Supabase auth check if needed)
  // const { data: { user } } = await supaAdmin.auth.getUser(req.headers.authorization?.split('Bearer ')[1]);
  // if (!user) {
  //   return res.status(401).json({ error: 'Unauthorized' });
  // }

  if (req.method !== 'GET') {
    res.setHeader('Allow', ['GET']);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
  }

  const reportName = req.query.name as string;

  if (!reportName || typeof reportName !== 'string') { // Validate input type
    return res.status(400).json({ error: 'Report name parameter is required and must be a string.' });
  }

  // Sanitize filename - prevent directory traversal
  const safeReportName = reportName.replace(/\.\.\//g, ''); // Basic sanitization
  if (safeReportName !== reportName) {
      return res.status(400).json({ error: 'Invalid report name.' });
  }

  try {
    console.log(`Attempting to download report: ${safeReportName} from bucket 'reports'`);
    // Download the file from Supabase storage
    const { data, error } = await supaAdmin.storage
      .from('reports') // Ensure this matches your bucket name
      .download(safeReportName); // Use sanitized name

    if (error) {
      console.error('Supabase storage download error:', error);
      // Provide more specific error messages if possible
      if (error.message.includes('Not found') || error.message.includes('OBJECT_NOT_FOUND')) {
         return res.status(404).json({ error: `Report '${safeReportName}' not found.` });
      }
      return res.status(500).json({ error: `Failed to download report: ${error.message}` });
    }

    if (!data) {
       return res.status(404).json({ error: `Report '${safeReportName}' data is empty or invalid.` });
    }

    console.log(`Successfully downloaded report: ${safeReportName}, size: ${data.size} bytes`);

    // Set appropriate headers for PDF download
    res.setHeader('Content-Type', 'application/pdf');
    res.setHeader('Content-Disposition', `inline; filename="${safeReportName}"`); // inline to display in browser
    // res.setHeader('Content-Disposition', `attachment; filename="${safeReportName}"`); // attachment to force download

    // Cache for 1 hour (private because PDFs may be investor-specific)
    res.setHeader('Cache-Control', 'private, max-age=3600');

    // Validate content type if available
    if (data.type && data.type !== 'application/pdf') {
      return res.status(415).json({ error: 'Unsupported media type returned from storage.' });
    }

    // Convert Blob (returned by supa storage download) to Buffer and send response
    const buffer = Buffer.from(await data.arrayBuffer());
    res.send(buffer);

  } catch (err) {
    console.error(`Unexpected error in /api/report for file ${safeReportName}:`, err);
    res.status(500).json({ error: 'An unexpected server error occurred.' });
  }
}
