import sqlite3
import subprocess
import platform
import socket
import logging
import os
import base64
import requests
from datetime import datetime, timedelta
from checkhost import CheckHostClient  # New import for check-host integration

# GitHub Configuration
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_OWNER = "unit500"
REPO_NAME = "check-it"
ARCHIVE_DB_PATH = "data/archive.db"
CHECKHOST_DB_PATH = "data/checkhost.db"  # New constant for checkhost database

class Monitoring:
    def __init__(self, db_path=None, archive_path=None, hosts=None, debug=False):
        """Initialize the monitoring class, setting up database path, archive path, and logging."""
        self.debug = debug
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_path = db_path if db_path else os.path.join(script_dir, "..", "data", "data.db")
        # Use provided archive_path or default based on repo structure.
        self.archive_path = archive_path if archive_path else os.path.join(script_dir, "..", ARCHIVE_DB_PATH)
        # Define the checkhost.db path similarly.
        self.checkhost_path = os.path.join(script_dir, "..", CHECKHOST_DB_PATH)

        if hosts is not None:
            self.hosts = hosts
        else:
            self.hosts = self.load_active_hosts()

    def load_active_hosts(self):
        """Load active hosts from the database that have not exceeded their duration."""
        hosts = []
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT domain, start_time, duration FROM scans WHERE finished = 0")
            rows = cursor.fetchall()

            now = datetime.now()
            for row in rows:
                domain, start_time, duration = row
                if duration and start_time:
                    start_time_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
                    time_limit = start_time_dt + timedelta(hours=duration)
                    if now < time_limit:
                        hosts.append(domain)  # Scan if within allowed duration
                    else:
                        logging.info("Marking scan as finished for %s: exceeded %d hours.", domain, duration)
                        self.mark_scan_finished(domain)  # Move to archive if expired
                else:
                    logging.warning("Missing duration or start time for %s. Using default behavior.", domain)
                    hosts.append(domain)
            conn.close()
            logging.debug("Loaded active hosts from DB: %s", hosts)
        except Exception as e:
            logging.error("Error loading active hosts from DB: %s", e)
        return hosts

    def run(self):
        """Runs monitoring checks for all active hosts, including check-host.net integration."""
        logging.debug("Starting monitoring checks for hosts: %s", self.hosts)
        results = []
        # Create an instance of the check-host client
        checkhost_client = CheckHostClient(debug=self.debug)
        for host in self.hosts:
            # Local check (ping + TCP connection)
            status, details = self.check_host(host)
            results.append({"host": host, "status": status, "details": details})
            self.update_host_status(host, status, details)
            logging.debug("Host %s status: %s, Details: %s", host, status, details)

            # --- Begin Check-Host Integration ---
            local_scan_id = checkhost_client.initiate_scan(host)
            if local_scan_id:
                # Update the scans table in data.db with the checkhost linking ID
                self.update_checkhost_reference(host, local_scan_id)
                # Retrieve the result (in a real scenario you might wait a few seconds before polling)
                result_data = checkhost_client.get_scan_result(local_scan_id)
                if result_data:
                    up_count, down_count = checkhost_client.process_result(result_data)
                    checkhost_client.update_summary(local_scan_id, up_count, down_count)
                    # Optionally update your data.db scans record with the summary counts.
            # --- End Check-Host Integration ---
        # After processing all hosts, upload the checkhost database to GitHub.
        self.upload_to_github(self.checkhost_path, "Update checkhost.db after monitoring")
        return results

    def update_checkhost_reference(self, host, local_scan_id):
        """Update the scans record in data.db with the checkhost linking ID."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            # Ensure that your scans table has a column named checkhost_id.
            cursor.execute("UPDATE scans SET checkhost_id = ? WHERE domain = ?", (local_scan_id, host))
            conn.commit()
            conn.close()
            logging.info("Updated checkhost_id for %s with local_scan_id %s", host, local_scan_id)
        except Exception as e:
            logging.error("Failed to update checkhost reference for %s: %s", host, e)

    def check_host(self, host, port=80):
        """Check if a host is reachable via ping and TCP connection."""
        logging.debug("Checking host: %s on port %d", host, port)
        # Step 1: Ping the host
        ping_status = "Ping failed"
        try:
            cmd = ["ping", "-c", "1", "-W", "2", host] if platform.system().lower() != 'windows' else ["ping", "-n", "1", "-w", "2000", host]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode == 0:
                ping_status = "Ping successful"
        except Exception as e:
            logging.error("Ping error for %s: %s", host, e)
        # Step 2: TCP connection check
        connection_status = "Connection failed"
        try:
            with socket.create_connection((host, port), timeout=3):
                connection_status = "Connection successful"
        except Exception as e:
            connection_status = f"Connection error: {e}"
            logging.error("Connection error for %s: %s", host, e)
        status = "Up" if "successful" in connection_status else "Down"
        details = f"{ping_status}, {connection_status}"
        return status, details

    def update_host_status(self, host, status, details):
        """Update the database with the latest scan result."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT total_scans, successful_scans, failed_scans FROM scans WHERE domain = ?", (host,))
            row = cursor.fetchone()
            if row:
                total_scans, successful_scans, failed_scans = row
                total_scans += 1
                if status == "Up":
                    successful_scans += 1
                else:
                    failed_scans += 1
            else:
                total_scans, successful_scans, failed_scans = 1, 1 if status == "Up" else 0, 1 if status == "Down" else 0

            cursor.execute("""
                UPDATE scans SET 
                    status = ?, 
                    details = ?, 
                    last_scan_time = ?, 
                    total_scans = ?, 
                    successful_scans = ?, 
                    failed_scans = ? 
                WHERE domain = ?""",
                (status, details, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), total_scans, successful_scans, failed_scans, host)
            )
            conn.commit()
            conn.close()
            logging.debug("Updated scan counts for %s - Total: %d, Success: %d, Failed: %d", host, total_scans, successful_scans, failed_scans)
        except Exception as e:
            logging.error("Failed to update status for %s: %s", host, e)

    def mark_scan_finished(self, host):
        """Move finished scans to archive.db and remove them from data.db."""
        try:
            # Increase timeout to help prevent "database is locked" errors
            conn = sqlite3.connect(self.db_path, timeout=30)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(scans);")
            columns = [row[1] for row in cursor.fetchall()]
            column_names = ", ".join(columns)
            placeholders = ", ".join(["?" for _ in columns])
            cursor.execute(f"SELECT {column_names} FROM scans WHERE domain = ?", (host,))
            row = cursor.fetchone()
            if row:
                logging.info(f"Preparing to archive scan for {host}")
                archive_abs_path = os.path.abspath(self.archive_path)
                logging.info(f"Archive DB path: {archive_abs_path}")
                archive_conn = sqlite3.connect(archive_abs_path, timeout=30)
                archive_cursor = archive_conn.cursor()
                # Create table if it does not exist
                archive_cursor.execute(f"CREATE TABLE IF NOT EXISTS scans ({column_names})")
                # Use INSERT OR REPLACE to handle duplicates (avoids UNIQUE constraint errors)
                archive_cursor.execute(f"INSERT OR REPLACE INTO scans ({column_names}) VALUES ({placeholders})", row)
                archive_conn.commit()
                archive_conn.close()
                logging.info(f"✅ Successfully moved {host} to archive.db")
                cursor.execute("DELETE FROM scans WHERE domain = ?", (host,))
                conn.commit()
                conn.close()
                logging.info(f"✅ Scan for {host} deleted from active scans.")
                self.upload_to_github(self.archive_path, "Update archive.db after monitoring")
            else:
                logging.warning(f"No scan found for {host} to archive.")
        except Exception as e:
            logging.error(f"❌ Failed to move scan to archive for {host}: {e}")

    def upload_to_github(self, file_path, commit_message):
        """Uploads a file to GitHub using the API."""
        if not GITHUB_TOKEN:
            logging.error("GitHub token is missing. Cannot upload.")
            return
        # Compute the repository file path as relative to the repository root.
        repo_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
        repo_file_path = os.path.relpath(file_path, repo_root)
        base_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{repo_file_path}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        with open(file_path, "rb") as f:
            content = base64.b64encode(f.read()).decode()
        # Fetch the current file SHA if it exists
        get_url = f"{base_url}?ref=main"
        get_response = requests.get(get_url, headers=headers)
        file_sha = get_response.json().get("sha") if get_response.status_code == 200 else None
        data = {
            "message": commit_message,
            "content": content,
            "branch": "main"
        }
        if file_sha:
            data["sha"] = file_sha
        response = requests.put(base_url, json=data, headers=headers)
        if response.status_code in [200, 201]:
            logging.info(f"✅ GitHub Commit Successful: {repo_file_path} updated.")
        else:
            logging.error(f"❌ GitHub Commit Failed for {repo_file_path}: {response.text}")
