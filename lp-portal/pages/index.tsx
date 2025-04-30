// lp-portal/pages/index.tsx
import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
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
    const router = useRouter();
    const [authLoading, setAuthLoading] = useState(true);
    const [user, setUser] = useState<any>(null);
    const [pnl, setPnl] = useState<string | null>(null);
    const [links, setLinks] = useState<SupabaseFile[]>([]); // Use specific type
    const [error, setError] = useState<string | null>(null);
    const [loadingReports, setLoadingReports] = useState<boolean>(true);
    const [daily, setDaily] = useState<any[]>([]);
    // RL/analytics state
    const [rlStatus, setRlStatus] = useState<any>(null);
    const [openPositions, setOpenPositions] = useState<any[]>([]);
    const [stopLossEvents, setStopLossEvents] = useState<any[]>([]);
    // Backtest history state
    const [backtestList, setBacktestList] = useState<any[]>([]);
    const [selectedBacktest, setSelectedBacktest] = useState<string>('');
    const [backtest, setBacktest] = useState<any>(null);
    // Drill-down modal state
    const [drillSymbol, setDrillSymbol] = useState<string | null>(null);
    // SWR fetcher
    const fetcher = (url: string) => fetch(url).then((r) => r.json());
    const { data: pnlResp, error: pnlErr } = useSWR('/api/pnl', fetcher, {
        refreshInterval: 15000,
    });
    // Auto-refresh and last update
    const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

    // Client-side Supabase auth check
    useEffect(() => {
        supa.auth.getUser().then(({ data }) => {
            setUser(data.user);
            setAuthLoading(false);
            if (!data.user) {
                router.replace('/login');
            }
        });
    }, [router]);

    useEffect(() => {
        const fetchAll = () => {
            fetch('/api/rl_status').then(r => r.json()).then(setRlStatus).catch(() => {});
            fetch('/api/open_positions').then(r => r.json()).then(d => setOpenPositions(d.positions || [])).catch(() => {});
            fetch('/api/stop_loss_events').then(r => r.json()).then(d => setStopLossEvents(d.events || [])).catch(() => {});
            fetch('/api/backtest_list').then(r => r.json()).then(d => {
                setBacktestList(d.backtests || []);
                if (d.backtests && d.backtests.length > 0) {
                    setSelectedBacktest(prev => prev || d.backtests[0].filename);
                }
            }).catch(() => {});
            setLastUpdated(new Date());
        };
        fetchAll();
        const interval = setInterval(fetchAll, 15000);
        return () => clearInterval(interval);
    }, []);

    useEffect(() => {
        if (selectedBacktest) {
            fetch(`/api/backtest_results?file=${encodeURIComponent(selectedBacktest)}`)
                .then(r => r.json()).then(setBacktest).catch(() => setBacktest(null));
        } else {
            setBacktest(null);
        }
    }, [selectedBacktest]);

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

                {/* RL Status Banner */}
                {rlStatus && (
                  <div className={`mb-6 p-4 rounded-xl text-white ${rlStatus.target_achieved ? 'bg-emerald-500' : 'bg-red-500'} shadow`}>
                    <div className="flex items-center justify-between">
                      <span className="font-bold">RL Monthly PnL:</span>
                      <span className="text-lg">{rlStatus.monthly_pnl?.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })}</span>
                    </div>
                    <div className="flex items-center justify-between mt-1">
                      <span className="font-bold">5% Target:</span>
                      <span>{rlStatus.target_achieved ? '✅ Achieved' : '❌ Not Yet'}</span>
                    </div>
                    <div className="flex items-center justify-between mt-1">
                      <span className="font-bold">Drawdown:</span>
                      <span>{(rlStatus.drawdown * 100).toFixed(2)}%</span>
                    </div>
                  </div>
                )}

                {/* Open Positions Table */}
                <div className="bg-white shadow rounded-lg mb-6 p-4">
                  <h2 className="text-lg font-semibold mb-2">Open Positions</h2>
                  <div className="text-xs text-gray-500 mb-2">Auto-refreshes every 15s. Last updated: {lastUpdated ? lastUpdated.toLocaleTimeString() : '...'}</div>
                  {openPositions.length === 0 ? (
                    <p className="text-gray-500 italic">No open positions.</p>
                  ) : (
                    <table className="min-w-full text-sm">
                      <thead>
                        <tr>
                          <th className="px-2 py-1">Symbol</th>
                          <th className="px-2 py-1">Entry</th>
                          <th className="px-2 py-1">Qty</th>
                          <th className="px-2 py-1">Stop-Loss</th>
                          <th className="px-2 py-1">Side</th>
                        </tr>
                      </thead>
                      <tbody>
                        {openPositions.map((pos, i) => (
                          <tr key={i} className="border-t">
                            <td className="px-2 py-1">
                              <a href="#" className="text-blue-700 underline" onClick={e => {e.preventDefault(); setDrillSymbol(pos.symbol);}}>{pos.symbol}</a>
                            </td>
                            <td className="px-2 py-1">{Number(pos.entry_price).toFixed(2)}</td>
                            <td className="px-2 py-1">{pos.qty}</td>
                            <td className="px-2 py-1">{Number(pos.stop_loss).toFixed(2)}</td>
                            <td className="px-2 py-1">{pos.side}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>

                {/* Stop-Loss Events Table */}
                <div className="bg-white shadow rounded-lg mb-6 p-4">
                  <h2 className="text-lg font-semibold mb-2">Stop-Loss Events</h2>
                  {stopLossEvents.length === 0 ? (
                    <p className="text-gray-500 italic">No stop-loss events.</p>
                  ) : (
                    <table className="min-w-full text-sm">
                      <thead>
                        <tr>
                          <th className="px-2 py-1">Symbol</th>
                          <th className="px-2 py-1">Action</th>
                          <th className="px-2 py-1">Qty</th>
                          <th className="px-2 py-1">Entry</th>
                          <th className="px-2 py-1">Exit</th>
                          <th className="px-2 py-1">Stop-Loss</th>
                          <th className="px-2 py-1">Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {stopLossEvents.slice(-20).reverse().map((ev, i) => (
                          <tr key={i} className="border-t">
                            <td className="px-2 py-1">
                              <a href="#" className="text-blue-700 underline" onClick={e => {e.preventDefault(); setDrillSymbol(ev.symbol);}}>{ev.symbol}</a>
                            </td>
                            <td className="px-2 py-1">{ev.action}</td>
                            <td className="px-2 py-1">{ev.qty}</td>
                            <td className="px-2 py-1">{Number(ev.entry_price).toFixed(2)}</td>
                            <td className="px-2 py-1">{Number(ev.exit_price).toFixed(2)}</td>
                            <td className="px-2 py-1">{Number(ev.stop_loss).toFixed(2)}</td>
                            <td className="px-2 py-1">{ev.status}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>

                {/* Drill-down Modal for Trade Details */}
                {drillSymbol && (
                  <div className="fixed z-50 inset-0 bg-black bg-opacity-40 flex items-center justify-center">
                    <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-2xl relative">
                      <button className="absolute top-2 right-3 text-2xl" onClick={() => setDrillSymbol(null)}>&times;</button>
                      <h3 className="text-lg font-bold mb-2">Trade Details: {drillSymbol}</h3>
                      {backtest && backtest.trades ? (
                        <table className="min-w-full text-sm mb-2">
                          <thead>
                            <tr>
                              <th className="px-2 py-1">Date</th>
                              <th className="px-2 py-1">Action</th>
                              <th className="px-2 py-1">Price</th>
                            </tr>
                          </thead>
                          <tbody>
                            {backtest.trades.filter((t: any) => t.symbol === drillSymbol).map((t: any, i: number) => (
                              <tr key={i} className="border-t">
                                <td className="px-2 py-1">{t.date}</td>
                                <td className="px-2 py-1">{t.action}</td>
                                <td className="px-2 py-1">{Number(t.price).toFixed(2)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      ) : (
                        <div className="text-gray-500 italic">No trade log available for this symbol in current backtest.</div>
                      )}
                      <button className="mt-2 px-4 py-2 rounded bg-blue-600 text-white" onClick={() => setDrillSymbol(null)}>Close</button>
                    </div>
                  </div>
                )}

                {/* Backtest Results Section (Multi-Backtest) */}
                <div className="bg-white shadow rounded-lg mb-6 p-4">
                  <h2 className="text-lg font-semibold mb-2">Backtest Results</h2>
                  {/* Backtest selection dropdown */}
                  <div className="mb-4">
                    <label className="mr-2 font-medium">Select Backtest:</label>
                    <select
                      className="border rounded px-2 py-1"
                      value={selectedBacktest}
                      onChange={e => setSelectedBacktest(e.target.value)}
                    >
                      {backtestList.map((b: any, i: number) => (
                        <option key={b.filename} value={b.filename}>
                          {b.strategy || b.filename} ({b.start_date} → {b.end_date})
                        </option>
                      ))}
                    </select>
                    {selectedBacktest && (
                      <a
                        href={`/api/backtest_trades?file=${encodeURIComponent(selectedBacktest)}`}
                        className="ml-4 text-blue-600 underline"
                        download
                      >
                        Download Trades CSV
                      </a>
                    )}
                  </div>
                  {!backtest || !backtest.summary ? (
                    <p className="text-gray-500 italic">No backtest results available.</p>
                  ) : (
                    <>
                      <div className="flex flex-wrap gap-4 mb-4">
                        <div className="bg-gray-50 rounded p-3 flex-1 min-w-[120px]">
                          <div className="text-xs text-gray-500">Strategy</div>
                          <div className="font-semibold">{backtest.summary.strategy}</div>
                        </div>
                        <div className="bg-gray-50 rounded p-3 flex-1 min-w-[120px]">
                          <div className="text-xs text-gray-500">PnL</div>
                          <div className="font-semibold">{Number(backtest.summary.pnl).toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })}</div>
                        </div>
                        <div className="bg-gray-50 rounded p-3 flex-1 min-w-[120px]">
                          <div className="text-xs text-gray-500"># Trades</div>
                          <div className="font-semibold">{backtest.summary.num_trades}</div>
                        </div>
                        <div className="bg-gray-50 rounded p-3 flex-1 min-w-[120px]">
                          <div className="text-xs text-gray-500">Period</div>
                          <div className="font-semibold">{backtest.summary.start_date} → {backtest.summary.end_date}</div>
                        </div>
                        {/* Additional metrics */}
                        {backtest.summary.sharpe !== undefined && (
                          <div className="bg-gray-50 rounded p-3 flex-1 min-w-[120px]">
                            <div className="text-xs text-gray-500">Sharpe</div>
                            <div className="font-semibold">{Number(backtest.summary.sharpe).toFixed(2)}</div>
                          </div>
                        )}
                        {backtest.summary.max_drawdown !== undefined && (
                          <div className="bg-gray-50 rounded p-3 flex-1 min-w-[120px]">
                            <div className="text-xs text-gray-500">Max Drawdown</div>
                            <div className="font-semibold">{Number(backtest.summary.max_drawdown).toLocaleString('en-US', { style: 'percent', minimumFractionDigits: 2 })}</div>
                          </div>
                        )}
                        {backtest.summary.win_rate !== undefined && (
                          <div className="bg-gray-50 rounded p-3 flex-1 min-w-[120px]">
                            <div className="text-xs text-gray-500">Win Rate</div>
                            <div className="font-semibold">{Number(backtest.summary.win_rate).toLocaleString('en-US', { style: 'percent', minimumFractionDigits: 1 })}</div>
                          </div>
                        )}
                      </div>
                      {/* Equity Curve Chart */}
                      {backtest.equity_curve && backtest.equity_curve.length > 2 && (
                        <div className="mb-4">
                          <h3 className="text-sm font-semibold mb-1">Equity Curve</h3>
                          <svg width="100%" height="120" viewBox={`0 0 400 120`} className="bg-gray-100 rounded">
                            {(() => {
                              const curve = backtest.equity_curve;
                              const min = Math.min(...curve.map((p: any) => p.value));
                              const max = Math.max(...curve.map((p: any) => p.value));
                              const scaleX = (i: number) => (i / (curve.length - 1)) * 400;
                              const scaleY = (v: number) => 110 - ((v - min) / (max - min + 1e-9)) * 100;
                              const points = curve.map((p: any, i: number) => `${scaleX(i)},${scaleY(p.value)}`).join(' ');
                              return (
                                <polyline
                                  fill="none"
                                  stroke="#2563eb"
                                  strokeWidth="2"
                                  points={points}
                                />
                              );
                            })()}
                          </svg>
                        </div>
                      )}
                      <div className="overflow-x-auto">
                        <table className="min-w-full text-sm">
                          <thead>
                            <tr>
                              <th className="px-2 py-1">Date</th>
                              <th className="px-2 py-1">Action</th>
                              <th className="px-2 py-1">Price</th>
                            </tr>
                          </thead>
                          <tbody>
                            {backtest.trades?.slice(-50).reverse().map((t: any, i: number) => (
                              <tr key={i} className="border-t">
                                <td className="px-2 py-1">{t.date}</td>
                                <td className="px-2 py-1">{t.action}</td>
                                <td className="px-2 py-1">{Number(t.price).toFixed(2)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </>
                  )}
                </div>

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
                        <p className="text-gray-500 italic text-center py-4">No reports found in the &apos;reports&apos; bucket.</p>
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

