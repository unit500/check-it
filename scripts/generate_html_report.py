import sqlite3
import pandas as pd
from jinja2 import Template

DB_PATH = '../data/data.db'

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Website Monitoring Report</title>
    <style>
        body { font-family: Arial, sans-serif; }
        table { width: 100%; border-collapse: collapse; }
        th, td { border: 1px solid #ddd; padding: 8px; vertical-align: top; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <h2>Website Monitoring Report</h2>
    <table>
        <thead>
            <tr>
                <th>Domain</th>
                <th>Successful Runs</th>
                <th>Failed Runs</th>
                <th>Start Time</th>
                <th>Last Scan Time</th>
                <th>Duration (hrs)</th>
                <th>Finished</th>
            </tr>
        </thead>
        <tbody>
            {% for row in rows %}
            <tr>
                <td>{{ row.domain }}</td>
                <td>{{ row.successful_runs }}</td>
                <td>{{ row.failed_runs }}</td>
                <td>{{ row.start_time }}</td>
                <td>{{ row.last_scan_time }}</td>
                <td>{{ row.duration }}</td>
                <td>{{ "Yes" if row.finished else "No" }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</body>
</html>
"""

def generate_report():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT domain, successful_runs, failed_runs, start_time, last_scan_time, duration, finished FROM scans", conn)
    conn.close()
    html = Template(HTML_TEMPLATE).render(rows=df.to_dict(orient='records'))
    with open("../report.html", "w") as f:
        f.write(html)
    print("HTML report generated successfully.")

if __name__ == "__main__":
    generate_report()
