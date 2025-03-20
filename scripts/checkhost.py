import sqlite3
import os
import json
import logging
import requests
from datetime import datetime

# Define the default path for the checkhost database
CHECKHOST_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "checkhost.db")

class CheckHostClient:
    def __init__(self, db_path=None, debug=False):
        self.debug = debug
        self.db_path = db_path if db_path else CHECKHOST_DB_PATH
        
        # Check if the checkhost.db file exists; if not, log and it will be created on connect.
        if not os.path.exists(self.db_path):
            logging.info("checkhost.db not found. Creating new checkhost database at %s", self.db_path)
        self._init_db()

    def _init_db(self):
        """Initialize the checkhost.db and create necessary tables if they do not exist."""
        # Connecting will automatically create the file if it doesn't exist.
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # Create the scan_meta table to store meta information for each scan.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scan_meta (
                id TEXT PRIMARY KEY,
                host TEXT,
                first_scan DATETIME,
                last_scan DATETIME,
                summary_up INTEGER DEFAULT 0,
                summary_down INTEGER DEFAULT 0
            )
        """)
        # Create the scan_results table to store each API call's response.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scan_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id TEXT,
                call_type TEXT,
                response TEXT,
                timestamp DATETIME,
                FOREIGN KEY(scan_id) REFERENCES scan_meta(id)
            )
        """)
        conn.commit()
        conn.close()

    def initiate_scan(self, host):
        """Initiate a scan via check-host.net API and store meta data.
        
        Returns the unique request_id provided by check-host.net.
        """
        url = f"https://check-host.net/check-http?host={host}"
        headers = {"Accept": "application/json"}
        try:
            response = requests.get(url, headers=headers, timeout=10)
            data = response.json()
            request_id = data.get("request_id")
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if request_id:
                # Insert or update meta information
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM scan_meta WHERE id = ?", (request_id,))
                row = cursor.fetchone()
                if row:
                    # Update the last scan time if the record already exists
                    cursor.execute("UPDATE scan_meta SET last_scan = ? WHERE id = ?", (now, request_id))
                else:
                    cursor.execute("""
                        INSERT INTO scan_meta (id, host, first_scan, last_scan)
                        VALUES (?, ?, ?, ?)
                    """, (request_id, host, now, now))
                # Save the initiate call result in scan_results
                cursor.execute("""
                    INSERT INTO scan_results (scan_id, call_type, response, timestamp)
                    VALUES (?, 'initiate', ?, ?)
                """, (request_id, json.dumps(data), now))
                conn.commit()
                conn.close()
                logging.info(f"CheckHost: Initiated scan for {host}, request_id: {request_id}")
                return request_id
            else:
                logging.error("CheckHost: No request_id returned on initiating scan.")
                return None
        except Exception as e:
            logging.error(f"CheckHost: Error initiating scan for {host}: {e}")
            return None

    def get_scan_result(self, request_id):
        """Fetch scan result using the provided request_id and store the API response."""
        url = f"https://check-host.net/check-result/{request_id}"
        headers = {"Accept": "application/json"}
        try:
            response = requests.get(url, headers=headers, timeout=10)
            data = response.json()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # Save the result in scan_results
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO scan_results (scan_id, call_type, response, timestamp)
                VALUES (?, 'result', ?, ?)
            """, (request_id, json.dumps(data), now))
            conn.commit()
            conn.close()
            logging.info(f"CheckHost: Retrieved scan result for request_id: {request_id}")
            return data
        except Exception as e:
            logging.error(f"CheckHost: Error retrieving scan result for {request_id}: {e}")
            return None

    def process_result(self, result):
        """Process the JSON result to count how many nodes are up versus down.
        
        Returns:
            (up_count, down_count)
        """
        up_count = 0
        down_count = 0
        if not result:
            return up_count, down_count

        # The API returns a JSON object whose keys are node identifiers.
        for node, values in result.items():
            if isinstance(values, list):
                for entry in values:
                    if isinstance(entry, list) and entry:
                        # Assuming that a value of 1 in the first element indicates "up"
                        if entry[0] == 1:
                            up_count += 1
                        else:
                            down_count += 1
                    else:
                        down_count += 1
            else:
                down_count += 1
        return up_count, down_count

    def update_summary(self, request_id, up_count, down_count):
        """Update the scan_meta record with the summary of up/down counts."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE scan_meta
                SET summary_up = ?, summary_down = ?
                WHERE id = ?
            """, (up_count, down_count, request_id))
            conn.commit()
            conn.close()
            logging.info(f"CheckHost: Updated summary for request_id {request_id}: Up={up_count}, Down={down_count}")
        except Exception as e:
            logging.error(f"CheckHost: Error updating summary for request_id {request_id}: {e}")
