"""
EasyView API client for fetching glucose monitor status and saving to Firestore.
"""

import os
import sys
import base64
import json
import time
import math
import datetime
import urllib.parse
import logging
import logging.handlers
import signal
from pathlib import Path
from typing import Dict, Any, Optional, Union

import requests
import firebase_admin
from firebase_admin import credentials, firestore, db
from dotenv import load_dotenv


# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent.absolute()

# Load environment variables
env_path = SCRIPT_DIR / ".env"
load_dotenv(env_path)

# Configure logging
LOG_DIR = SCRIPT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOG_FILE = LOG_DIR / "gluco-watch.log"
LOG_FILE_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
LOG_BACKUP_COUNT = 5  # Keep 5 backup files

# Create logger
logger = logging.getLogger("gluco-watch")
logger.setLevel(logging.DEBUG)

# Create formatters
detailed_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
simple_formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# File handler with rotation
file_handler = logging.handlers.RotatingFileHandler(
    LOG_FILE,
    maxBytes=LOG_FILE_MAX_BYTES,
    backupCount=LOG_BACKUP_COUNT,
    encoding='utf-8'
)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(detailed_formatter)

# Console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(simple_formatter)

# Add handlers to logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Global flag for graceful shutdown
shutdown_flag = False

# Firebase initialization
FIREBASE_CREDENTIALS_PATH = SCRIPT_DIR / "gluco-watch-firebase-adminsdk-fbsvc-cd567c4e05.json"
FIREBASE_DATABASE_URL = os.getenv("FIREBASE_DATABASE_URL", "https://gluco-watch-default-rtdb.europe-west1.firebasedatabase.app/")

if not firebase_admin._apps:
    if not FIREBASE_CREDENTIALS_PATH.exists():
        logger.error(f"Firebase credentials file not found: {FIREBASE_CREDENTIALS_PATH}")
        raise FileNotFoundError(f"Firebase credentials file not found: {FIREBASE_CREDENTIALS_PATH}")
    
    cred = credentials.Certificate(str(FIREBASE_CREDENTIALS_PATH))
    # Initialize with database URL for Realtime Database support
    firebase_admin.initialize_app(cred, {
        'databaseURL': FIREBASE_DATABASE_URL
    })
    logger.info(f"Firebase initialized with database URL: {FIREBASE_DATABASE_URL}")

db_firestore = firestore.client()


