# Minimal REST API for Dynasty Engine analytics (stop-loss, positions, RL status)
# Uses Flask if available, falls back to Python http.server otherwise

import os
import json
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()
import sqlite3
import pandas as pd
import datetime
from flask_cors import CORS
from prometheus_client import make_wsgi_app
from werkzeug.middleware.dispatcher import DispatcherMiddleware
import threading

app = Flask(__name__)
CORS(app)

# --- Prometheus Metrics Integration ---
try:
    from exporter_prom import collect_metrics
    def metrics_before_response(environ, start_response):
        # Run metrics collection before serving metrics
        try:
            # Run in a thread to avoid blocking
            t = threading.Thread(target=collect_metrics)
            t.start()
            t.join(timeout=5)
        except Exception as e:
            print(f"Metrics collection error: {e}")
        return make_wsgi_app()(environ, start_response)
    app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {'/metrics': metrics_before_response})
except ImportError as e:
    print(f"Prometheus integration failed: {e}")

# --- Stop-Loss Events Endpoint ---
@app.route('/api/stop_loss_events')
def stop_loss_events():
    events = []
    if os.path.exists('data/stop_loss_events.csv'):
        with open('data/stop_loss_events.csv') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 7:
                    events.append({
                        'symbol': parts[0],
                        'action': parts[1],
                        'qty': parts[2],
                        'entry_price': parts[3],
                        'exit_price': parts[4],
                        'stop_loss': parts[5],
                        'event': parts[6],
                        'status': parts[7] if len(parts) > 7 else None
                    })
    return jsonify({'events': events})

# --- Open Positions Endpoint ---
@app.route('/api/open_positions')
def open_positions():
    # For now, load from a snapshot file if exists (since in-memory positions live in main process)
    positions = []
    if os.path.exists('data/open_positions.json'):
        with open('data/open_positions.json') as f:
            positions = json.load(f)
    return jsonify({'positions': positions})

# --- RL Status Endpoint ---
@app.route('/api/rl_status')
def rl_status():
    status = {'monthly_pnl': None, 'target_achieved': False, 'drawdown': None}
    # Try to load from file if available
    if os.path.exists('data/rl_status.json'):
        with open('data/rl_status.json') as f:
            status = json.load(f)
    return jsonify(status)

import glob
from flask import send_file, request

# --- Backtest List Endpoint ---
@app.route('/api/backtest_list')
def backtest_list():
    import os, json
    folder = 'data/backtests'
    os.makedirs(folder, exist_ok=True)
    files = sorted(glob.glob(os.path.join(folder, '*.json')), reverse=True)
    summaries = []
    for f in files:
        try:
            with open(f) as jf:
                data = json.load(jf)
            summary = data.get('summary', {})
            summary['filename'] = os.path.basename(f)
            summaries.append(summary)
        except Exception:
            continue
    return jsonify({'backtests': summaries})

# --- Backtest Results Endpoint (specific file) ---
@app.route('/api/backtest_results')
def backtest_results():
    import os, json
    fname = request.args.get('file')
    if fname:
        path = os.path.join('data/backtests', fname)
    else:
        # fallback to legacy single file
        path = 'data/backtest_results.json'
    if os.path.exists(path):
        with open(path) as f:
            results = json.load(f)
        return jsonify(results)
    return jsonify({})

# --- Backtest Trades CSV Download ---
@app.route('/api/backtest_trades')
def backtest_trades():
    import os, json, csv, io
    fname = request.args.get('file')
    if not fname:
        return ('Missing file param', 400)
    path = os.path.join('data/backtests', fname)
    if not os.path.exists(path):
        return ('Not found', 404)
    with open(path) as f:
        data = json.load(f)
    trades = data.get('trades', [])
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=['date','action','price'])
    writer.writeheader()
    for row in trades:
        writer.writerow(row)
    output.seek(0)
    return StreamingResponse(output, media_type='text/csv', headers={'Content-Disposition': 'attachment; filename=trades.csv'})

# --- Trades Table Endpoint ---
@app.get('/api/trades')
async def get_trades():
    db_path = 'trade_tracker.db'
    if not os.path.exists(db_path):
        return JSONResponse([])
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('SELECT * FROM trades ORDER BY timestamp DESC LIMIT 100')
    rows = c.fetchall()
    conn.close()
    trades = [
        {
            'timestamp': r[0], 'ticker': r[1], 'action': r[2], 'quantity': r[3],
            'strategy_price': r[4], 'avg_fill_price': r[5], 'commission': r[6], 'slippage_bp': r[7], 'status': r[8]
        }
        for r in rows
    ]
    return JSONResponse(trades)

# --- Agent Decisions Log Endpoint ---
@app.get('/api/agent-decisions')
async def get_agent_decisions():
    csv_path = 'data/agent_decisions.csv'
    if not os.path.exists(csv_path):
        return JSONResponse([])
    df = pd.read_csv(csv_path)
    if df.empty:
        return JSONResponse([])
    df = df.tail(50)
    return JSONResponse(df.to_dict(orient='records'))

# --- Bot Command Submission Endpoint ---
@app.post('/api/commands')
async def submit_command(command: str):
    if not command:
        return JSONResponse({'error': 'Missing command'}, status_code=400)
    entry = {"timestamp": str(datetime.datetime.now()), "command": command}
    try:
        with open('memory_store.json', 'a') as f:
            f.write(json.dumps(entry) + "\n")
        return JSONResponse({'status': 'success'})
    except Exception as e:
        return JSONResponse({'error': str(e)}, status_code=500)

# Health check endpoint
@app.get('/health')
async def health():
    return JSONResponse({'status': 'ok'})

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8008)
