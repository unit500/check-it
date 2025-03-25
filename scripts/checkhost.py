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
        
        # If checkhost.db does not exist, log that we are creating one.
        if not os.path.exists(self.db_path):
            logging.info("checkhost.db not found. Creating new checkhost database at %s", self.db_path)
        self._init_db()

    def _init_db(self):
        """Initialize the checkhost.db and create necessary tables if they do not exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # Create scan_meta table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scan_meta (
                local_id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT,
                checkhost_id TEXT,
                first_scan DATETIME,
                last_scan DATETIME,
                summary_up INTEGER DEFAULT 0,
                summary_down INTEGER DEFAULT 0
            )
        """)
        # Create scan_results table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scan_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                local_scan_id INTEGER,
                call_type TEXT,
                response TEXT,
                timestamp DATETIME,
                FOREIGN KEY(local_scan_id) REFERENCES scan_meta(local_id)
            )
        """)
        conn.commit()
        conn.close()

    def initiate_scan(self, host):
        """Initiate a scan via check-host.net API and store meta data."""
        url = f"https://check-host.net/check-http?host={host}"
        headers = {"Accept": "application/json"}
        try:
            response = requests.get(url, headers=headers, timeout=10)
            data = response.json()
            checkhost_id = data.get("request_id")
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if checkhost_id:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO scan_meta (domain, checkhost_id, first_scan, last_scan)
                    VALUES (?, ?, ?, ?)
                """, (host, checkhost_id, now, now))
                local_scan_id = cursor.lastrowid
                cursor.execute("""
                    INSERT INTO scan_results (local_scan_id, call_type, response, timestamp)
                    VALUES (?, 'initiate', ?, ?)
                """, (local_scan_id, json.dumps(data), now))
                conn.commit()
                conn.close()
                logging.info(f"CheckHost: Initiated scan for {host}, checkhost_id: {checkhost_id}, local_scan_id: {local_scan_id}")
                return local_scan_id
            else:
                logging.error("CheckHost: No request_id returned on initiating scan.")
                return None
        except Exception as e:
            logging.error(f"CheckHost: Error initiating scan for {host}: {e}")
            return None

    def get_scan_result(self, local_scan_id):
        """Fetch scan result using the checkhost_id and store the API response."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT checkhost_id FROM scan_meta WHERE local_id = ?", (local_scan_id,))
            row = cursor.fetchone()
            if not row:
                logging.error(f"CheckHost: No scan_meta record found for local_scan_id {local_scan_id}")
                conn.close()
                return None
            checkhost_id = row[0]
            conn.close()

            url = f"https://check-host.net/check-result/{checkhost_id}"
            headers = {"Accept": "application/json"}
            response = requests.get(url, headers=headers, timeout=10)
            data = response.json()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO scan_results (local_scan_id, call_type, response, timestamp)
                VALUES (?, 'result', ?, ?)
            """, (local_scan_id, json.dumps(data), now))
            conn.commit()
            conn.close()
            logging.info(f"CheckHost: Retrieved scan result for local_scan_id: {local_scan_id}")
            return data
        except Exception as e:
            logging.error(f"CheckHost: Error retrieving scan result for local_scan_id {local_scan_id}: {e}")
            return None

    def process_result(self, result):
        """Process the JSON result to count how many nodes are up versus down."""
        up_count = 0
        down_count = 0
        if not result:
            return up_count, down_count

        for node, values in result.items():
            if isinstance(values, list):
                for entry in values:
                    if isinstance(entry, list) and entry:
                        if entry[0] == 1:
                            up_count += 1
                        else:
                            down_count += 1
                    else:
                        down_count += 1
            else:
                down_count += 1
        return up_count, down_count

    def update_summary(self, local_scan_id, up_count, down_count):
        """Update the scan_meta record with the summary of up/down counts."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                UPDATE scan_meta
                SET summary_up = ?, summary_down = ?, last_scan = ?
                WHERE local_id = ?
            """, (up_count, down_count, now, local_scan_id))
            conn.commit()
            conn.close()
            logging.info(f"CheckHost: Updated summary for local_scan_id {local_scan_id}: Up={up_count}, Down={down_count}")
        except Exception as e:
            logging.error(f"CheckHost: Error updating summary for local_scan_id {local_scan_id}: {e}")

    def export_and_remove_domain_data(self, domain, output_file):
        """
        Export all check-host data for the given domain to a JSON file,
        then remove those rows from checkhost.db (both scan_meta and scan_results).
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Gather all local_ids for this domain
            cursor.execute("SELECT local_id, checkhost_id, first_scan, last_scan, summary_up, summary_down FROM scan_meta WHERE domain = ?", (domain,))
            rows_meta = cursor.fetchall()
            if not rows_meta:
                logging.info("No checkhost data found for domain %s", domain)
                conn.close()
                return None

            domain_export = {
                "domain": domain,
                "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "local_ids": []
            }

            local_ids = [row[0] for row in rows_meta]
            for row in rows_meta:
                local_scan_id = row[0]
                checkhost_id = row[1]
                first_scan = row[2]
                last_scan = row[3]
                summary_up = row[4]
                summary_down = row[5]
                
                # Gather results for this local_id
                cursor.execute("SELECT call_type, response, timestamp FROM scan_results WHERE local_scan_id = ?", (local_scan_id,))
                rows_results = cursor.fetchall()
                results_list = []
                for r in rows_results:
                    call_type, response_json, ts = r
                    try:
                        parsed_response = json.loads(response_json)
                    except:
                        parsed_response = response_json
                    results_list.append({
                        "call_type": call_type,
                        "response": parsed_response,
                        "timestamp": ts
                    })
                    
                domain_export["local_ids"].append({
                    "local_scan_id": local_scan_id,
                    "checkhost_id": checkhost_id,
                    "first_scan": first_scan,
                    "last_scan": last_scan,
                    "summary_up": summary_up,
                    "summary_down": summary_down,
                    "scan_results": results_list
                })

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(domain_export, f, indent=4)
            logging.info("Exported check-host data for domain %s to %s", domain, output_file)

            # Remove rows from scan_results and scan_meta
            for local_id in local_ids:
                cursor.execute("DELETE FROM scan_results WHERE local_scan_id = ?", (local_id,))
                cursor.execute("DELETE FROM scan_meta WHERE local_id = ?", (local_id,))
            conn.commit()
            conn.close()
            return output_file
        except Exception as e:
            logging.error("Failed to export/remove checkhost data for domain %s: %s", domain, e)
            return None
