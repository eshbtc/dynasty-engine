# Minimal REST API for Dynasty Engine analytics (stop-loss, positions, RL status)
# Uses Flask if available, falls back to Python http.server otherwise

import os
import json
from flask import Flask, jsonify, request
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
    return send_file(io.BytesIO(output.read().encode()), mimetype='text/csv', as_attachment=True, download_name='trades.csv')

# --- Trades Table Endpoint ---
@app.route('/api/trades')
def get_trades():
    db_path = 'trade_tracker.db'
    if not os.path.exists(db_path):
        return jsonify({'trades': []})
    try:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql_query('SELECT * FROM trades', conn)
        conn.close()
        trades = df.to_dict(orient='records')
        return jsonify({'trades': trades})
    except Exception as e:
        return jsonify({'error': str(e), 'trades': []})

# --- Agent Decisions Log Endpoint ---
@app.route('/api/agent-decisions')
def get_agent_decisions():
    csv_path = 'data/agent_decisions.csv'
    if not os.path.exists(csv_path):
        return jsonify({'decisions': []})
    try:
        df = pd.read_csv(csv_path)
        decisions = df.tail(50).to_dict(orient='records')
        return jsonify({'decisions': decisions})
    except Exception as e:
        return jsonify({'error': str(e), 'decisions': []})

# --- Bot Command Submission Endpoint ---
@app.route('/api/commands', methods=['POST'])
def submit_command():
    data = request.get_json()
    command = data.get('command')
    if not command:
        return jsonify({'error': 'Missing command'}), 400
    entry = {"timestamp": str(datetime.datetime.now()), "command": command}
    try:
        with open('memory_store.json', 'a') as f:
            f.write(json.dumps(entry) + "\n")
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8008, debug=True)
