import sqlite3
import subprocess
import platform
import socket
import logging

class Monitoring:
    def __init__(self, db_path="../data/data.db", hosts=None, debug=False):
        self.db_path = db_path
        self.debug = debug
        if hosts is not None:
            self.hosts = hosts
        else:
            self.hosts = self.load_hosts_from_db()
    
    def load_hosts_from_db(self):
        """Read the scans table from the database and return the list of active domains."""
        hosts = []
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            # Read active scans (assuming finished=0 means still being monitored)
            cursor.execute("SELECT domain FROM scans WHERE finished = 0")
            rows = cursor.fetchall()
            hosts = [row[0] for row in rows]
            conn.close()
            logging.debug("Loaded hosts from DB: %s", hosts)
        except Exception as e:
            logging.error("Error loading hosts from DB: %s", e)
        return hosts

    def run(self):
        logging.debug("Starting monitoring checks for hosts: %s", self.hosts)
        results = []
        for host in self.hosts:
            status = self.check_host(host)
            results.append({"host": host, "status": status})
            logging.debug("Host %s status: %s", host, status)
        return results

    def check_host(self, host):
        logging.debug("Pinging host: %s", host)
        try:
            # Use appropriate ping command based on OS
            if platform.system().lower() == 'windows':
                cmd = ["ping", "-n", "1", "-w", "2000", host]
            else:
                cmd = ["ping", "-c", "1", "-W", "2", host]
            result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return "Up" if result.returncode == 0 else "Down"
        except Exception as e:
            logging.error("Error pinging %s: %s", host, e)
            return "Down"
