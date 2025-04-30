// lp-portal/pages/index.tsx
import React, { useEffect, useState } from 'react';
import { GetServerSideProps } from 'next';
import { createServerSupabaseClient } from '@supabase/auth-helpers-nextjs';
import useSWR from 'swr';
import { supa } from '../lib/supa';

// Define interface for Supabase file objects (more specific)
interface SupabaseFile {
    name: string;
    id: string;
    updated_at: string;
    created_at: string;
    last_accessed_at: string;
    metadata: Record<string, any>;
}

export default function Home() {
    const [pnl, setPnl] = useState<string | null>(null);
    const [links, setLinks] = useState<SupabaseFile[]>([]); // Use specific type
    const [error, setError] = useState<string | null>(null);
    const [loadingReports, setLoadingReports] = useState<boolean>(true);
    const [daily, setDaily] = useState<any[]>([]);

    // SWR fetcher
    const fetcher = (url: string) => fetch(url).then((r) => r.json());
    const { data: pnlResp, error: pnlErr } = useSWR('/api/pnl', fetcher, {
        refreshInterval: 15000,
    });

    useEffect(() => {
        // Convert SWR data to formatted pnl string
        if (pnlResp?.pnl !== undefined) {
            setPnl(
                Number(pnlResp.pnl).toLocaleString('en-US', {
                    style: 'currency',
                    currency: 'USD',
                    minimumFractionDigits: 0,
                    maximumFractionDigits: 0,
                })
            );
        }

        if (pnlErr) {
            setError(pnlErr.message);
        }

        // Fetch report links from Supabase storage
        const fetchReports = async () => {
            setLoadingReports(true);
            setError(null);
            try {
                const { data, error: listError } = await supa.storage.from('reports').list(undefined, {
                    limit: 100,
                    offset: 0,
                    sortBy: { column: 'created_at', order: 'desc' },
                });

                if (listError) throw listError;

                // Ensure data is an array and filter placeholder files
                const validFiles = Array.isArray(data) ? data.filter(f => f.name !== '.emptyFolderPlaceholder') : [];
                setLinks(validFiles);

            } catch (err) {
                console.error('Error listing reports:', err);
                setError(err instanceof Error ? err.message : 'Failed to list reports.');
                setLinks([]);
            } finally {
                setLoadingReports(false);
            }
        };

        fetchReports();

        // fetch daily summary parquet rows
        fetch('/api/summary')
          .then(r => r.json())
          .then(d => setDaily(d.rows || []))
          .catch(e => console.error('summary fetch', e));
    }, [pnlResp, pnlErr]);

    return (
        <main className="min-h-screen bg-gradient-to-br from-gray-50 to-indigo-100 flex flex-col items-center py-12 px-4 sm:px-6 lg:px-8">
            <div className="w-full max-w-md">
                <h1 className="text-3xl sm:text-4xl font-bold text-center text-gray-800 mb-8">
                    Dynasty LP Portal
                </h1>

                {error && (
                    <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative mb-6" role="alert">
                        <strong className="font-bold">Error: </strong>
                        <span className="block sm:inline">{error}</span>
                    </div>
                )}

                <div className="bg-white shadow-xl rounded-2xl p-6 mb-10 text-center ring-1 ring-gray-200">
                    <p className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-1">Live Cumulative PnL</p>
                    {!pnl ? (
                        <div className="animate-pulse h-10 bg-gray-200 rounded w-3/4 mx-auto mt-2"></div>
                    ) : (
                        <p className={`text-4xl font-semibold ${pnl && parseFloat(pnl.replace(/[^\d.-]/g, '')) >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                            {pnl ?? 'Loading...'}
                        </p>
                    )}
                </div>

                <div className="bg-white shadow-lg rounded-lg p-6 ring-1 ring-gray-100">
                    <h2 className="text-xl font-semibold text-gray-700 mb-4 border-b pb-2">Monthly Reports</h2>
                    {loadingReports ? (
                        <p className="text-gray-500 italic">Loading reports...</p>
                    ) : links.length > 0 ? (
                        <ul className="space-y-2">
                            {links.map(file => (
                                <li key={file.id} className="flex items-center justify-between hover:bg-gray-50 p-2 rounded">
                                    <span className="text-gray-800 font-medium truncate pr-4">{file.name}</span>
                                    <a
                                        href={`/api/report?name=${encodeURIComponent(file.name)}`}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-sm text-indigo-600 hover:text-indigo-800 font-semibold whitespace-nowrap underline"
                                    >
                                        View PDF
                                    </a>
                                </li>
                            ))}
                        </ul>
                    ) : (
                        <p className="text-gray-500 italic text-center py-4">No reports found in the 'reports' bucket.</p>
                    )}
                    {daily.length > 0 && (
                      <div className="mt-6">
                        <h3 className="text-md font-semibold mb-2">Daily Summary</h3>
                        <table className="min-w-full text-sm text-left">
                          <thead>
                            <tr>
                              <th className="px-2 py-1">Date</th>
                              <th className="px-2 py-1">Symbol</th>
                              <th className="px-2 py-1 text-right">Trades</th>
                              <th className="px-2 py-1 text-right">PnL</th>
                            </tr>
                          </thead>
                          <tbody>
                            {daily.slice(0, 30).map((r, i) => (
                              <tr key={i} className="border-t">
                                <td className="px-2 py-1">{r.date}</td>
                                <td className="px-2 py-1">{r.symbol}</td>
                                <td className="px-2 py-1 text-right">{r.trades}</td>
                                <td className="px-2 py-1 text-right">{r.last_price?.toFixed?.(2)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                </div>
            </div>
        </main>
    );
}

export const getServerSideProps: GetServerSideProps = async (ctx) => {
    const supabase = createServerSupabaseClient(ctx);
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) {
        return {
            redirect: {
                destination: '/login',
                permanent: false,
            },
        };
    }
    return { props: {} };
};