def dump_data_to_json_file(data, filename="dump_data.json"):
    """
    Dump the provided data to a JSON file for inspection or debugging.
    Args:
        data: The data (usually dict or list) to dump.
        filename: The output filename (default "dump_data.json")
    """
    dump_path = SCRIPT_DIR / filename
    try:
        with open(dump_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.debug(f"Data dumped to {dump_path}")
    except Exception as e:
        logger.error(f"Failed to dump data to {dump_path}: {e}", exc_info=True)

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
        logger.info(f"Attempting login for user: {self.username}")
        payload = {
            "user_name": self.username,
            "user_type": self.user_type,
            "password": "***" if self.password else None,  # Don't log password
        }
        logger.debug(f"Login payload (password hidden): {payload}")
        
        payload = {
            "user_name": self.username,
            "user_type": self.user_type,
            "password": self.password,
        }
        
        try:
            response = self.session.post(
                self.LOGIN_URL,
                json=payload,
                headers=self._get_login_headers(),
                timeout=30
            )
            response.raise_for_status()
            
            logger.info(f"Login successful. Status: {response.status_code}")
            
            # Extract and store user_id from login response
            self.user_id = self.extract_monitor_uid_from_login(response)
            logger.info(f"Extracted user_id: {self.user_id}")

            return response
        except requests.exceptions.Timeout:
            logger.error(f"Login request timed out after 30 seconds")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Login request failed: {e}", exc_info=True)
            raise
    
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
            logger.debug(f"Login response keys: {list(login_data.keys())}")
            
            # Try to extract UID from response (adjust based on actual API response structure)
            if "monitor_uid" in login_data:
                uid = login_data["monitor_uid"]
                logger.debug(f"Found monitor_uid in response: {uid}")
                return uid
            elif "uid" in login_data:
                uid = login_data["uid"]
                logger.debug(f"Found uid in response: {uid}")
                return uid
            else:
                # Log the full response for debugging (but mask sensitive data)
                logger.error(f"Could not find monitor_uid or uid in login response. Available keys: {list(login_data.keys())}")
                logger.debug(f"Login response (sanitized): {json.dumps(login_data, default=str)}")
                raise ValueError(
                    "EASYVIEW_MONITOR_UID not set and could not be extracted from login response. "
                    "Please set it in .env file."
                )
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse login response as JSON: {e}")
            logger.debug(f"Response text: {login_response.text[:500]}")
            raise ValueError(
                f"Could not extract monitor UID from login response: {e}. "
                "Please set EASYVIEW_MONITOR_UID in .env file."
            )
        except KeyError as e:
            logger.error(f"Key error while extracting monitor UID: {e}")
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
            logger.error("user_id not set. Login must be called first.")
            raise ValueError(
                "user_id not set. Please call login() first to extract user_id from login response."
            )
        
        logger.info(f"Fetching status for monitor_uid: {self.user_id} (tz_offset={tz_offset_hours}h, window={window_hours}h)")
        param = self._build_easyview_param(tz_offset_hours, window_hours)
        status_url = f"{self.STATUS_URL_TEMPLATE.format(monitor_uid=self.user_id)}?param={param}"
        logger.debug(f"Status URL: {status_url}")
        
        try:
            response = self.session.get(
                status_url,
                headers=self._get_status_headers(),
                timeout=30
            )
            response.raise_for_status()
            logger.info(f"Status request successful. Status code: {response.status_code}")

            # Dump the raw response JSON to a file for debugging or inspection
            dump_path = SCRIPT_DIR / "response_dump.json"
            try:
                with open(dump_path, "w", encoding="utf-8") as f:
                    f.write(response.text)
                logger.debug(f"Response dumped to {dump_path}")
            except Exception as e:
                logger.warning(f"Failed to dump response to file: {e}")
            
            return json.loads(response.text)
        except requests.exceptions.Timeout:
            logger.error(f"Status request timed out after 30 seconds")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Status request failed: {e}", exc_info=True)
            raise
    
    def get_values(self, data):
        """
        Extract glucose values from status data.
        
        Args:
            data: Status data dictionary from get_status()
            
        Returns:
            Dictionary with glucose, timestamp, and time
        """
        try:
            if 'data' not in data or 'chart' not in data['data'] or 'sg' not in data['data']['chart']:
                logger.error(f"Unexpected data structure. Available keys: {list(data.keys())}")
                raise ValueError("Status data does not contain expected structure: data.chart.sg")
            
            sg_data = data['data']['chart']['sg']
            if not sg_data or len(sg_data) == 0:
                logger.warning("No glucose data (sg) found in response")
                raise ValueError("No glucose data available in response")
            
            last_item = sg_data[-1]
            logger.debug(f"Last glucose reading: {last_item}")

            ts_utc = float(last_item[0])
            dt = datetime.datetime.fromtimestamp(ts_utc)  # - tz_offset * 3600 - not used by them
            values = {
                "glucose": round(last_item[1], 1),
                "timestamp": ts_utc,
                "time": dt.isoformat(),
            }
            
            logger.info(f"Extracted values: glucose={values['glucose']}, time={values['time']}")
            return values
        except (KeyError, IndexError, ValueError, TypeError) as e:
            logger.error(f"Failed to extract values from data: {e}", exc_info=True)
            raise


    @staticmethod
    def _build_easyview_param(tz_offset_hours: int = 1, window_hours: int = 24) -> str:
        """
        Build EasyView API parameter string.
        
        Args:
            tz_offset_hours: Timezone offset (CET = 1)
            window_hours: How many hours back to fetch (default: 24)
            
        Returns:
            URL-encoded base64 parameter string
        """
        # Current time in UTC seconds
        now_utc = int(time.time())
        
        # Adjust for timezone to get current time in local timezone
        now_tz_local = now_utc + tz_offset_hours * 3600
        
        # Calculate seconds since midnight in local timezone
        seconds_since_midnight = now_tz_local % 86400  # 86400 = seconds in a day
        
        # Calculate following midnight (next midnight) in local timezone
        # Always round up to the next midnight
        if seconds_since_midnight == 0:
            # Exactly at midnight, use next midnight (tomorrow)
            next_midnight_tz = now_tz_local + 86400
        else:
            # Round up to next midnight (tomorrow)
            next_midnight_tz = now_tz_local - seconds_since_midnight + 86400
        
        # Convert back to UTC for the API (subtract timezone offset)
        now_tz = next_midnight_tz - tz_offset_hours * 3600
        
        # Window start: 24 hours back from following midnight
        start_tz = now_tz - window_hours * 3600
        
        payload = {
            "ts": [start_tz, now_tz],
            "tz": tz_offset_hours
        }
        
        # Compact JSON (no spaces!)
        json_str = json.dumps(payload, separators=(",", ":"))
        logger.debug(f"EasyView param payload: {json_str}")
        
        # Base64 encode (standard, with == padding)
        b64 = base64.b64encode(json_str.encode()).decode()
        
        # URL encode (so == → %3D%3D)
        encoded_param = urllib.parse.quote(b64, safe="")
        logger.debug(f"Encoded param length: {len(encoded_param)}")
        return encoded_param


###########

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
    
    try:
        logger.info(f"Saving data to Firestore: users/{uid_str}")
        # Prepare data for Firestore (handle NaN, Infinity, etc.)
        #cleaned_data = prepare_for_firestore(data)
        
        doc_ref = db_firestore.collection("users").document(uid_str)
        doc_ref.set(data)
        logger.info(f"Data saved to Firestore: users/{uid_str}")

        dump_data_to_json_file(data, f"dump_data_{uid_str}.json")
    except Exception as e:
        logger.error(f"Failed to save to Firestore: {e}", exc_info=True)
        raise


def save_to_realtime_db(uid: str, data: Dict[str, Any]) -> None:
    """
    Save monitor status data to Firebase Realtime Database.
    
    Args:
        uid: User UID (will be converted to string if needed)
        data: Data to save
    """
    # Ensure uid is a string
    uid_str = str(uid)
    
    try:
        logger.info(f"Saving data to Realtime Database: users/{uid_str}/latest")
        # Get reference to the path: users/{uid}/latest
        ref = db.reference(f"users/{uid_str}/latest")
        ref.set(data)
        logger.info(f"Data saved to Realtime Database: users/{uid_str}/latest")
    except Exception as e:
        logger.error(f"Failed to save to Realtime Database: {e}", exc_info=True)
        raise


def setup():
    """Initialize and setup the EasyView client."""
    logger.info("=" * 60)
    logger.info("Starting Gluco-Watch service setup")
    logger.info("=" * 60)

    global username, password, user_type, tz_offset, window_hours
    
    # Load credentials from environment
    username = os.getenv("EASYVIEW_USERNAME")
    password = os.getenv("EASYVIEW_PASSWORD")
    user_type = os.getenv("EASYVIEW_USER_TYPE", "P")
    
    try:
        tz_offset = int(os.getenv("TZ_OFFSET_HOURS", "1"))
    except ValueError:
        logger.warning(f"Invalid TZ_OFFSET_HOURS, using default: 1")
        tz_offset = 1
    
    try:
        window_hours = int(os.getenv("WINDOW_HOURS", "24"))
    except ValueError:
        logger.warning(f"Invalid WINDOW_HOURS, using default: 24")
        window_hours = 24
    
    if not username or not password:
        logger.error("EASYVIEW_USERNAME and EASYVIEW_PASSWORD must be set in .env file")
        raise ValueError(
            "EASYVIEW_USERNAME and EASYVIEW_PASSWORD must be set in .env file"
        )
    
    logger.info(f"Configuration: user_type={user_type}, tz_offset={tz_offset}h, window_hours={window_hours}h")
    
    # Initialize client
    logger.info("Initializing EasyView client...")
    client = EasyViewClient(username, password, user_type)
    
    # Login (this will extract and store user_id)
    logger.info("Logging in to EasyView API...")
    client.login()
    
    logger.info(f"Setup complete. Using user_id: {client.user_id}")
    return client


def loop(client: EasyViewClient):
    """Execute one monitoring loop iteration."""
    logger.info("-" * 60)
    logger.info("Starting monitoring loop iteration")
    
    try:
        # Get status
        logger.info("Fetching status from EasyView API...")
        status_data = client.get_status(tz_offset, window_hours)
        logger.debug(f"Response data keys: {list(status_data.keys()) if isinstance(status_data, dict) else 'N/A'}")

        # Extract values
        logger.info("Extracting glucose values...")
        values = client.get_values(status_data)
        
        # Prepare data for Firestore - add timestamp and extract 'data' field if present
        firestore_data = {
            "main": values,
            "fetched_at": datetime.datetime.now().isoformat(),
            "fetched_at_unix": int(time.time()),
            "fetched_at_unix_ms": int(time.time() * 1000),
            #"data": prepare_for_firestore(status_data['data'])
        }
        logger.debug(f"Prepared data: glucose={values.get('glucose')}, time={values.get('time')}")
        
        # Save to Firestore
        logger.info("Saving to Firestore...")
        save_to_firestore(client.user_id, firestore_data)
        
        # Save to Realtime Database
        logger.info("Saving to Realtime Database...")
        save_to_realtime_db(client.user_id, firestore_data)
        
        logger.info("Monitoring loop iteration completed successfully")
        return True
    except Exception as e:
        logger.error(f"Error in monitoring loop: {e}", exc_info=True)
        return False


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global shutdown_flag
    logger.info(f"Received signal {signum}. Initiating graceful shutdown...")
    shutdown_flag = True


def main():
    """Main entry point for the service."""
    global shutdown_flag
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    client = None
    consecutive_errors = 0
    max_consecutive_errors = 5
    loop_interval = 2 * 60  # 2 minutes
    error_retry_interval = 5 * 60  # 5 minutes
    
    logger.info("Gluco-Watch service starting...")
    logger.info(f"Loop interval: {loop_interval}s, Error retry interval: {error_retry_interval}s")
    
    try:
        client = setup()
        
        while not shutdown_flag:
            try:
                success = loop(client)
                
                if success:
                    consecutive_errors = 0
                    logger.debug(f"Sleeping for {loop_interval} seconds until next iteration...")
                    # Sleep in smaller chunks to check shutdown_flag more frequently
                    for _ in range(loop_interval):
                        if shutdown_flag:
                            break
                        time.sleep(1)
                else:
                    consecutive_errors += 1
                    logger.warning(f"Loop iteration failed. Consecutive errors: {consecutive_errors}/{max_consecutive_errors}")
                    
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error(f"Too many consecutive errors ({consecutive_errors}). Reinitializing client...")
                        consecutive_errors = 0
                        try:
                            client = setup()
                        except Exception as e:
                            logger.error(f"Failed to reinitialize client: {e}", exc_info=True)
                            logger.info(f"Waiting {error_retry_interval} seconds before retry...")
                            for _ in range(error_retry_interval):
                                if shutdown_flag:
                                    break
                                time.sleep(1)
                    
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt")
                shutdown_flag = True
                break
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
                logger.warning(f"Consecutive errors: {consecutive_errors}/{max_consecutive_errors}")
                
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(f"Too many consecutive errors ({consecutive_errors}). Reinitializing client...")
                    consecutive_errors = 0
                    try:
                        client = setup()
                    except Exception as setup_error:
                        logger.error(f"Failed to reinitialize client: {setup_error}", exc_info=True)
                
                logger.info(f"Waiting {error_retry_interval} seconds before retry...")
                for _ in range(error_retry_interval):
                    if shutdown_flag:
                        break
                    time.sleep(1)
        
        logger.info("Shutdown flag set. Exiting gracefully...")
        
    except Exception as e:
        logger.critical(f"Fatal error in main: {e}", exc_info=True)
        raise
    finally:
        logger.info("Gluco-Watch service stopped")


if __name__ == "__main__":
    main()