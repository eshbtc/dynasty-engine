# Dynasty Engine Phase 3 - Trade Commentary Module (trade_commentary.py)

import openai
import yaml
import os

# Load Configs
def load_config():
    with open('config.yaml', 'r') as f:
        return yaml.safe_load(f)

config = load_config()

# Setup OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')

# Generate Trade Commentary
def generate_trade_commentary(ticker, action, quantity, price, iv_rank, btc_correlation):
    prompt = f"""
    Write a professional trade commentary for a trade:

    Ticker: {ticker}
    Action: {action}
    Quantity: {quantity}
    Execution Price: ${price:.2f}
    IV Rank: {iv_rank}%
    Bitcoin Correlation: {btc_correlation}

    Keep it clear, under 50 words.
    """

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )

    commentary = response['choices'][0]['message']['content'].strip()
    return commentary

# === dynasty_engine.py update ===
# After executing any trade (Buy/Sell), call generate_trade_commentary()

# Example integration inside dynasty_engine_cycle():
'''
from trade_commentary import generate_trade_commentary

# After placing order:
commentary = generate_trade_commentary(
    ticker='MSTR',
    action='BUY',
    quantity=qty,
    price=price,
    iv_rank=25,  # Example dummy value
    btc_correlation=0.8
)

cursor.execute("INSERT INTO trades (ticker, action, quantity, price, date, outcome, commentary) VALUES (?, ?, ?, ?, ?, ?, ?)",
               ('MSTR', 'BUY', qty, price, datetime.datetime.now().isoformat(), 'OPEN', commentary))
conn.commit()
'''

# === Database Update ===
# Add a 'commentary' column to your trades table:
'''
ALTER TABLE trades ADD COLUMN commentary TEXT;
'''

# === dashboard.py Update ===
# In the dashboard table, add commentary field to the displayed trades:

'''
st.dataframe(trades[['ticker', 'action', 'quantity', 'price', 'date', 'outcome', 'commentary']])
'''

# === Summary ===
# - After each trade, GPT-4 generates a 1-liner explanation.
# - Commentary stored in SQLite alongside trade data.
# - Displayed live in dashboard.
# - Included in Monthly Reports for investors.

# === Additional Notes ===
# OpenAI API call is lightweight and optimized.
# Cost per commentary generation is minimal (<$0.01 per trade).

