import sqlite3
import subprocess
import platform
import socket
import logging
import os
from datetime import datetime, timedelta

class Monitoring:
    def __init__(self, db_path=None, archive_path=None, hosts=None, debug=False):
        """Initialize the monitoring class, setting up database path, archive path, and logging."""
        self.debug = debug
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_path = db_path if db_path else os.path.join(script_dir, "..", "data", "data.db")
        self.archive_path = archive_path if archive_path else os.path.join(script_dir, "..", "data", "archive.db")

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
                    hosts.append(domain)  # Default behavior if no duration set

            conn.close()
            logging.debug("Loaded active hosts from DB: %s", hosts)
        except Exception as e:
            logging.error("Error loading active hosts from DB: %s", e)
        return hosts

    def run(self):
        """Runs monitoring checks for all active hosts."""
        logging.debug("Starting monitoring checks for hosts: %s", self.hosts)
        results = []
        for host in self.hosts:
            status, details = self.check_host(host)
            results.append({"host": host, "status": status, "details": details})
            self.update_host_status(host, status, details)
            logging.debug("Host %s status: %s, Details: %s", host, status, details)
        return results

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

        # Step 2: Attempt a TCP connection
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
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get column names dynamically
            cursor.execute("PRAGMA table_info(scans);")
            columns = [row[1] for row in cursor.fetchall()]
            column_names = ", ".join(columns)
            placeholders = ", ".join(["?" for _ in columns])

            # Fetch row data
            cursor.execute(f"SELECT {column_names} FROM scans WHERE domain = ?", (host,))
            row = cursor.fetchone()

            if row:
                logging.info(f"Preparing to archive scan for {host}")

                # Ensure correct path
                archive_abs_path = os.path.abspath(self.archive_path)
                logging.info(f"Archive DB path: {archive_abs_path}")

                archive_conn = sqlite3.connect(archive_abs_path)
                archive_cursor = archive_conn.cursor()

                # Ensure the archive table exists
                archive_cursor.execute(f"CREATE TABLE IF NOT EXISTS scans ({column_names})")
                archive_cursor.execute(f"INSERT INTO scans ({column_names}) VALUES ({placeholders})", row)

                archive_conn.commit()
                archive_conn.execute("PRAGMA wal_checkpoint(FULL);")  # Ensure writes are flushed
                archive_conn.close()
                logging.info(f"✅ Successfully moved {host} to archive.db")

                # Ensure SQLite flushes writes to disk
                cursor.execute("PRAGMA wal_checkpoint(FULL);")
                conn.commit()
                conn.close()
                logging.info(f"✅ Changes fully written to disk for {host}.")

                # Push archive.db to GitHub
                self.upload_to_github(self.archive_path, "Update archive.db after monitoring")

            else:
                logging.warning(f"No scan found for {host} to archive.")

        except Exception as e:
            logging.error(f"❌ Failed to move scan to archive for {host}: {e}")
