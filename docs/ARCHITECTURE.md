# Dynasty Engine — Architecture & Vision

> **Purpose**: Provide a single, authoritative reference for every moving part of the Dynasty trading stack—code, data flow, model lifecycle, monitoring and mobile operations—so a new engineer or quant can ramp up in minutes rather than weeks.

---
## 0. Bird-eye Vision
* **Ambition** – Autonomously trade multi-asset portfolios using deep reinforcement-learning while respecting stringent risk controls and delivering fully transparent, human-friendly telemetry.
* **North-star KPI** – Risk-adjusted return (Sharpe) against market benchmarks with a max 5 % intraday draw-down.
* **Core pillars**   
  ① Research → **`train_rl.py` + Optuna** nightly research loop  
  ② Execution → **`multi_asset_manager.py` + `rl_policy.py`** act in live markets  
  ③ Safety → **`risk_manager.py`** veto & kill-switch  
  ④ Observability → Prom / Grafana, LP Portal, **Dynasty Mobile**  
  ⑤ Ops CI → GitHub Actions + Expo EAS TestFlight builds

---
## 1. End-to-End Data & Control Flow
```
┌─────────────┐    1 OHLC/IV                    ┌───────────────┐
│ data_provider│  ────────────────►  CSV/Parquet│ feature_builder│
└─────────────┘                                └───────────────┘
          ▲                                            │ obs[]
          │ 8 draw-down / manual halt                  ▼
┌──────────────┐    2 train + Optuna        ┌────────────────────┐   3 decide action
│  train_rl.py │ ─────────────────────────► │ rl_policy.decide   │ ────────────────► exchange / broker
└──────────────┘  model.zip + norm.pkl     └────────────────────┘
          │ save                       ▲              │ trade_decision
          ▼                            │ 4 update NAV │
  model_registry                      │              ▼
          │ 9 new version           ┌────────────────────┐
          ▼          push alert     │ risk_manager      │
 metrics_exporter.send_push ◄───────┴────────────────────┘
          │ 6 metrics                         │ veto
          │                                   ▼
   Prometheus ─────────► Grafana dashboard ◄─── episode_logger (csv)
                                                │
                                                ▼ nightly
                                   reflect.py → daily_summary.parquet
```
Legend: **blue numbers** denote stages referenced in §2.

---
## 2. Module Deep-Dive
| # | File | Stage | Responsibility |
|---|----------------------------------------|--------|-------------------------------------------------------------|
| 1 | `data_provider.py` | Data ingest | Fetch IV Rank (Polygon / Tradier), crypto realised vol (Deribit). Fail-safe fall-back with logging. |
| 2 | `train_rl.py` | Training | Loads CSV features, spawns `stable-baselines3.PPO`, checkpoints to `model_registry`. |
|   | `rl/hyperparam_search.py` | Research | Optuna study + cross-val; stores best model with meta-params. |
|   | `model_registry.py` | Storage | Timestamped directory per symbol (`models/<sym>/<ts>_run`). |
| 3 | `rl_policy.py` | Inference | Loads latest model + `VecNormalize`, returns discrete action (0 hold / 1 buy / 2 sell), **robust to missing/corrupt models, logs fallback to HOLD**. |
| 4 | `multi_asset_manager.py` | Execution | Builds obs via `feature_builder`, asks RL policy, applies **Kelly sizing** & risk veto before sending orders. **Now includes retry logic and robust error handling for data fetches and trading logic.** |
| 5 | `dyn_engine/risk_manager.py` | Safety | Tracks max NAV, computes draw-down, honours `settings.dynasty_halt`. **Now logs and handles all error paths robustly.** |
| 6 | `metrics_exporter.py` | Telemetry | Exposes Prometheus HTTP on :8000, pushes Expo notifications (`send_push`). **Prometheus metrics endpoint integrated with Flask API for Cloud Run.** |
| 7 | `episode_logger.py` | Logging | Appends every RL step to `data/trades_episodes.csv`. |
| 8 | `reflect.py` | Analytics | Nightly cron summarises step CSV → `daily_summary.parquet`. |
| 9 | `.github/workflows/rl_train.yml` | CI | Nightly retrain, commits new model, updates dashboard metric. |

