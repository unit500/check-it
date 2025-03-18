import sqlite3
import subprocess
import platform
import socket
import logging
import os
from datetime import datetime, timedelta

class Monitoring:
    def __init__(self, db_path=None, archive_path=None, hosts=None, debug=False):
        """Initialize the monitoring class, setting up database path and archive path."""
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
                        self.mark_scan_finished(domain)  # Move to archive if expired
                else:
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
        
        ping_status = "Ping failed"
        try:
            cmd = ["ping", "-c", "1", "-W", "2", host] if platform.system().lower() != 'windows' else ["ping", "-n", "1", "-w", "2000", host]
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

            cursor.execute("SELECT * FROM scans WHERE domain = ?", (host,))
            row = cursor.fetchone()

            if row:
                # Insert into archive database
                archive_conn = sqlite3.connect(self.archive_path)
                archive_cursor = archive_conn.cursor()

                archive_cursor.execute("""
                    CREATE TABLE IF NOT EXISTS scans (
                        domain TEXT PRIMARY KEY,
                        status TEXT,
                        details TEXT,
                        start_time TEXT,
                        last_scan_time TEXT,
                        total_scans INTEGER,
                        successful_scans INTEGER,
                        failed_scans INTEGER,
                        duration INTEGER,
                        finished INTEGER
                    )
                """)

                archive_cursor.execute("""
                    INSERT INTO scans 
                    (domain, status, details, start_time, last_scan_time, total_scans, successful_scans, failed_scans, duration, finished)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, row)

                archive_conn.commit()
                archive_conn.close()

                # Remove from active database
                cursor.execute("DELETE FROM scans WHERE domain = ?", (host,))
                conn.commit()
                conn.close()

                logging.info("Moved scan for %s to archive and marked as finished.", host)

        except Exception as e:
            logging.error("Failed to move scan to archive for %s: %s", host, e)
