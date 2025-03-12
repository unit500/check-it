import sqlite3
import requests
import socket
from urllib.parse import urlparse
from datetime import datetime

DB_PATH = '../data/data.db'

def load_sites(file_path='../sites.txt'):
    with open(file_path, 'r') as file:
        return [line.strip() for line in file if line.strip()]

def insert_check(conn, data):
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO checks (host, ip, port, response_time, status)
        VALUES (?, ?, ?, ?, ?)
    ''', data)
    conn.commit()

def check_site(url):
    parsed = urlparse(url)
    hostname = parsed.hostname or parsed.path
    port = 443 if parsed.scheme == "https" else 80

    try:
        ip = socket.gethostbyname(hostname)
    except Exception:
        ip = '0.0.0.0'

    start = datetime.now()
    try:
        response = requests.get(url, timeout=10)
        response_time = (datetime.now() - start).total_seconds()
        status = response.status_code
    except requests.RequestException:
        response_time = None
        status = 0

    return hostname, ip, port, response_time, status

if __name__ == "__main__":
    sites = load_sites('../sites.txt')
    conn = sqlite3.connect('../data/data.db')

    for url in sites:
        parsed = urlparse(url)
        host = parsed.hostname or parsed.path
        port = 443 if parsed.scheme == "https" else 80

        try:
            ip = socket.gethostbyname(host)
        except socket.error:
            ip = '0.0.0.0'

        start_time = datetime.now()
        try:
            response = requests.get(url, timeout=10)
            response_time = (datetime.now() - start_time).total_seconds()
            status = response.status_code
        except requests.RequestException:
            response_time = None
            status = 0

        data = (host, ip, port, response_time, status)
        insert_check(conn, data)
        print(f"Checked {url} - Status: {status}, Response time: {response_time}s")

if __name__ == "__main__":
    conn = sqlite3.connect('../data/data.db')
    sites = load_sites()
    for url in sites:
        insert_check_for_site(conn, url)
    conn.close()