### Front-ends
| Directory | Tech | Key files | Notes |
|-----------|------|-----------|-------|
| `lp-portal/` | Next.js + Tailwind | `pages/index.tsx`, `api/*.ts` | Web dashboard & PDF report viewer. |
| `apps/dynasty-mobile/` | Expo React-Native | `App.tsx`, `screens/*.tsx` | iOS TestFlight – live PnL, trades list, push alerts. |

---
## 3. Environment & Config
* **Secrets** – `POLYGON_KEY`, `TRADIER_KEY`, `SUPABASE_*` via GitHub / Apple Secrets.  
* **Settings** – `settings.py` centralises commission, slippage, halt flag.  
* **Pre-commit** – Black, Ruff, Bandit enforce style & security.

---
## 4. Monitoring & Alerting
| Metric | Origin | Description |
|--------|--------|-------------|
| `dynasty_drawdown_pct` | `metrics_exporter` | Current draw-down vs max equity. |
| `dynasty_sharpe` | ″ | Rolling 50-step Sharpe. |
| `dynasty_action_total{symbol,action}` | ″ | Action counters. |
| `dynasty_model_version{symbol}` | ″ | Unix timestamp of active model. |
| `dynasty_rl_infer_ms{symbol}` | ″ | RL inference latency in milliseconds (p50). |
| **Push alerts** | `send_push()` | Draw-down breach, trade confirmations, model roll-over. |

---
## 5. Mobile UX (iOS-only)
* **Dashboard tab** – Large PnL number, sparkline of last 1 d NAV, today’s summary stats.  
* **Trades tab** – Infinite scroll FlashList, badges: BUY green, SELL red.  
* **Notifications** – Expo push; first app launch registers device token via `/api/register_device`.

---
## 6. Robustness & Reliability Improvements (Spring 2025)
- **Comprehensive error handling** added to all core modules (`trading_env.py`, `multi_asset_manager.py`, `rl_policy.py`, `risk_manager.py`, `execution.py`, `backtest_harness.py`).
- **Retry logic** for asset data fetches and API calls.
- **Logging** for all error paths and fallbacks (including RL model inference and trade execution).
- **Prometheus metrics endpoint** integrated directly into Flask API for Cloud Run compatibility.
- **Dockerfile** updated to use Gunicorn for API serving; Streamlit references removed.
- **Requirements** cleaned for duplicate/conflicting entries.
- **Robustness review process**: All critical files reviewed for execution gaps and improved without breaking downstream APIs.

---
## 7. Roadmap
1. Adaptive risk limits (vol-scaled).  
2. Synthetic training (dreamer) to boost data efficiency.  
3. AWS Secrets Manager migration.  
4. Auto-deploy LP Portal & Mobile via GitHub Actions (CI → EAS).

---
## 7. Repository Top-Level Map
```
/ dyn_engine/               Core python libs
   ├─ risk_manager.py
   ├─ logging_config.py
   └─ ...
/ rl/                       Training helpers
   ├─ hyperparam_search.py
   └─ ...
/ models/                   Saved RL checkpoints (git-ignored)
/ data/                     Episode CSV + parquet summaries
/ jobs/                     Scheduled batch tasks (self_tuner, walk_forward)
/ lp-portal/                Next.js dashboard
/ apps/dynasty-mobile/      Expo iOS app
/ .github/workflows/        CI pipelines
/ docs/                     ← you are here
```

---
## 8. Getting Started (Dev)
```bash
# 1) Clone & install
poetry install   # or pip -r requirements.txt
npm --prefix lp-portal i
npm --prefix apps/dynasty-mobile i

# 2) Run services
python metrics_exporter.py &   # :8000/metrics
npm --prefix lp-portal run dev  # web dashboard
expo start -p 8081              # iOS simulator

# 3) Trigger a dummy trade for smoke-test
auto_trade.py --symbol AAPL --dry
```

_This document will be updated automatically by CI when new modules are added._
