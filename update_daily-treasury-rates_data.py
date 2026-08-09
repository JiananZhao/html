import os
import datetime
import requests
import pandas as pd
from io import StringIO
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

OUTPUT_FILENAME = 'daily-treasury-rates.csv'

def get_retry_session():
    """Configures a resilient requests session with exponential backoff retries."""
    session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        raise_on_status=False
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

def fetch_treasury_csv(current_year):
    """Attempts to fetch daily treasury rates from primary or fallback endpoints."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/csv,application/csv,text/html,application/xhtml+xml,application/xml'
    }

    primary_url = f"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{current_year}/all?field_tdr_date_value={current_year}&type=daily_treasury_yield_curve&page&_format=csv"
    fallback_url = f"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/all/{current_year}?type=daily_treasury_yield_curve&field_tdr_date_value_month={current_year}&page&_format=csv"

    urls = [primary_url, fallback_url]
    session = get_retry_session()

    for url in urls:
        try:
            print(f"Fetching Treasury data from: {url}")
            response = session.get(url, headers=headers, timeout=20)
            if response.status_code == 200 and len(response.text.strip()) > 100:
                return response.text
            else:
                print(f"Received status code {response.status_code} from {url}")
        except Exception as e:
            print(f"Error requesting Treasury data: {e}")

    return None

def download_and_update_data():
    current_year = datetime.datetime.now().year
    csv_text = fetch_treasury_csv(current_year)

    if not csv_text:
        print("Failed to download Treasury data from all endpoints.")
        set_github_output("commit_needed", "false")
        return

    try:
        df_new = pd.read_csv(StringIO(csv_text))
    except Exception as e:
        print(f"Failed to parse downloaded CSV data: {e}")
        set_github_output("commit_needed", "false")
        return

    if df_new.empty or 'Date' not in df_new.columns:
        print("Downloaded Treasury data is empty or missing 'Date' column.")
        set_github_output("commit_needed", "false")
        return

    df_new['Date'] = pd.to_datetime(df_new['Date'])
    df_new = df_new.sort_values('Date').reset_index(drop=True)

    latest_fetched_date = df_new['Date'].max()
    latest_fetched_date_str = latest_fetched_date.strftime('%Y-%m-%d')
    print(f"Latest fetched Treasury date: {latest_fetched_date_str}")

    commit_needed = False

    if os.path.exists(OUTPUT_FILENAME) and os.path.getsize(OUTPUT_FILENAME) > 10:
        try:
            df_existing = pd.read_csv(OUTPUT_FILENAME)
            if 'Date' in df_existing.columns and len(df_existing) > 0:
                df_existing['Date'] = pd.to_datetime(df_existing['Date'])
                latest_existing_date = df_existing['Date'].max()

                if latest_fetched_date > latest_existing_date:
                    print(f"New Treasury data available ({latest_fetched_date_str} > {latest_existing_date.strftime('%Y-%m-%d')}). Updating...")
                    df_combined = pd.concat([df_existing, df_new]).drop_duplicates(subset=['Date']).sort_values('Date')
                    df_combined['Date'] = df_combined['Date'].dt.strftime('%Y-%m-%d')
                    df_combined.to_csv(OUTPUT_FILENAME, index=False)
                    commit_needed = True
                else:
                    print(f"Treasury data is up to date (Latest: {latest_existing_date.strftime('%Y-%m-%d')}). No update needed.")
            else:
                df_new['Date'] = df_new['Date'].dt.strftime('%Y-%m-%d')
                df_new.to_csv(OUTPUT_FILENAME, index=False)
                commit_needed = True
        except Exception as e:
            print(f"Error processing existing Treasury CSV: {e}. Rewriting...")
            df_new['Date'] = df_new['Date'].dt.strftime('%Y-%m-%d')
            df_new.to_csv(OUTPUT_FILENAME, index=False)
            commit_needed = True
    else:
        df_new['Date'] = df_new['Date'].dt.strftime('%Y-%m-%d')
        df_new.to_csv(OUTPUT_FILENAME, index=False)
        commit_needed = True

    if commit_needed:
        set_github_output("commit_needed", "true")
        set_github_env("LATEST_DATE", latest_fetched_date_str)
    else:
        set_github_output("commit_needed", "false")

def set_github_output(name, value):
    github_output = os.environ.get('GITHUB_OUTPUT')
    if github_output:
        with open(github_output, 'a') as f:
            f.write(f"{name}={value}\n")

def set_github_env(name, value):
    github_env = os.environ.get('GITHUB_ENV')
    if github_env:
        with open(github_env, 'a') as f:
            f.write(f"{name}={value}\n")

if __name__ == "__main__":
    download_and_update_data()
