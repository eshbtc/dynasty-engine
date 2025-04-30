# Dynasty Engine Phase 3 - Monthly Reporter Module (monthly_reporter.py)

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import sqlite3
import pandas as pd
import datetime
import yaml
import os

# Load Configs
def load_config():
    with open('config.yaml', 'r') as f:
        return yaml.safe_load(f)

config = load_config()

# Database Connection
def fetch_trades():
    conn = sqlite3.connect('trade_tracker.db')
    df = pd.read_sql_query("SELECT * FROM trades", conn)
    conn.close()
    return df

# Generate Monthly Report
def generate_report():
    trades = fetch_trades()
    if trades.empty:
        return "No trades recorded this month."

    trades['date'] = pd.to_datetime(trades['date'])
    now = datetime.datetime.now()
    monthly_trades = trades[(trades['date'].dt.month == now.month) & (trades['date'].dt.year == now.year)]

    if monthly_trades.empty:
        return "No trades this month."

    pnl = monthly_trades['price'].diff().sum()
    total_trades = monthly_trades.shape[0]
    wins = monthly_trades[monthly_trades['price'].diff() > 0].shape[0]
    losses = monthly_trades[monthly_trades['price'].diff() <= 0].shape[0]
    win_rate = (wins / total_trades) * 100 if total_trades else 0

    report = f"""
    Dynasty Engine Monthly Report - {now.strftime('%B %Y')}

    Total Trades: {total_trades}
    Winning Trades: {wins}
    Losing Trades: {losses}
    Win Rate: {win_rate:.2f}%
    Cumulative PnL: ${pnl:.2f}
    """
    return report

# Email Report Function
def send_email(report_text):
    sender_email = config['sender_email']
    receiver_email = config['receiver_email']
    password = os.getenv('EMAIL_PASSWORD')

    message = MIMEMultipart("alternative")
    message["Subject"] = "Dynasty Engine Monthly Trading Report"
    message["From"] = sender_email
    message["To"] = receiver_email

    part1 = MIMEText(report_text, "plain")
    message.attach(part1)

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email, message.as_string())

if __name__ == "__main__":
    report = generate_report()
    send_email(report)


    # === .env Environment Variables ===
# You must set EMAIL_PASSWORD as an environment variable (don't hardcode!)
# e.g., export EMAIL_PASSWORD="yourpassword"

# === Cloud Scheduler Setup ===
# Schedule this script to run monthly using GCP Cloud Scheduler or any cron-like scheduler:
# Example cron timing for 1st of every month 9AM:
# 0 9 1 * *