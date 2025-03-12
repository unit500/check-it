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
        th, td { border: 1px solid #ddd; padding: 8px; }
        th { background-color: #f2f2f2; }
        .up { color: green; }
        .down { color: red; }
    </style>
</head>
<body>
    <h2>Website Monitoring Report</h2>
    <table>
        <thead>
            <tr>
                <th>Domain</th>
                <th>Total Checks</th>
                <th>Successful Checks</th>
                <th>Failed Checks</th>
                <th>Average Response Time (s)</th>
                <th>Uptime (%)</th>
                <th>Last Checked</th>
                <th>Current Status</th>
            </tr>
        </thead>
        <tbody>
            {% for row in rows %}
            <tr>
                <td>{{ row.host }}</td>
                <td>{{ row.total }}</td>
                <td>{{ row.up }}</td>
                <td>{{ row.down }}</td>
                <td>{{ "%.2f"|format(row.avg_response) }}</td>
                <td>{{ "%.2f"|format(row.uptime_percent) }}%</td>
                <td>{{ row.last_checked }}</td>
                <td class="{{ 'up' if row.current_status else 'down' }}">
                    {{ 'UP' if row.current_status else 'DOWN' }}
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</body>
</html>
"""

def generate_report():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT host, checked_at, status, response_time FROM checks", conn)

    summary = []
    for host, group in df.groupby('host'):
        total = len(group)
        # Consider any status code less than 400 as a success (UP)
        up = group[group.status < 400].shape[0]
        down = total - up
        avg_response = group['response_time'].dropna().mean() or 0
        uptime_percent = (up / total) * 100 if total else 0
        last_checked = group['checked_at'].iloc[-1]
        current_status = group['status'].iloc[-1] < 400
        summary.append({
            'host': host,
            'total': total,
            'up': up,
            'down': down,
            'avg_response': avg_response,
            'uptime_percent': uptime_percent,
            'last_checked': last_checked,
            'current_status': current_status
        })

    html = Template(HTML_TEMPLATE).render(rows=summary)

    with open("../report.html", "w") as f:
        f.write(html)
    print("HTML report generated successfully.")

if __name__ == "__main__":
    generate_report()
