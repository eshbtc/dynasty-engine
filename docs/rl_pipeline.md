# Dynasty RL Pipeline

This document walks through the end-to-end reinforcement-learning workflow used by **Dynasty Engine**.

---

## 1. Data path

| stage | script | artifact |
|-------|--------|----------|
| raw OHLC | `scripts/data_fetch_polygon.py` | `data/<sym>_raw.parquet` |
| features | `scripts/feature_engineering.py` | `data/<sym>_features.parquet` |

`feature_builder.build_obs()` guarantees that the live-stream feature vector is identical to training.

## 2. Training

```
python train_rl.py \
  --csv data/mstr_features.parquet \
  --symbol MSTR --timesteps 300000 \
  --commission 1 --slippage 5
```

For hyper-parameter search:

```
python rl/hyperparam_search.py --csv data/mstr_features.parquet --symbol MSTR --trials 50
```

Both commands save to a timestamped run directory:

```
models/<sym>/<YYYYmmdd_HHMMSS>_{manual|optuna}/
  ├─ model.zip         (SB3 checkpoint)
  ├─ norm.pkl          (VecNormalize)
  └─ meta.json         (params)
```

## 3. CI / Nightly retrain

GitHub Action `.github/workflows/rl_train.yml` retrains every night, commits the new model back to the repo and Prometheus metric `dynasty_model_version` is updated live.

## 4. Live decision loop

```
multi_asset_manager ➜ build_obs ➜ rl_policy.decide
                        ▲                │
                        │                ▼
            metrics_exporter.update_action / update_equity
```

Risk-manager veto (`drawdown > limit` or manual halt) sits between decision & execution.

## 5. Monitoring

`metrics_exporter.py` starts an HTTP server on port 8000 exposing:

| metric | description |
|--------|-------------|
| `dynasty_action_total{symbol,action}` | cumulative RL actions |
| `dynasty_drawdown_pct` | current drawdown vs max NAV |
| `dynasty_sharpe` | rolling Sharpe (50 steps) |
| `dynasty_model_version{symbol}` | UNIX timestamp of active model |

Import these into Grafana to create dashboards & alerts.

## 6. Episode logs & reflection

Every RL step is appended to `data/trades_episodes.csv` by `episode_logger.log_step`.

Run `python reflect.py` nightly to produce `data/daily_summary.parquet` for analytics.

---

For any questions ping `@ai-engineering` in Slack.
