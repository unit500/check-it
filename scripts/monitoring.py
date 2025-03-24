import sqlite3
import subprocess
import platform
import socket
import logging
import os
import base64
import requests
from datetime import datetime, timedelta
from checkhost import CheckHostClient  # Integration with check-host.net

# GitHub Configuration
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_OWNER = "unit500"
REPO_NAME = "check-it"
ARCHIVE_DB_PATH = "data/archive.db"
CHECKHOST_DB_PATH = "data/checkhost.db"

class Monitoring:
    def __init__(self, db_path=None, archive_path=None, hosts=None, debug=False):
        """Initialize the monitoring class with database paths and load active hosts."""
        self.debug = debug
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_path = db_path if db_path else os.path.join(script_dir, "..", "data", "data.db")
        self.archive_path = archive_path if archive_path else os.path.join(script_dir, "..", ARCHIVE_DB_PATH)
        self.checkhost_path = os.path.join(script_dir, "..", CHECKHOST_DB_PATH)
        self.hosts = hosts if hosts is not None else self.load_active_hosts()

    def load_active_hosts(self):
        """Load active hosts from data.db where finished = 0 and the scan has not expired."""
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
                    start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
                    time_limit = start_dt + timedelta(hours=duration)
                    if now < time_limit:
                        hosts.append(domain)
                    else:
                        logging.info("Marking scan as finished for %s: exceeded %d hours.", domain, duration)
                        self.mark_scan_finished(domain)
                else:
                    logging.warning("Missing duration or start time for %s. Using default behavior.", domain)
                    hosts.append(domain)
            conn.close()
            logging.debug("Loaded active hosts: %s", hosts)
        except Exception as e:
            logging.error("Error loading active hosts from DB: %s", e)
        return hosts

    def run(self):
        """Run monitoring checks for all active hosts and integrate with check-host.net."""
        logging.debug("Starting monitoring checks for hosts: %s", self.hosts)
        results = []
        checkhost_client = CheckHostClient(debug=self.debug)
        for host in self.hosts:
            status, details = self.check_host(host)
            results.append({"host": host, "status": status, "details": details})
            self.update_host_status(host, status, details)
            logging.debug("Host %s status: %s, Details: %s", host, status, details)

            local_scan_id = checkhost_client.initiate_scan(host)
            if local_scan_id:
                self.update_checkhost_reference(host, local_scan_id)
                result_data = checkhost_client.get_scan_result(local_scan_id)
                if result_data:
                    up_count, down_count = checkhost_client.process_result(result_data)
                    checkhost_client.update_summary(local_scan_id, up_count, down_count)
        self.upload_to_github(self.checkhost_path, "Update checkhost.db after monitoring")
        return results

    def update_checkhost_reference(self, host, local_scan_id):
        """Update the scans record in data.db with the checkhost linking ID."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("UPDATE scans SET checkhost_id = ? WHERE domain = ?", (local_scan_id, host))
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error("Failed to update checkhost reference for %s: %s", host, e)

    def check_host(self, host, port=80):
        """Check if a host is reachable via ping and TCP connection."""
        ping_status = "Ping failed"
        try:
            cmd = (["ping", "-c", "1", "-W", "2", host]
                   if platform.system().lower() != 'windows'
                   else ["ping", "-n", "1", "-w", "2000", host])
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode == 0:
                ping_status = "Ping successful"
        except Exception as e:
            logging.error("Ping error for %s: %s", host, e)

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
        """Update the scan record in data.db with the latest result for a host."""
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
                (status, details, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 total_scans, successful_scans, failed_scans, host)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error("Failed to update status for %s: %s", host, e)

    def mark_scan_finished(self, host):
        """
        When a scan expires, update finished = 1 in data.db,
        re-read the updated row, archive it into archive.db,
        and then delete it from data.db.
        (Since rows in archive.db are considered completed, we do not need to further mark them.)
        """
        try:
            conn = sqlite3.connect(self.db_path, timeout=30)
            cursor = conn.cursor()
            # Get table columns (assumes the table already has a 'finished' column)
            cursor.execute("PRAGMA table_info(scans)")
            columns = [row[1] for row in cursor.fetchall()]
            column_names = ", ".join(columns)
            placeholders = ", ".join(["?" for _ in columns])
            
            # Update the record's finished field to 1
            cursor.execute("UPDATE scans SET finished = 1 WHERE domain = ?", (host,))
            conn.commit()
            # Re-read the updated row so that finished now equals 1
            cursor.execute(f"SELECT {column_names} FROM scans WHERE domain = ?", (host,))
            row = cursor.fetchone()
            if row:
                # Archive the updated record into archive.db (no need to check finished here)
                archive_conn = sqlite3.connect(self.archive_path, timeout=30)
                archive_cursor = archive_conn.cursor()
                archive_cursor.execute(f"CREATE TABLE IF NOT EXISTS scans ({column_names})")
                archive_cursor.execute(f"INSERT OR REPLACE INTO scans ({column_names}) VALUES ({placeholders})", row)
                archive_conn.commit()
                archive_conn.close()

                # Delete the record from data.db
                cursor.execute("DELETE FROM scans WHERE domain = ?", (host,))
                conn.commit()
                conn.close()

                logging.info(f"✅ Finished scan for {host} archived and removed from active scans.")
                self.upload_to_github(self.archive_path, "Update archive.db after monitoring")
            else:
                logging.warning(f"No scan found for {host} to archive.")
        except Exception as e:
            logging.error(f"❌ Failed to archive scan for {host}: {e}")

    def upload_to_github(self, file_path, commit_message):
        """Upload the specified file to GitHub using the API."""
        if not GITHUB_TOKEN:
            logging.error("GitHub token is missing. Cannot upload.")
            return
        repo_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
        repo_file_path = os.path.relpath(file_path, repo_root)
        base_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{repo_file_path}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        with open(file_path, "rb") as f:
            content = base64.b64encode(f.read()).decode()
        get_response = requests.get(f"{base_url}?ref=main", headers=headers)
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
