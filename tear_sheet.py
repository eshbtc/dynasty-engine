"""Generate monthly tear‑sheet PDF, auto‑upload to Supabase Storage
   Usage:  python tear_sheet.py
   Requires env: OPENAI_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY
"""
import jinja2, pdfkit, sqlite3, datetime, os, openai, pandas as pd
from supabase import create_client, Client

# --- Configuration & Clients ---
openai_api_key = os.getenv('OPENAI_API_KEY')
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_SERVICE_KEY')

if not all([openai_api_key, supabase_url, supabase_key]):
    raise ValueError("Missing required environment variables: OPENAI_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY")

openai.api_key = openai_api_key
supa: Client = create_client(supabase_url, supabase_key)
db_path = 'trade_tracker.db'

# --- Functions ---
def gpt_commentary(pnl, sharpe):
    """Generates manager commentary using OpenAI API."""
    prompt = (
        f"Generate a concise (max 70 words) manager commentary for a quantitative trading strategy's monthly performance. "
        f"This month's cumulative PnL = {pnl:,.0f} USD. The 90-day rolling Sharpe ratio is {sharpe:.2f}. "
        f"Comment on performance drivers (if discernible from PnL/Sharpe), risk management discipline, and outlook/next steps. "
        f"Maintain a professional and objective tone."
    )
    try:
        response = openai.chat.completions.create(
             model='gpt-4o', # Ensure you have access or use appropriate model
             messages=[{"role":"user", "content": prompt}],
             max_tokens=100, # Limit response length
             temperature=0.5 # Adjust creativity
        )
        commentary = response.choices[0].message.content.strip()
        print("Generated commentary:", commentary)
        return commentary
    except Exception as e:
        print(f"Error generating commentary: {e}")
        return "Performance commentary generation failed."

def build_context():
    """Builds the data context for the Jinja template from the database."""
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}")
        # Return default/empty context to avoid crashing
        return {
            'month': datetime.date.today().strftime('%B %Y'),
            'cumulative_pnl': 0,
            'trade_count': 0,
            'winners': [],
            'losers': [],
            'commentary': 'Trade database not found.'
        }

    conn = sqlite3.connect(db_path)
    try:
        # IMPORTANT: PnL & Sharpe calculation assumes 'trades' table structure
        # and might need adjustment based on how trades are logged (e.g., entry/exit pairs vs single PnL entries)
        # This example uses a simple diff on 'price' which is likely INACCURATE for real trading.
        # Replace with accurate PnL calculation based on your schema!
        df = pd.read_sql('SELECT ticker, price, fee, timestamp FROM trades ORDER BY timestamp ASC', conn)

        if df.empty:
             pnl, sharpe, trade_count, winners_df, losers_df = 0, 0, 0, pd.DataFrame(), pd.DataFrame()
        else:
            # --- Placeholder PnL Calculation (NEEDS REVIEW/REPLACEMENT) ---
            # This calculates PnL based on price changes *within* the dataframe period.
            # It does NOT accurately reflect closed trade PnL unless 'price' stores final value.
            df['pnl_diff'] = df.groupby('ticker')['price'].diff().fillna(0)
            # Adjust for fees (assuming 'fee' is per trade)
            df['net_pnl'] = df['pnl_diff'] - df['fee'].fillna(0)
            # --------------------------------------------------------------

            pnl = df['net_pnl'].sum()
            trade_count = df.shape[0]

            # Calculate rolling Sharpe (adjust window and annualization factor as needed)
            # This uses the placeholder 'net_pnl'. Needs accurate daily/periodic PnL.
            rolling_pnl = df['net_pnl'].rolling(window=min(90, len(df)), min_periods=1).sum() # Example: 90-trade window
            # Basic Sharpe (highly depends on PnL calculation frequency and accuracy)
            if rolling_pnl.std() > 0:
                 sharpe = (rolling_pnl.mean() / rolling_pnl.std()) * (252**0.5) # Assumes daily-ish PnL
            else:
                 sharpe = 0

            # Group by ticker for winners/losers (using placeholder PnL)
            ticker_pnl = df.groupby('ticker')['net_pnl'].sum()
            winners_df = ticker_pnl.nlargest(3).reset_index().rename(columns={'net_pnl': 'pnl'})
            losers_df = ticker_pnl.nsmallest(3).reset_index().rename(columns={'net_pnl': 'pnl'})

    except pd.io.sql.DatabaseError as e:
         print(f"Database Error: {e}. Check 'trades' table exists and has expected columns.")
         return { # Return default context on DB error
            'month': datetime.date.today().strftime('%B %Y'), 'cumulative_pnl': 0,
            'trade_count': 0, 'winners': [], 'losers': [],
            'commentary': 'Error accessing trade data.'
        }
    finally:
        conn.close()

    ctx = {
        'month': datetime.date.today().strftime('%B %Y'),
        'cumulative_pnl': pnl,
        'trade_count': trade_count,
        'winners': winners_df.to_dict('records'),
        'losers': losers_df.to_dict('records'),
        'commentary': gpt_commentary(pnl, sharpe) # Generate commentary
    }
    return ctx

# --- Main Execution ---
if __name__ == "__main__":
    print("Generating monthly tear sheet...")
    context = build_context()

    # Render HTML from template
    template_dir = 'templates'
    template_file = 'tear_sheet.html'
    if not os.path.exists(os.path.join(template_dir, template_file)):
        raise FileNotFoundError(f"Template file not found: {os.path.join(template_dir, template_file)}")

    env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir),
                             autoescape=jinja2.select_autoescape(['html', 'xml']))
    html_content = env.get_template(template_file).render(**context)

    # Generate PDF
    output_filename = f"dynasty_report_{datetime.date.today().strftime('%Y_%m')}.pdf"
    try:
        # Ensure wkhtmltopdf is installed and in PATH, or specify path in config
        # pdfkit_config = pdfkit.configuration(wkhtmltopdf='/path/to/wkhtmltopdf') # If needed
        pdfkit.from_string(html_content, output_filename) # config=pdfkit_config
        print(f"PDF saved locally: {output_filename}")
    except Exception as e:
        print(f"Error generating PDF: {e}. Ensure wkhtmltopdf is installed and accessible.")
        exit(1)

    # Auto-upload to Supabase
    bucket_name = 'reports' # Ensure this bucket exists in your Supabase project
    try:
        with open(output_filename, 'rb') as f:
            # Supabase storage uses file path as the key in the bucket
            response = supa.storage.from_(bucket_name).upload(
                path=output_filename,
                file=f,
                file_options={"upsert": "true"} # Overwrite if exists
            )
            print(f"Successfully uploaded '{output_filename}' to Supabase bucket '{bucket_name}'.")
            # print(f"Supabase response: {response}")
    except Exception as e:
        print(f"Error uploading {output_filename} to Supabase bucket '{bucket_name}': {e}")

    print("Tear sheet generation complete.")
