import requests
import base64
import json
import time
import urllib.parse


def build_easyview_param(tz_offset_hours=1, window_hours=24):
    """
    tz_offset_hours: timezone offset (CET = 1)
    window_hours:    how many hours back
    """
    # Example of used URL: https://easyview.medtrum.eu/api/v2.1/monitor/78347/status?param=eyJ0cyI6WzE3NjYwOTg4MDAsMTc2NjE4NTIwMF0sInR6IjoxfQ%3D%3D

    # current time in UTC seconds
    now_utc = int(time.time())

    # adjust for timezone (+1 hour)
    now_tz = now_utc + tz_offset_hours * 3600

    # round down to nearest whole hour
    now_tz = (now_tz // 3600) * 3600

    # window start (24h back)
    start_tz = now_tz - window_hours * 3600

    # round down to nearest whole hour
    start_tz = (start_tz // 3600) * 3600

    payload = {
        "ts": [start_tz, now_tz],
        "tz": tz_offset_hours
    }

    # compact JSON (no spaces!)
    json_str = json.dumps(payload, separators=(",", ":"))
    print(json_str)

    # Base64 encode (standard, with == padding)
    b64 = base64.b64encode(json_str.encode()).decode()

    # URL encode (so == → %3D%3D)
    return urllib.parse.quote(b64, safe="")




session = requests.Session()

login_url = "https://easyview.medtrum.eu/v3/api/v2.0/login"

payload = {
    "user_name": "jaroslav.kmoch@gmail.com",
    "user_type": "P",
    "password": ""
}

headers = {
    "accept": "application/json",
    "content-type": "application/json",
    "apptag": "v=3.0.2(15);n=eyvw",
    "referer": "https://easyview.medtrum.eu/v3/",
}

response = session.post(login_url, json=payload, headers=headers)

print("Status:", response.status_code)
print("Cookies after login:", session.cookies)






status_url = f"https://easyview.medtrum.eu/api/v2.1/monitor/{uid}/status?param={build_easyview_param()}"


status_headers = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "cs-CZ,cs;q=0.9",
    "apptag": "v=3.0.2(15);n=eyvw",
    "cache-control": "no-cache",
    "pragma": "no-cache",
    "referer": "https://easyview.medtrum.eu/v3/",
}

response = session.get(status_url, headers=status_headers)
response.raise_for_status()

print("Status:", response.status_code)
print("Response JSON:", response.json())
