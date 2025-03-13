import sqlite3

conn = sqlite3.connect('../data/data.db')
cursor = conn.cursor()

# Create the scans table (summary of monitored domains)
cursor.execute('''
    CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain TEXT,
        protocol TEXT,
        duration INTEGER,  -- monitoring duration in hours
        finished INTEGER DEFAULT 0,  -- 0 = not finished, 1 = finished
        successful_runs INTEGER DEFAULT 0,
        failed_runs INTEGER DEFAULT 0,
        start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_scan_time TIMESTAMP
    )
''')

# Create the checks table (individual check records)
cursor.execute('''
    CREATE TABLE IF NOT EXISTS checks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scan_id INTEGER,
        result TEXT,
        response_time REAL,
        check_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(scan_id) REFERENCES scans(id)
    )
''')

# Create the archive table (for finished scan summaries)
cursor.execute('''
    CREATE TABLE IF NOT EXISTS archive (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain TEXT,
        protocol TEXT,
        duration INTEGER,
        successful_runs INTEGER,
        failed_runs INTEGER,
        start_time TIMESTAMP,
        last_scan_time TIMESTAMP,
        finished INTEGER
    )
''')

# Updated duplicates table to include last_scan_time
cursor.execute('''
    CREATE TABLE IF NOT EXISTS duplicates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain TEXT,
        protocol TEXT,
        duration INTEGER,
        start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_scan_time TIMESTAMP
    )
''')

conn.commit()
conn.close()
print("Database initialized successfully.")
