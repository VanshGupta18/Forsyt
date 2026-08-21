"""Download the Caldara/Iacoviello "AI-GPR" benchmark CSVs into nifty-50/data/.

WHAT: three public, ready-made geopolitical-risk-index files (daily,
monthly, and per-country monthly) published at matteoiacoviello.com.

WHY: this package (`forsyt_gpr`) is built and tested against that
well-established, decades-long benchmark index rather than Forsyt's own
India index, simply because it already has enough history to validate
models against (see `forsyt_gpr/README.md` and `forsyt_gpr/data.py`'s
"pluggable contract" note for how the real India index eventually plugs in
instead). Re-run this script any time you need a fresh copy of these three
files -- it just overwrites whatever is already in `data/`.
"""
import urllib.request
import os

files_to_download = {
    "ai_gpr_data_daily.csv": "https://www.matteoiacoviello.com/ai_gpr_files/ai_gpr_data_daily.csv",
    "ai_gpr_data_monthly.csv": "https://www.matteoiacoviello.com/ai_gpr_files/ai_gpr_data_monthly.csv",
    "ai_gpr_country_monthly.csv": "https://www.matteoiacoviello.com/ai_gpr_files/ai_gpr_country_monthly.csv",
}

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

os.makedirs("data", exist_ok=True)

for filename, url in files_to_download.items():
    path = os.path.join("data", filename)
    print(f"Downloading {filename} from {url}...")
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            with open(path, 'wb') as out_file:
                out_file.write(response.read())
        print(f"Successfully downloaded {filename}. Size: {os.path.getsize(path)} bytes")
    except Exception as e:
        print(f"Failed to download {filename}: {e}")
