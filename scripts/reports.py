import sqlite3
import subprocess
import platform
import socket
import logging
import os

class Monitoring:
    def __init__(self, db_path=None, hosts=None, debug=False):
        """Initialize the monitoring class, setting up database path and hosts list."""
        self.debug = debug
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_path = db_path if db_path else os.path.join(script_dir, "..", "data", "data.db")
        
        if hosts is not None:
            self.hosts = hosts
        else:
            self.hosts = self.load_hosts_from_db()

    def load_hosts_from_db(self):
        """Read the `scans` table from the database and return active domains."""
        hosts = []
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT domain FROM scans WHERE finished = 0")
            rows = cursor.fetchall()
            hosts = [row[0] for row in rows]
            conn.close()
            logging.debug("Loaded hosts from DB: %s", hosts)
        except Exception as e:
            logging.error("Error loading hosts from DB: %s", e)
        return hosts

    def run(self):
        """Runs monitoring checks for all hosts in the list and stores the results."""
        logging.debug("Starting monitoring checks for hosts: %s", self.hosts)
        results = []
        for host in self.hosts:
            status, details = self.check_host(host)
            results.append({"host": host, "status": status, "details": details})
            self.update_host_status(host, status, details)  # Update DB with status and details
            logging.debug("Host %s status: %s, Details: %s", host, status, details)
        return results

    def check_host(self, host, port=80):
        """
        Check if a host is reachable via:
        - A **ping test** to determine network connectivity.
        - A **TCP connection attempt** to the specified port.
        """
        logging.debug("Checking host: %s on port %d", host, port)
        
        # Step 1: Ping the host
        ping_status = "Ping failed"
        try:
            if platform.system().lower() == 'windows':
                cmd = ["ping", "-n", "1", "-w", "2000", host]
            else:
                cmd = ["ping", "-c", "1", "-W", "2", host]
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

        # Determine final status
        status = "Up" if "successful" in connection_status else "Down"
        details = f"{ping_status}, {connection_status}"
        
        return status, details

    def update_host_status(self, host, status, details):
        """Update the database with the monitoring result of a host."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE scans SET status = ?, details = ?, last_scan_time = ? WHERE domain = ?", 
                (status, details, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), host)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error("Failed to update status for %s: %s", host, e)
