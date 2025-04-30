# ------------------------------------------------------------------
# walk_forward.py  (S‑B)
# ------------------------------------------------------------------
"""Nightly job: run back‑test trailing 2yrs w/ current cfg."""
import subprocess
import datetime
import slack_notify as sn
import yaml
import os
import sys

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.yaml')
BACKTEST_SCRIPT = os.path.join(os.path.dirname(__file__), 'backtest_harness.py')
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')

def load_assets_from_config():
    try:
        with open(CONFIG_PATH) as f:
            config = yaml.safe_load(f)
            return list(config.get('assets', {}).keys())
    except FileNotFoundError:
        print(f"Error: Config file not found at {CONFIG_PATH}")
        return []
    except Exception as e:
        print(f"Error loading config: {e}")
        return []

print("Starting nightly walk-forward backtest...")
window_start = (datetime.date.today() - datetime.timedelta(days=730)).isoformat()
today_iso = datetime.date.today().isoformat()
assets_to_test = load_assets_from_config()

if not assets_to_test:
    print("No assets found in config to test. Exiting.")
    sys.exit(0) # Exit cleanly if no assets

print(f"Testing assets: {', '.join(assets_to_test)}")
halted = False

for tkr in assets_to_test:
    path = os.path.join(DATA_DIR, f'{tkr}.csv')
    if not os.path.exists(path):
        print(f"Warning: Data file not found for {tkr} at {path}. Skipping.")
        continue

    command = ['python', BACKTEST_SCRIPT, tkr, window_start, today_iso, path]
    print(f"Running backtest for {tkr}: {' '.join(command)}")

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=300) # Added timeout
        output_lines = result.stdout.strip().split('\n')
        last_line = output_lines[-1]
        print(f"Backtest output for {tkr}: ... {last_line}")
        # Attempt to parse Sharpe ratio (assuming it's the last number in the output)
        # This is brittle; consider having backtest_harness output structured data (e.g., JSON)
        try:
            sharpe_str = last_line.split()[-1].strip('(),') # Basic parsing
            sharpe = float(sharpe_str)
            print(f"Parsed Sharpe for {tkr}: {sharpe:.2f}")
        except (ValueError, IndexError):
            print(f"Error: Could not parse Sharpe ratio from backtest output for {tkr}: '{last_line}'")
            sn.slack(f"🚨 Walk-forward Error: Could not parse Sharpe for {tkr}. Check backtest output.")
            continue # Continue to next ticker

        if sharpe < 0.4:
            halt_msg = f"⚠️ Walk‑forward alert: {tkr} Sharpe {sharpe:.2f} < 0.4 – Halting bot execution."
            print(halt_msg)
            sn.slack(halt_msg)
            halted = True
            # Consider additional actions: e.g., set DYNASTY_HALT env var, trigger alert system
            break # Stop further tests if one fails critically

    except FileNotFoundError:
        print(f"Error: Backtest script not found at {BACKTEST_SCRIPT}")
        halted = True; break
    except subprocess.CalledProcessError as e:
        print(f"Error running backtest for {tkr}: {e}")
        print(f"Stderr: {e.stderr}")
        sn.slack(f"🚨 Walk-forward Error: Backtest failed for {tkr}. Check logs.")
        halted = True; break # Halt on backtest error
    except subprocess.TimeoutExpired:
        print(f"Error: Backtest for {tkr} timed out after 300 seconds.")
        sn.slack(f"🚨 Walk-forward Error: Backtest timed out for {tkr}.")
        halted = True; break # Halt on timeout
    except Exception as e:
        print(f"An unexpected error occurred during backtest for {tkr}: {e}")
        sn.slack(f"🚨 Walk-forward Error: Unexpected error during backtest for {tkr}. Check logs.")
        halted = True; break # Halt on unexpected error

if halted:
    print("Walk-forward test failed. Exiting with error status.")
    sys.exit(1) # Exit with error code 1 to signal failure
else:
    print("Walk-forward tests completed successfully for all assets.")
    sys.exit(0) # Exit normally
