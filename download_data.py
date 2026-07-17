import urllib.request
import os

files_to_download = {
    "ai_gpr_data_daily.csv": "https://www.matteoiacoviello.com/ai_gpr_files/ai_gpr_data_daily.csv",
    "ai_gpr_data_monthly.csv": "https://www.matteoiacoviello.com/ai_gpr_files/ai_gpr_data_monthly.csv",
    "ai_gpr_country_monthly.csv": "https://www.matteoiacoviello.com/ai_gpr_files/ai_gpr_country_monthly.csv",
}

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

for filename, url in files_to_download.items():
    print(f"Downloading {filename} from {url}...")
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            with open(filename, 'wb') as out_file:
                out_file.write(response.read())
        print(f"Successfully downloaded {filename}. Size: {os.path.getsize(filename)} bytes")
    except Exception as e:
        print(f"Failed to download {filename}: {e}")
