import pandas as pd
from pathlib import Path

from trading_env import TradingEnv


def test_env_runs(tmp_path):
    # minimal df
    df = pd.DataFrame({
        'date': ['2024-01-01','2024-01-02'],
        'price':[100,101],
        'iv_rank':[20,25],
    })
    env = TradingEnv(df)
    obs,_ = env.reset()
    obs2, reward, done, trunc, _ = env.step(1)
    assert env.observation_space.contains(obs)
    assert env.observation_space.contains(obs2)
    assert isinstance(reward, float)
    assert done is False or done is True
