import sqlite3

conn = sqlite3.connect('data.db')
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    host TEXT NOT NULL,
    ip TEXT NOT NULL,
    port INTEGER NOT NULL,
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    response_time_ms REAL,
    status TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS summary (
    host TEXT PRIMARY KEY,
    ip TEXT,
    port INTEGER,
    total_checks INTEGER,
    success_checks INTEGER,
    average_response_time REAL
)
''')

conn.commit()
conn.close()
