import streamlit as st
import sqlite3
import pandas as pd

# Connect to database
conn = sqlite3.connect('trade_tracker.db')
cursor = conn.cursor()

st.title("Dynasty Engine Dashboard")

# Load Trades
def load_trades():
    df = pd.read_sql_query("SELECT * FROM trades", conn)
    return df

# Show Trade History
st.header("Trade History")
trades = load_trades()
st.dataframe(trades)

# Show Basic Stats
if not trades.empty:
    total_trades = trades.shape[0]
    open_trades = trades[trades['outcome'] == 'OPEN'].shape[0]
    closed_trades = total_trades - open_trades
    st.metric("Total Trades", total_trades)
    st.metric("Open Trades", open_trades)
    st.metric("Closed Trades", closed_trades)

# Chat/Command Interface
st.header("Bot Command Center")
command = st.text_input("Send feedback or command to bot:")
if st.button("Submit Command"):
    with open('memory_store.json', 'a') as f:
        f.write(json.dumps({"timestamp": str(datetime.datetime.now()), "command": command}) + "\n")
    st.success("Command recorded. Bot will adapt next cycle.")