# Gluco Watch Dashboard

A React TypeScript dashboard application for displaying glucose monitoring data from Firebase Realtime Database.

## Features

- Google Authentication for secure access
- Admin verification from Firestore
- Real-time glucose data display from Firebase
- User ID selector to view different users' data
- Color-coded glucose status (Low/Normal/High)
- Responsive design with modern UI

## Setup

1. Install dependencies:
```bash
npm install
```

2. Start the development server:
```bash
npm run dev
```

3. Build for production:
```bash
npm run build
```

## Configuration

Firebase configuration is set up in `src/firebase/config.ts`. The app connects to Firebase Realtime Database and reads data from the path `users/{userId}/latest`.

## Authentication & Admin Setup

The app uses Google Authentication and checks admin permissions from Firestore:

1. **User Mapping** (required): Create a document in Firestore at `/userMappings/{firebaseAuthUid}` with:
   ```json
   {
     "glucoseUserId": "78347"
   }
   ```
   Where `{firebaseAuthUid}` is the Firebase Authentication UID and `glucoseUserId` is the glucose monitoring service user ID.

2. **Admin Permissions**: Create a document in Firestore at `/admins/{glucoseUserId}` with:
   ```json
   {
     "admins": ["admin1@example.com", "admin2@example.com"]
   }
   ```
   Where `{glucoseUserId}` is the glucose monitoring service user ID (e.g., "78347") and `admins` is an array of allowed email addresses.

## Usage

1. Sign in with Google
2. If your email is in the admin list for your mapped glucose user ID, you'll see the dashboard
3. Enter a user ID in the input field (default: 78347)
4. The dashboard will automatically fetch and display the latest glucose data
5. Data updates in real-time as it changes in Firebase

## Data Structure

The app expects data in the following format:
```json
{
  "main": {
    "glucose": 11.2,
    "timestamp": 1766435342.0,
    "time": "2025-12-22T21:29:02"
  },
  "fetched_at": "2025-12-22T21:29:08.767105",
  "fetched_at_unix": 1766435348,
  "fetched_at_unix_ms": 1766435348767
}
```
