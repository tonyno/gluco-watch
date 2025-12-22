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
        self.user_id = None
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
        Login to EasyView API and extract user_id from response.
        
        Returns:
            Response object from login request
            
        Raises:
            requests.HTTPError: If login fails
            ValueError: If user_id cannot be extracted from login response
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
        
        # Extract and store user_id from login response
        self.user_id = self.extract_monitor_uid_from_login(response)
        print(f"Extracted user_id: {self.user_id}")

        return response
    
    def extract_monitor_uid_from_login(self, login_response: requests.Response) -> str:
        """
        Extract monitor UID from login response.
        
        Args:
            login_response: Response object from login request
            
        Returns:
            Monitor UID string
            
        Raises:
            ValueError: If monitor UID cannot be extracted from response
        """
        try:
            login_data = login_response.json()
            # Try to extract UID from response (adjust based on actual API response structure)
            if "monitor_uid" in login_data:
                return login_data["monitor_uid"]
            elif "uid" in login_data:
                return login_data["uid"]
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
    
    def get_status(
        self,
        tz_offset_hours: int = 1,
        window_hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get monitor status from EasyView API.
        
        Args:
            tz_offset_hours: Timezone offset in hours (default: 1 for CET)
            window_hours: Hours to look back (default: 24)
            
        Returns:
            JSON response as dictionary
            
        Raises:
            ValueError: If user_id is not set (login not called or failed)
            requests.HTTPError: If request fails
        """
        if not self.user_id:
            raise ValueError(
                "user_id not set. Please call login() first to extract user_id from login response."
            )
        
        param = self._build_easyview_param(tz_offset_hours, window_hours)
        status_url = f"{self.STATUS_URL_TEMPLATE.format(monitor_uid=self.user_id)}?param={param}"
        
        response = self.session.get(
            status_url,
            headers=self._get_status_headers()
        )
        response.raise_for_status()

        # Dump the raw response JSON to a file for debugging or inspection
        with open("response_dump.json", "w", encoding="utf-8") as f:
            f.write(response.text)
        
        return json.loads(response.text)
    
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
    - Arrays of arrays (convert to arrays of objects)
    
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
        # Check if this is an array of arrays (which Firestore doesn't handle well)
        # Only convert if we're confident ALL elements are arrays/tuples
        if len(data) > 0:
            # Check if first element is an array/tuple
            first_is_array = isinstance(data[0], (list, tuple))
            
            if first_is_array:
                # Sample more elements to confirm this is truly an array of arrays
                # Check multiple elements to avoid false positives
                sample_indices = [0]  # Always check first
                if len(data) > 1:
                    sample_indices.append(len(data) - 1)  # Check last
                if len(data) > 2:
                    sample_indices.append(len(data) // 2)  # Check middle
                
                is_array_of_arrays = all(
                    isinstance(data[i], (list, tuple)) for i in sample_indices
                )
                
                if is_array_of_arrays:
                    # Convert array of arrays to array of objects
                    # This prevents "invalid nested entity" errors in Firestore
                    converted = []
                    for item in data:
                        if isinstance(item, (list, tuple)):
                            # Convert to object with numeric string keys (Firestore-friendly)
                            item_dict = {}
                            for idx, val in enumerate(item):
                                item_dict[str(idx)] = prepare_for_firestore(val, max_depth, current_depth + 1)
                            converted.append(item_dict)
                        else:
                            # If we find a non-array item, just process it normally
                            converted.append(prepare_for_firestore(item, max_depth, current_depth + 1))
                    return converted
        
        # Regular array - convert tuples to lists, process each item
        return [prepare_for_firestore(item, max_depth, current_depth + 1) for item in data]
    elif isinstance(data, float):
        # Handle NaN and Infinity
        if math.isnan(data):
            return None  # Convert NaN to None
        elif math.isinf(data):
            return None  # Convert Infinity to None
        return data
    elif isinstance(data, str):
        # Strings pass through unchanged - Firestore handles them natively
        return data
    elif isinstance(data, (int, bool)) or data is None:
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
    tz_offset = int(os.getenv("TZ_OFFSET_HOURS", "1"))
    window_hours = int(os.getenv("WINDOW_HOURS", "24"))
    
    if not username or not password:
        raise ValueError(
            "EASYVIEW_USERNAME and EASYVIEW_PASSWORD must be set in .env file"
        )
    
    # Initialize client
    client = EasyViewClient(username, password, user_type)
    
    # Login (this will extract and store user_id)
    client.login()
    
    print(f"Using user_id: {client.user_id}")
    
    # Get status
    status_data = client.get_status(tz_offset, window_hours)
    
    print(f"Status retrieved successfully")
    print(f"Response data keys: {list(status_data.keys()) if isinstance(status_data, dict) else 'N/A'}")
    
    # Prepare data for Firestore - add timestamp and extract 'data' field if present
    firestore_data = {
        "timestamp": firestore.SERVER_TIMESTAMP,
        "fetched_at": int(time.time()),
        "data": status_data['data']
    }
    
    # Save to Firestore
    # Use user_id from the client
    save_to_firestore(client.user_id, firestore_data)
    
    print("Process completed successfully")


if __name__ == "__main__":
    main()
