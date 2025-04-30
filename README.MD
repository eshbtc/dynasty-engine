# Dynasty Engine — Multi-Asset RL Trading Platform

### Overview
Dynasty Engine autonomously trades equities, crypto futures & ETFs using deep reinforcement-learning with strict risk controls. It ships real-time telemetry via Prometheus/Grafana plus a Next.js dashboard & Expo iOS app for operations.

### Features
- Interactive Brokers multi-asset execution
- Deep RL policy (Stable-Baselines3 PPO) with Optuna hyper-param search
- Kelly sizing & draw-down risk manager
- Prometheus metrics exporter + Expo push alerts
- Next.js dashboard (`lp-portal`) & Expo mobile app (`apps/dynasty-mobile`)
- Pre-commit (Black, Ruff) & GitHub Actions CI (tests, lint, nightly retrain)
- Docker Compose for local dev & monitoring stack

### Deployment

1. Install deps
   ```bash
   poetry install                    # Python core
   npm --prefix lp-portal i          # Web portal
   npm --prefix apps/dynasty-mobile i # Mobile
   ```

2. Copy env files & fill secrets (`POLYGON_KEY`, `TRADIER_KEY`, `SUPABASE_*` …).

3. Local all-in-one stack
   ```bash
   docker compose up            # engine + Prom + Grafana + portal
   # http://localhost:8000/metrics , http://localhost:3000 , http://localhost:3001
   ```

4. Manual run (no Docker)
   ```bash
   python metrics_exporter.py &
   python multi_asset_manager.py --symbol AAPL
   npm --prefix lp-portal run dev
   expo start -p 8081
   ```

5. Production – push to `main`; CI pipeline runs tests, lint, retrains model, and can deploy to Cloud Run.

### Secrets
- IBKR API credentials, OpenAI API key fetched securely from GCP Secret Manager

### Monitoring
- Prometheus scrape endpoint `:8000/metrics`

Key metrics:
* `dynasty_drawdown_pct`
* `dynasty_action_total{symbol,action}`
* `dynasty_model_version{symbol}`
* `dynasty_rl_infer_ms{symbol}`

Visualised in Grafana dashboard (`grafana/dynasty.json`). Push alerts delivered via Expo.

### Prometheus
Run `python metrics_exporter.py` or use `docker compose` which already includes Prometheus.

### Back‑test
```bash
python backtest_harness.py MSTR 2022-01-01 2024-01-01 data/MSTR.csv
```

### Tests
```bash
pytest -q
```

### Author
- Esh, Founder of Entropie LLC