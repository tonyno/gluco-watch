# EasyView API Ingestor

This script fetches glucose monitor status from EasyView Medtrum API and saves it to Firebase Firestore.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file in the `ingestor` directory with your credentials:
```bash
# EasyView API Credentials
EASYVIEW_USERNAME=your_email@example.com
EASYVIEW_PASSWORD=your_password
EASYVIEW_USER_TYPE=P

# Monitor UID (optional, can be extracted from login response)
EASYVIEW_MONITOR_UID=

# Timezone settings
TZ_OFFSET_HOURS=1
WINDOW_HOURS=24
```

3. Make sure the Firebase service account key file is present:
   - `gluco-watch-firebase-adminsdk-fbsvc-cd567c4e05.json`

## Usage

Run the script:
```bash
python test.py
```

The script will:
1. Login to EasyView API using credentials from `.env`
2. Fetch monitor status data
3. Save the data to Firestore at `users/{uid}/state/latest`

## Environment Variables

- `EASYVIEW_USERNAME`: Your EasyView account email
- `EASYVIEW_PASSWORD`: Your EasyView account password
- `EASYVIEW_USER_TYPE`: User type (default: "P")
- `EASYVIEW_MONITOR_UID`: Monitor UID (optional, will try to extract from login response)
- `TZ_OFFSET_HOURS`: Timezone offset in hours (default: 1 for CET)
- `WINDOW_HOURS`: Hours to look back when fetching data (default: 24)


# Loading from endpoint

https://firestore.googleapis.com/v1/projects/gluco-watch/databases/(default)/documents/users/78347/