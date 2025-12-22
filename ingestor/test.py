"""
EasyView API client for fetching glucose monitor status and saving to Firestore.
"""

import os
import base64
import json
import time
import math
import urllib.parse
from typing import Dict, Any, Optional, Union

import requests
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Firebase initialization
FIREBASE_CREDENTIALS_PATH = "gluco-watch-firebase-adminsdk-fbsvc-cd567c4e05.json"

if not firebase_admin._apps:
    cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
    firebase_admin.initialize_app(cred)

db = firestore.client()


class EasyViewClient:
    """Client for interacting with EasyView Medtrum API."""
    
    BASE_URL = "https://easyview.medtrum.eu"
    LOGIN_URL = f"{BASE_URL}/v3/api/v2.0/login"
    STATUS_URL_TEMPLATE = f"{BASE_URL}/api/v2.1/monitor/{{monitor_uid}}/status"
    
    def __init__(self, username: str, password: str, user_type: str = "P"):
        """
        Initialize EasyView client.
        
        Args:
            username: Email address for login
            password: Password for login
            user_type: User type (default: "P")
        """
        self.username = username
        self.password = password
        self.user_type = user_type
        self.session = requests.Session()
        self._apptag = "v=3.0.2(15);n=eyvw"
        
    def _get_login_headers(self) -> Dict[str, str]:
        """Get headers for login request."""
        return {
            "accept": "application/json",
            "content-type": "application/json",
            "apptag": self._apptag,
            "referer": f"{self.BASE_URL}/v3/",
        }
    
    def _get_status_headers(self) -> Dict[str, str]:
        """Get headers for status request."""
        return {
            "accept": "application/json, text/plain, */*",
            "accept-language": "cs-CZ,cs;q=0.9",
            "apptag": self._apptag,
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "referer": f"{self.BASE_URL}/v3/",
        }
    
    def login(self) -> requests.Response:
        """
        Login to EasyView API.
        
        Returns:
            Response object from login request
            
        Raises:
            requests.HTTPError: If login fails
        """
        payload = {
            "user_name": self.username,
            "user_type": self.user_type,
            "password": self.password,
        }
        
        response = self.session.post(
            self.LOGIN_URL,
            json=payload,
            headers=self._get_login_headers()
        )
        response.raise_for_status()
        
        print(f"Login successful. Status: {response.status_code}")
        return response
    
    def get_status(
        self,
        monitor_uid: str,
        tz_offset_hours: int = 1,
        window_hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get monitor status from EasyView API.
        
        Args:
            monitor_uid: Monitor UID
            tz_offset_hours: Timezone offset in hours (default: 1 for CET)
            window_hours: Hours to look back (default: 24)
            
        Returns:
            JSON response as dictionary
            
        Raises:
            requests.HTTPError: If request fails
        """
        param = self._build_easyview_param(tz_offset_hours, window_hours)
        status_url = f"{self.STATUS_URL_TEMPLATE.format(monitor_uid=monitor_uid)}?param={param}"
        
        response = self.session.get(
            status_url,
            headers=self._get_status_headers()
        )
        response.raise_for_status()
        
        return response.json()
    
    @staticmethod
    def _build_easyview_param(tz_offset_hours: int = 1, window_hours: int = 24) -> str:
        """
        Build EasyView API parameter string.
        
        Args:
            tz_offset_hours: Timezone offset (CET = 1)
            window_hours: How many hours back to fetch
            
        Returns:
            URL-encoded base64 parameter string
        """
        # Current time in UTC seconds
        now_utc = int(time.time())
        
        # Adjust for timezone
        now_tz = now_utc + tz_offset_hours * 3600
        
        # Round down to nearest whole hour
        now_tz = (now_tz // 3600) * 3600
        
        # Window start
        start_tz = now_tz - window_hours * 3600
        
        # Round down to nearest whole hour
        start_tz = (start_tz // 3600) * 3600
        
        payload = {
            "ts": [start_tz, now_tz],
            "tz": tz_offset_hours
        }
        
        # Compact JSON (no spaces!)
        json_str = json.dumps(payload, separators=(",", ":"))
        
        # Base64 encode (standard, with == padding)
        b64 = base64.b64encode(json_str.encode()).decode()
        
        # URL encode (so == → %3D%3D)
        return urllib.parse.quote(b64, safe="")


def prepare_for_firestore(data: Any, max_depth: int = 100, current_depth: int = 0) -> Any:
    """
    Recursively prepare data for Firestore by converting unsupported types.
    
    Firestore doesn't support:
    - NaN (float('nan'))
    - Infinity (float('inf') or float('-inf'))
    - Some complex nested structures
    - Circular references
    
    Args:
        data: Data to prepare (can be dict, list, or primitive)
        max_depth: Maximum recursion depth to prevent stack overflow
        current_depth: Current recursion depth
        
    Returns:
        Firestore-compatible data
    """
    if current_depth > max_depth:
        return None  # Prevent infinite recursion
    
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            # Ensure keys are strings (Firestore requirement)
            key_str = str(key) if not isinstance(key, str) else key
            result[key_str] = prepare_for_firestore(value, max_depth, current_depth + 1)
        return result
    elif isinstance(data, (list, tuple)):
        # Convert tuples to lists (Firestore prefers lists)
        return [prepare_for_firestore(item, max_depth, current_depth + 1) for item in data]
    elif isinstance(data, float):
        # Handle NaN and Infinity
        if math.isnan(data):
            return None  # Convert NaN to None
        elif math.isinf(data):
            return None  # Convert Infinity to None
        return data
    elif isinstance(data, (int, str, bool)) or data is None:
        return data
    elif isinstance(data, (bytes, bytearray)):
        # Convert bytes to base64 string
        return base64.b64encode(data).decode('utf-8')
    else:
        # Convert any other type to string as fallback
        try:
            return str(data)
        except Exception:
            return None


def save_to_firestore(uid: str, data: Dict[str, Any]) -> None:
    """
    Save monitor status data to Firestore.
    
    Args:
        uid: User UID (will be converted to string if needed)
        data: Data to save (will be cleaned for Firestore compatibility)
    """
    # Ensure uid is a string (Firestore document IDs must be strings)
    uid_str = str(uid)
    
    # Prepare data for Firestore (handle NaN, Infinity, etc.)
    cleaned_data = prepare_for_firestore(data)
    
    doc_ref = db.collection("users").document(uid_str).collection("state").document("latest")
    doc_ref.set(cleaned_data)
    print(f"Data saved to Firestore: users/{uid_str}/state/latest")


def main():
    """Main execution function."""
    # Load credentials from environment
    username = os.getenv("EASYVIEW_USERNAME")
    password = os.getenv("EASYVIEW_PASSWORD")
    user_type = os.getenv("EASYVIEW_USER_TYPE", "P")
    monitor_uid = os.getenv("EASYVIEW_MONITOR_UID")
    tz_offset = int(os.getenv("TZ_OFFSET_HOURS", "1"))
    window_hours = int(os.getenv("WINDOW_HOURS", "24"))
    
    if not username or not password:
        raise ValueError(
            "EASYVIEW_USERNAME and EASYVIEW_PASSWORD must be set in .env file"
        )
    
    # Initialize client
    client = EasyViewClient(username, password, user_type)
    
    # Login
    login_response = client.login()
    
    # Extract monitor UID from login response if not provided in env
    if not monitor_uid:
        try:
            login_data = login_response.json()
            # Try to extract UID from response (adjust based on actual API response structure)
            if "monitor_uid" in login_data:
                monitor_uid = login_data["monitor_uid"]
            elif "uid" in login_data:
                monitor_uid = login_data["uid"]
            else:
                # If not in response, try to get from cookies or other fields
                # This is a fallback - you may need to adjust based on actual API response
                raise ValueError(
                    "EASYVIEW_MONITOR_UID not set and could not be extracted from login response. "
                    "Please set it in .env file."
                )
        except (json.JSONDecodeError, KeyError) as e:
            raise ValueError(
                f"Could not extract monitor UID from login response: {e}. "
                "Please set EASYVIEW_MONITOR_UID in .env file."
            )
    
    print(f"Using monitor UID: {monitor_uid}")
    
    # Get status
    status_data = client.get_status(monitor_uid, tz_offset, window_hours)
    
    print(f"Status retrieved successfully")
    print(f"Response data keys: {list(status_data.keys()) if isinstance(status_data, dict) else 'N/A'}")
    
    # Prepare data for Firestore - add timestamp and extract 'data' field if present
    firestore_data = {
        "timestamp": firestore.SERVER_TIMESTAMP,
        "fetched_at": int(time.time()),
    }
    
    # If response has 'data' field, store it as JSON string to avoid Firestore nesting limits
    # Firestore has a limit of 20 levels of nesting, and the API data can be very deeply nested
    if isinstance(status_data, dict) and "data" in status_data:
        # Store the complex nested 'data' field as a JSON string
        # This avoids Firestore's nesting depth limitations
        firestore_data["data_json"] = json.dumps(status_data["data"], default=str)
        if "error" in status_data:
            firestore_data["error"] = status_data["error"]
    else:
        # If no 'data' field, store the whole response as JSON string
        firestore_data["response_json"] = json.dumps(status_data, default=str)
    
    # Save to Firestore
    # Use monitor_uid as the user UID, or extract from status_data if different
    save_to_firestore(monitor_uid, firestore_data)
    
    print("Process completed successfully")


if __name__ == "__main__":
    main()
