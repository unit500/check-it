import sqlite3
import requests
import socket
import time
from datetime import datetime
import os

def check_host(host):
    import requests
    from urllib.parse import urlparse

    parsed = urlparse(host)
    domain = parsed.hostname or parsed.path
    port = 443 if parsed.scheme == "https" else 80
    start_time = datetime.now()

    try:
        response = requests.get(host, timeout=10)
        response_time = (datetime.now() - start_time).total_seconds()
        ip = socket.gethostbyname(domain)
        status = 'up' if response.ok else 'down'
    except Exception as e:
        response_time = None
        ip = "Unknown"
        status = False
    else:
        status = True if response.ok else False

    return host, ip, port, response_time, response.ok
