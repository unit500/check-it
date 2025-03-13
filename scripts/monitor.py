import sqlite3
import requests
import socket
from urllib.parse import urlparse
from datetime import datetime, timedelta

DB_PATH = '../data/data.db'

def is_valid_domain(domain):
    try:
        socket.gethostbyname(domain)
        return True
    except socket.gaierror:
        return False

def monitor_scans():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all non-finished scan records from scans table.
    cursor.execute("SELECT id, domain, protocol, duration, start_time, successful_runs, failed_runs FROM scans WHERE finished = 0")
    scans = cursor.fetchall()
    now = datetime.now()
    
    for scan in scans:
        scan_id, domain, protocol, duration, start_time_str, successful_runs, failed_runs = scan
        
        try:
            start_time = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
        except Exception:
            start_time = now  # fallback
        
        # If the domain is not valid, delete the record.
        if not is_valid_domain(domain):
            print(f"Domain {domain} is invalid. Deleting record.")
            cursor.execute("DELETE FROM scans WHERE id = ?", (scan_id,))
            conn.commit()
            continue
        
        # Check if the monitoring duration has passed.
        allowed_duration = timedelta(hours=int(duration))
        if now - start_time >= allowed_duration:
            print(f"Domain {domain} monitoring finished. Archiving record.")
            # Mark finished and update last_scan_time
            cursor.execute("UPDATE scans SET finished = 1, last_scan_time = ? WHERE id = ?", (now.strftime("%Y-%m-%d %H:%M:%S"), scan_id))
            conn.commit()
            # Move record to archive
            cursor.execute('''
                INSERT INTO archive (domain, protocol, duration, successful_runs, failed_runs, start_time, last_scan_time, finished)
                SELECT domain, protocol, duration, successful_runs, failed_runs, start_time, last_scan_time, finished
                FROM scans WHERE id = ?
            ''', (scan_id,))
            conn.commit()
            # Delete from scans
            cursor.execute("DELETE FROM scans WHERE id = ?", (scan_id,))
            conn.commit()
            continue
        
        # Otherwise, perform the HTTP check.
        url = f"{protocol}://{domain}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36"
        }
        try:
            start_check = datetime.now()
            response = requests.get(url, headers=headers, timeout=10)
            response_time = (datetime.now() - start_check).total_seconds()
            status = response.status_code
            result = "success" if status < 400 else "fail"
        except Exception as e:
            response_time = None
            status = 0
            result = "fail"
        
        # Insert individual check result into checks table
        cursor.execute('''
            INSERT INTO checks (scan_id, result, response_time)
            VALUES (?, ?, ?)
        ''', (scan_id, result, response_time))
        conn.commit()
        
        # Update summary counts in scans table
        if result == "success":
            successful_runs += 1
            cursor.execute("UPDATE scans SET successful_runs = ?, last_scan_time = ? WHERE id = ?",
                           (successful_runs, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), scan_id))
        else:
            failed_runs += 1
            cursor.execute("UPDATE scans SET failed_runs = ?, last_scan_time = ? WHERE id = ?",
                           (failed_runs, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), scan_id))
        conn.commit()
        print(f"Checked {url} - Status: {status}, Response time: {response_time}s")
    
    conn.close()

if __name__ == "__main__":
    monitor_scans()
