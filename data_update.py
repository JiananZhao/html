import pandas as pd
import requests
import os
from datetime import datetime
from io import StringIO # 用于将下载的文本内容包装成文件对象

# --- Configuration ---
TREASURY_DAILY_CSV_URL = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/2025/all?type=daily_treasury_yield_curve&field_tdr_date_value=2025&page&_format=csv"

OUTPUT_FILENAME = 'daily-treasury-rates.csv'

def download_and_update_data():
    """Downloads the latest CSV, compares it to the existing file, and saves if newer."""
    print(f"[{datetime.now()}] Starting data download and update...")

    temp_filename = "temp_download.csv" # 临时文件用于保存下载内容
    
    try:
        # --- 1. Download New Data ---
        print(f"Downloading data from: {TREASURY_DAILY_CSV_URL}")
        # 使用 requests.get 发送请求，并使用 stream=True 以便处理大文件
        # 允许重定向，因为下载链接可能会有重定向
        response = requests.get(TREASURY_DAILY_CSV_URL, stream=True, allow_redirects=True)
        response.raise_for_status()  # 检查是否为 HTTP 错误 (4xx 或 5xx)

        # 获取文件名 (可选，如果文件名固定则不需要)
        # filename = response.headers.get('content-disposition')
        # if filename and "filename=" in filename:
        #     filename = filename.split("filename=")[1].strip('"')
        # else:
        #     filename = "downloaded_file.csv"

        # 以二进制写入模式打开临时文件，并将内容分块写入
        with open(temp_filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk: # 过滤掉保持连接的空 chunk
                    f.write(chunk)
        print(f"临时文件成功保存到: {temp_filename}")
        
        # 读取下载的临时 CSV 文件到 DataFrame
        new_df = pd.read_csv(temp_filename)
        new_df['Date'] = pd.to_datetime(new_df['Date'])

        # --- 2. Comparison Logic ---
        should_update = False
        
        if os.path.exists(OUTPUT_FILENAME):
            existing_df = pd.read_csv(OUTPUT_FILENAME)
            existing_df['Date'] = pd.to_datetime(existing_df['Date'])
            
            latest_new_date = new_df['Date'].max()
            latest_existing_date = existing_df['Date'].max()
            
            if latest_new_date > latest_existing_date:
                should_update = True
                print(f"Newer data found! Latest new date: {latest_new_date.strftime('%Y-%m-%d')}")
            else:
                print(f"No newer data available. Latest date: {latest_existing_date.strftime('%Y-%m-%d')}")
        else:
            should_update = True
            print("Existing data file not found, saving the newly downloaded data.")

        # --- 3. Final Save and Cleanup ---
        if should_update:
            # Save the new data, overwriting the old one
            new_df.to_csv(OUTPUT_FILENAME, index=False)
            print(f"[{datetime.now()}] Successfully saved new data to {OUTPUT_FILENAME}")
            # Clean up the temporary file
            os.remove(temp_filename)
            return True # Indicates an update occurred
        else:
            os.remove(temp_filename)
            return False # Indicates no update occurred

    except requests.exceptions.RequestException as e:
        print(f"[{datetime.now()}] Error during download: {e}")
        return False
    except pd.errors.EmptyDataError:
        print(f"[{datetime.now()}] Downloaded file is empty or malformed.")
        return False
    except Exception as e:
        print(f"[{datetime.now()}] An unexpected error occurred: {e}")
        return False
    finally:
        # 确保临时文件在任何情况下都被删除
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

if __name__ == "__main__":
    if download_and_update_data():
        print("::set-output name=commit_needed::true")
    else:
        print("::set-output name=commit_needed::false")