# EasyView API Ingestor

This script fetches glucose monitor status from EasyView Medtrum API and saves it to both Firebase Firestore and Firebase Realtime Database.

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

# Firebase Realtime Database URL (optional, defaults to gluco-watch-default-rtdb)
FIREBASE_DATABASE_URL=https://gluco-watch-default-rtdb.firebaseio.com/
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
3. Save the data to Firestore at `users/{uid}`
4. Save the data to Realtime Database at `users/{uid}/latest`

## Environment Variables

- `EASYVIEW_USERNAME`: Your EasyView account email
- `EASYVIEW_PASSWORD`: Your EasyView account password
- `EASYVIEW_USER_TYPE`: User type (default: "P")
- `EASYVIEW_MONITOR_UID`: Monitor UID (optional, will try to extract from login response)
- `TZ_OFFSET_HOURS`: Timezone offset in hours (default: 1 for CET)
- `WINDOW_HOURS`: Hours to look back when fetching data (default: 24)
- `FIREBASE_DATABASE_URL`: Firebase Realtime Database URL (default: `https://gluco-watch-default-rtdb.firebaseio.com/`)

## REST API Endpoints

### Firebase Firestore REST API

To retrieve data from Firestore, use the Firestore REST API:

**Get user document:**
```
GET https://firestore.googleapis.com/v1/projects/gluco-watch/databases/(default)/documents/users/{uid}
```

**Example:**
```
GET https://firestore.googleapis.com/v1/projects/gluco-watch/databases/(default)/documents/users/78347
```

**Authentication:** Requires OAuth 2.0 token or service account credentials.

### Firebase Realtime Database REST API

To retrieve data from Realtime Database, use the Realtime Database REST API:

**Get user data:**
```
GET https://{project-id}.firebaseio.com/users/{uid}/latest.json
```

**Example (with default project):**
```
GET https://gluco-watch-default-rtdb.firebaseio.com/users/78347/latest.json
```

**With authentication token:**
```
GET https://gluco-watch-default-rtdb.firebaseio.com/users/78347/latest.json?auth={YOUR_AUTH_TOKEN}
```

**Get all user data:**
```
GET https://gluco-watch-default-rtdb.firebaseio.com/users/{uid}.json
```

**Query parameters:**
- `auth={token}`: Authentication token (if database rules require it)
- `orderBy="{key}"`: Order results by a specific key
- `limitToFirst={n}`: Limit to first N results
- `limitToLast={n}`: Limit to last N results
- `startAt={value}`: Start at a specific value
- `endAt={value}`: End at a specific value

**Example with query:**
```
GET https://gluco-watch-default-rtdb.europe-west1.firebasedatabase.app/
users/78347/latest.json?orderBy="fetched_at_unix"&limitToLast=1
```

**Note:** Replace `{project-id}` with your actual Firebase project ID. The default URL format is `https://{project-id}-default-rtdb.firebaseio.com/` or you can find your exact URL in the Firebase Console under Realtime Database settings.